import json
import uuid
import chromadb
from datetime import datetime
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("vector_store")

_client = None
_collection = None

# RRF constant (Cormack et al., SIGIR 2009)
RRF_K = 60


def _get_collection() -> chromadb.Collection:
    global _client, _collection
    if _collection is not None:
        return _collection

    logger.info(f"Initializing ChromaDB at {settings.chroma_persist_dir}")
    _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    _collection = _client.get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info(
        f"ChromaDB collection '{settings.chroma_collection}' ready "
        f"({_collection.count()} documents)"
    )
    return _collection


def add_entry(
    summary: str,
    embedding: list[float],
    source_type: str,
    source: str,
    tags: list[str],
    full_text: str = "",
) -> str:
    """Store a single document in ChromaDB (legacy non-chunked path)."""
    collection = _get_collection()
    doc_id = str(uuid.uuid4())

    metadata = {
        "source_type": source_type,
        "source": source,
        "tags": json.dumps(tags),
        "created_at": datetime.now().isoformat(),
        "full_text_length": len(full_text),
    }

    collection.add(
        ids=[doc_id],
        embeddings=[embedding],
        documents=[summary],
        metadatas=[metadata],
    )

    logger.info(f"Stored entry {doc_id}: {source_type} from {source}")
    return doc_id


def add_chunks(
    chunks: list[str],
    embeddings: list[list[float]],
    source_type: str,
    source: str,
    tags: list[str],
    summary: str = "",
    full_text: str = "",
) -> list[str]:
    """Store multiple chunks from a single document with a shared parent_id.

    Each chunk gets its own embedding for precise retrieval.
    The summary is stored in metadata for frontend display.
    """
    collection = _get_collection()
    parent_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    chunk_ids = []

    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        doc_id = str(uuid.uuid4())
        metadata = {
            "source_type": source_type,
            "source": source,
            "tags": json.dumps(tags),
            "created_at": now,
            "full_text_length": len(full_text),
            "parent_id": parent_id,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "summary": summary[:1000],  # T5 summary for display
        }

        collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[chunk],
            metadatas=[metadata],
        )
        chunk_ids.append(doc_id)

    logger.info(
        f"Stored {len(chunks)} chunks (parent={parent_id}): "
        f"{source_type} from {source}"
    )
    return chunk_ids


def get_sibling_chunks(doc_id: str, window: int = 1) -> list[str]:
    """Get neighboring chunks for parent-child context expansion.

    Retrieves sibling chunks within `window` positions of the given chunk.
    """
    collection = _get_collection()
    try:
        result = collection.get(ids=[doc_id], include=["metadatas"])
        if not result["metadatas"]:
            return []

        meta = result["metadatas"][0]
        parent_id = meta.get("parent_id")
        chunk_index = meta.get("chunk_index")
        if parent_id is None or chunk_index is None:
            return []

        # Fetch all chunks from the same parent
        all_chunks = collection.get(
            where={"parent_id": parent_id},
            include=["documents", "metadatas"],
        )

        # Sort by chunk_index and return window around target
        indexed = []
        for i, m in enumerate(all_chunks["metadatas"]):
            indexed.append((m.get("chunk_index", 0), all_chunks["documents"][i]))
        indexed.sort(key=lambda x: x[0])

        # Extract window around the target chunk
        siblings = []
        for idx, doc in indexed:
            if abs(idx - chunk_index) <= window:
                siblings.append(doc)

        return siblings
    except Exception as e:
        logger.error(f"Sibling chunk retrieval error: {e}")
        return []


def _build_result_item(doc_id, document, metadata, distance):
    """Build a standardized result dict from ChromaDB fields."""
    # For chunked entries, use the stored summary for display;
    # for legacy entries, the document IS the summary
    display_summary = metadata.get("summary", document)
    return {
        "id": doc_id,
        "summary": display_summary if display_summary else document,
        "chunk_text": document,  # the actual indexed text
        "source_type": metadata.get("source_type", ""),
        "source": metadata.get("source", ""),
        "tags": json.loads(metadata.get("tags", "[]")),
        "distance": distance,
        "created_at": metadata.get("created_at", ""),
        "parent_id": metadata.get("parent_id", ""),
        "chunk_index": metadata.get("chunk_index", -1),
    }


def search(
    query_embedding: list[float],
    top_k: int = 5,
    where: dict | None = None,
) -> list[dict]:
    """Search by vector similarity."""
    collection = _get_collection()

    kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    items = []
    for i in range(len(results["ids"][0])):
        items.append(_build_result_item(
            results["ids"][0][i],
            results["documents"][0][i],
            results["metadatas"][0][i],
            results["distances"][0][i],
        ))

    logger.info(f"Search returned {len(items)} results")
    return items


def hybrid_search(
    query_text: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """Hybrid search with Reciprocal Rank Fusion (RRF).

    Combines dense vector search and keyword search using RRF scoring
    instead of a flat distance boost. RRF properly merges rankings from
    multiple retrieval methods.
    """
    collection = _get_collection()
    fetch_k = top_k * 3  # over-fetch for better fusion

    # --- Dense vector search ---
    vector_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=fetch_k,
        include=["documents", "metadatas", "distances"],
    )

    # --- Keyword search ---
    keyword_results = None
    keywords = [w for w in query_text.split() if len(w) > 3]
    if keywords:
        try:
            keyword_filter = {
                "$or": [{"$contains": kw} for kw in keywords[:3]]
            }
            keyword_results = collection.query(
                query_embeddings=[query_embedding],
                n_results=fetch_k,
                where_document=keyword_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            pass

    # --- Reciprocal Rank Fusion ---
    # Build rank lists
    rrf_scores = {}  # doc_id -> rrf_score
    doc_data = {}  # doc_id -> result dict

    def process_result_list(results):
        if not results or not results["ids"][0]:
            return
        for rank, i in enumerate(range(len(results["ids"][0]))):
            doc_id = results["ids"][0][i]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + (
                1.0 / (RRF_K + rank + 1)
            )
            if doc_id not in doc_data:
                doc_data[doc_id] = _build_result_item(
                    doc_id,
                    results["documents"][0][i],
                    results["metadatas"][0][i],
                    results["distances"][0][i],
                )

    process_result_list(vector_results)
    if keyword_results:
        process_result_list(keyword_results)

    # Sort by RRF score (higher = more relevant)
    ranked_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)

    merged = []
    for doc_id in ranked_ids[:top_k]:
        item = doc_data[doc_id]
        item["rrf_score"] = rrf_scores[doc_id]
        merged.append(item)

    logger.info(
        f"Hybrid search (RRF): {len(merged)} results from "
        f"{len(doc_data)} candidates"
    )
    return merged


def get_collection_stats() -> dict:
    """Get stats about the stored collection with type breakdown and file counts."""
    import os
    from pathlib import Path

    collection = _get_collection()
    total = collection.count()

    type_counts = {}
    chunk_count = 0
    parent_ids = set()
    if total > 0:
        try:
            all_meta = collection.get(include=["metadatas"])
            for meta in all_meta["metadatas"]:
                st = meta.get("source_type", "unknown")
                type_counts[st] = type_counts.get(st, 0) + 1
                if meta.get("parent_id"):
                    chunk_count += 1
                    parent_ids.add(meta["parent_id"])
        except Exception:
            pass

    file_counts = {"images_on_disk": 0, "documents_on_disk": 0, "bookmarks": 0}
    watch_dirs = settings.watch_dirs
    if watch_dirs:
        image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
        doc_exts = {".pdf", ".docx", ".doc", ".txt", ".md"}
        for dir_path in watch_dirs.split(","):
            path = Path(dir_path.strip()).expanduser()
            if path.exists():
                for f in path.rglob("*"):
                    if f.is_file():
                        ext = f.suffix.lower()
                        if ext in image_exts:
                            file_counts["images_on_disk"] += 1
                        elif ext in doc_exts:
                            file_counts["documents_on_disk"] += 1

    try:
        bookmark_path = Path(settings.bookmark_path).expanduser()
        if bookmark_path.exists():
            import json as _json

            with open(bookmark_path, "r") as f:
                bm_data = _json.load(f)

            def _count_bookmarks(node):
                count = 0
                if node.get("type") == "url":
                    count += 1
                for child in node.get("children", []):
                    count += _count_bookmarks(child)
                return count

            for root in bm_data.get("roots", {}).values():
                if isinstance(root, dict):
                    file_counts["bookmarks"] += _count_bookmarks(root)
    except Exception:
        pass

    return {
        "total_documents": total,
        "total_chunks": chunk_count,
        "unique_parents": len(parent_ids),
        "collection_name": settings.chroma_collection,
        "by_type": type_counts,
        "file_counts": file_counts,
    }


def is_source_indexed(source: str) -> bool:
    """Check if a file path/source has already been indexed in ChromaDB."""
    collection = _get_collection()
    try:
        results = collection.get(
            where={"source": source},
            limit=1,
            include=[],
        )
        return len(results["ids"]) > 0
    except Exception as e:
        logger.warning(f"Could not check index status for {source}: {e}")
        return False


def delete_by_source(source: str) -> int:
    """Delete all chunks stored for a given source path/URL.

    Returns the number of chunks deleted.
    """
    collection = _get_collection()
    try:
        results = collection.get(where={"source": source}, include=[])
        if results["ids"]:
            collection.delete(ids=results["ids"])
            logger.info(f"Deleted {len(results['ids'])} chunks for source: {source}")
            return len(results["ids"])
    except Exception as e:
        logger.error(f"delete_by_source error for '{source}': {e}")
    return 0


def delete_entry(doc_id: str) -> bool:
    """Delete a document by ID. If it's a chunk, also deletes siblings."""
    collection = _get_collection()
    try:
        # Check if it has a parent_id (is a chunk)
        result = collection.get(ids=[doc_id], include=["metadatas"])
        if result["metadatas"]:
            parent_id = result["metadatas"][0].get("parent_id")
            if parent_id:
                # Delete all sibling chunks
                all_siblings = collection.get(
                    where={"parent_id": parent_id},
                    include=[],
                )
                if all_siblings["ids"]:
                    collection.delete(ids=all_siblings["ids"])
                    logger.info(
                        f"Deleted {len(all_siblings['ids'])} chunks "
                        f"(parent={parent_id})"
                    )
                    return True

        collection.delete(ids=[doc_id])
        logger.info(f"Deleted entry {doc_id}")
        return True
    except Exception as e:
        logger.error(f"Delete error: {e}")
        return False
