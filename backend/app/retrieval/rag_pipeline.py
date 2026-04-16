import re
import urllib.parse

import httpx
from app.config import settings
from app.processing.embedder import embed_text
from app.processing.reranker import rerank
from app.storage.vector_store import hybrid_search, get_sibling_chunks
from app.utils.logger import get_logger

logger = get_logger("rag_pipeline")

# Cache Ollama model availability — checked once, not on every query
_ollama_model_available: bool | None = None


def _is_quality_result(item: dict) -> bool:
    """Check if a search result is high-quality and relevant."""
    if item.get("distance", 1.0) > settings.relevance_threshold:
        return False

    text = item.get("chunk_text", item.get("summary", "")).strip()
    if len(text) < 30:
        return False

    lower = text.lower()
    garbage_markers = [
        "performing security verification",
        "this website uses a security service",
        "enable javascript",
        "please verify you are a human",
        "access denied",
        "403 forbidden",
    ]
    if any(marker in lower for marker in garbage_markers):
        return False

    words = text.split()
    if len(words) > 5:
        short_words = sum(1 for w in words if len(w) <= 2)
        if short_words / len(words) > 0.4:
            return False

    return True


def _ollama_has_model() -> bool:
    """Check if the required Ollama model is available. Only caches True — a False
    result is never cached so that Ollama can come up after the server starts."""
    global _ollama_model_available
    if _ollama_model_available is True:
        return True
    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
        models = [m["name"] for m in response.json().get("models", [])]
        if any(settings.ollama_model in m for m in models):
            _ollama_model_available = True
            return True
    except Exception:
        pass
    return False


def _warmup_ollama():
    """Load the Ollama model into memory by sending a minimal request."""
    if not _ollama_has_model():
        return
    try:
        httpx.post(
            settings.ollama_url,
            json={"model": settings.ollama_model, "prompt": "hi", "stream": False,
                  "options": {"num_predict": 1}},
            timeout=120.0,
        )
        logger.info(f"Ollama model '{settings.ollama_model}' warmed up")
    except Exception as e:
        logger.warning(f"Ollama warmup failed (will retry on first query): {e}")


def _query_ollama(prompt: str, max_tokens: int = 300) -> str:
    """Send a prompt to Ollama and get the response."""
    if not _ollama_has_model():
        return ""
    try:
        response = httpx.post(
            settings.ollama_url,
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "num_predict": max_tokens,
                },
            },
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return ""


def _query_t5(query: str, context: str) -> str:
    """Use the local T5 model as a fallback when Ollama is unavailable."""
    try:
        from app.processing.summarizer import _load_model, _tokenizer, _model, smart_truncate
        from app.config import DEVICE
        import torch

        _load_model()

        truncated_context = smart_truncate(context, max_chars=1500)
        prompt = f"question: {query} context: {truncated_context}"

        device = DEVICE if DEVICE != "mps" else "cpu"
        inputs = _tokenizer(
            prompt, return_tensors="pt", max_length=512, truncation=True
        ).to(device)

        with torch.no_grad():
            output_ids = _model.generate(
                **inputs,
                max_length=200,
                min_length=20,
                num_beams=4,
                repetition_penalty=1.2,
                no_repeat_ngram_size=3,
            )

        answer = _tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
        logger.info(f"T5 fallback answer generated ({len(answer)} chars)")
        return answer
    except Exception as e:
        logger.error(f"T5 fallback error: {e}")
        return ""


def _is_kb_query(query: str) -> bool:
    """Return True when the user explicitly asks about their personal knowledge base.

    These queries must always go through RAG — never the general LLM — because
    the whole point of InfoStore is that the user's content is indexed here.
    """
    q = query.lower()
    return any(kw in q for kw in [
        "bookmark", "my document", "my note", "my file", "my pdf",
        "i saved", "i uploaded", "i added", "you indexed", "you stored",
        "in my knowledge base", "from my kb", "from my docs",
        "read my", "show my", "find my", "search my",
    ])


def _is_domain_query(query: str) -> bool:
    """Return True if the query contains F1 / motorsport domain keywords.

    Domain queries always go through RAG regardless of rerank score,
    preventing false out-of-domain routing for legitimate KB questions.
    """
    q = query.lower()
    keywords = {
        # Sport / series
        "f1", "formula 1", "formula one", "formula1", "grand prix", " gp",
        "fia", "motorsport", "motor sport", "racing", "race",
        # Regulatory / financial
        "regulation", "budget", "cost cap", "financial", "cost", "spend",
        "cap", "fee", "prize", "payment", "allocation",
        # Technical
        "aerodynamic", "aero", "downforce", "drag", "drs", "active aero",
        "wing", "diffuser", "floor", "bodywork", "chassis", "suspension",
        "engine", "power unit", "hybrid", "ers", "mgu", "turbo", "fuel",
        "tire", "tyre", "brake", "gearbox", "transmission",
        # Race weekend / operations
        "qualifying", "sprint", "pit", "lap", "stint", "strategy",
        "parc ferme", "scrutineering", "safety car", "virtual safety",
        "sector", "track", "circuit", "corner",
        # Teams / drivers (common)
        "ferrari", "mercedes", "red bull", "mclaren", "alpine", "haas",
        "williams", "aston martin", "sauber", "kick",
        "verstappen", "hamilton", "leclerc", "norris", "russell", "alonso",
        "perez", "sainz", "piastri", "tsunoda",
        # Seasons / years in context
        "2025 f1", "2026 f1", "f1 2025", "f1 2026",
    }
    return any(kw in q for kw in keywords)


def _is_conversational(query: str) -> bool:
    """Return True if the query is conversational/general and doesn't need KB retrieval."""
    q = query.lower().strip().rstrip("?!.")

    conversational_patterns = {
        # Greetings
        "hi", "hello", "hey", "howdy", "hiya", "sup", "what's up", "whats up",
        "good morning", "good afternoon", "good evening", "good night",
        # How are you variants
        "how are you", "how are you doing", "how do you do", "how's it going",
        "hows it going", "how r u", "how are u", "you okay", "are you okay",
        "how are things", "how's everything",
        # Identity / capability
        "who are you", "what are you", "what can you do", "what do you do",
        "tell me about yourself", "introduce yourself", "what's your name",
        "whats your name", "who made you", "who created you", "your name",
        # Acknowledgements / chitchat
        "thanks", "thank you", "thank you so much", "ok", "okay", "cool", "great",
        "awesome", "got it", "understood", "makes sense", "nice", "perfect",
        "bye", "goodbye", "see you", "later", "sounds good", "sure", "alright",
    }

    if q in conversational_patterns:
        return True

    # Prefix matches for greeting-style openers
    greeting_prefixes = ("hi ", "hello ", "hey ", "good morning", "good afternoon",
                         "good evening", "how are you", "how r u")
    if any(q.startswith(p) for p in greeting_prefixes):
        return True

    return False


_TRAILING_BOILERPLATE = [
    r"for (?:the )?(?:most )?(?:accurate|up-to-date|current|latest|real-time)",
    r"(?:please|you (?:might|may|can|could)|i (?:would )?recommend).*?(?:check|visit|consult|refer|look at)",
    r"(?:check|visit|consult|look at).*?(?:official website|news source|weather|forecast|app|sources?)",
    r"reliable (?:weather|business|news|information|source)",
    r"official website",
    r"for (?:more|the latest|further) (?:information|details|updates?)",
    r"to get (?:the )?(?:most )?(?:accurate|current|latest|up-to-date)",
    r"(?:weather\.com|accuweather|bbc weather|weather channel|apple\.com|google)",
]


def _strip_apology(text: str) -> str:
    """Remove apologetic openers and boilerplate trailing sentences from LLM output."""
    # --- Leading apologies / disclaimers ---
    leading_patterns = [
        r"^I'm sorry(?: for(?: any|the)? (?:inconvenience|confusion|trouble|that))?,?\s*",
        r"^I apologize(?: for(?: any|the)? (?:confusion|inconvenience|trouble))?,?\s*",
        r"^Sorry(?: for(?: any|the)? (?:confusion|inconvenience|trouble))?,?\s*",
        r"^Unfortunately,?\s*",
        r"^I'm afraid,?\s*",
        r"^I regret to inform you(?: that)?,?\s*",
        r"^As an AI(?: language model|assistant)?,?\s*I (?:don't|cannot|can't|do not) have (?:real-time|current|live|access to real-time).*?\.\s*",
    ]
    for pattern in leading_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()

    # --- Trailing boilerplate sentences ("please check a website…") ---
    # Split into sentences and drop any trailing ones that match boilerplate patterns.
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    while sentences:
        last = sentences[-1].strip()
        if any(re.search(p, last, re.IGNORECASE) for p in _TRAILING_BOILERPLATE):
            sentences.pop()
        else:
            break
    text = " ".join(sentences).strip()

    # Capitalise first letter
    if text:
        text = text[0].upper() + text[1:]
    return text


def _is_weather_query(query: str) -> bool:
    q = query.lower()
    return any(w in q for w in [
        "weather", "temperature", "forecast", "raining", "snowing",
        "sunny", "cloudy", "humid", "wind speed", "feels like",
    ])


def _extract_location(query: str) -> str:
    """Pull a city/region name out of a weather question."""
    patterns = [
        r'(?:weather|temperature|forecast)\s+(?:in|for|at|of)\s+([A-Za-z][A-Za-z\s,]+?)(?:\s+today|\s+tomorrow|\s+now|\s+this week|\s*\?|$)',
        r'(?:how(?:\'s| is)(?: the)? weather(?: like)?(?:\s+in| in)?)\s+([A-Za-z][A-Za-z\s,]+?)(?:\s*\?|$)',
        r'what(?:\'s| is)(?: the)? weather(?: like)?(?:\s+in|\s+for)?\s+([A-Za-z][A-Za-z\s,]+?)(?:\s*\?|$)',
        r'([A-Za-z][A-Za-z\s,]{2,30}?)\s+weather',
    ]
    for pattern in patterns:
        m = re.search(pattern, query, re.IGNORECASE)
        if m:
            loc = m.group(1).strip().strip(",")
            if 2 < len(loc) < 60:
                return loc
    return ""


def _fetch_weather(query: str) -> str:
    """Return current weather for the location in the query using wttr.in (no API key)."""
    location = _extract_location(query)
    if not location:
        return ""
    encoded = urllib.parse.quote(location)
    try:
        # Custom format: location, condition, temp, feels-like, humidity, wind
        fmt = urllib.parse.quote("%l: %C, %t (feels like %f), humidity %h, wind %w")
        resp = httpx.get(
            f"https://wttr.in/{encoded}?format={fmt}",
            timeout=8.0,
            follow_redirects=True,
            headers={"User-Agent": "curl/7.68.0"},
        )
        if resp.status_code == 200:
            text = resp.text.strip()
            if text and "Unknown" not in text and len(text) > 8:
                return text
    except Exception as e:
        logger.warning(f"wttr.in error for '{location}': {e}")
    return ""


def _web_search(query: str) -> str:
    """Return a text snippet for the query via DuckDuckGo Instant Answers (no API key)."""
    try:
        url = (
            "https://api.duckduckgo.com/?q="
            + urllib.parse.quote(query)
            + "&format=json&no_html=1&skip_disambig=1"
        )
        resp = httpx.get(url, timeout=8.0, follow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        data = resp.json()
        # AbstractText is the best (Wikipedia summary)
        abstract = data.get("AbstractText", "").strip()
        if abstract and len(abstract) > 40:
            return abstract
        # Instant calculator / unit answers
        answer = data.get("Answer", "").strip()
        if answer:
            return answer
        # Related topic snippets as last resort
        snippets = [
            t["Text"] for t in data.get("RelatedTopics", [])
            if isinstance(t, dict) and t.get("Text")
        ]
        if snippets:
            return " | ".join(snippets[:3])
    except Exception as e:
        logger.warning(f"DuckDuckGo search error: {e}")
    return ""


def _answer_without_context(query: str, note: str = "") -> dict:
    """Answer a query from live data or LLM general knowledge — no KB context used.

    Priority:
    1. Weather queries → wttr.in real-time data
    2. Other queries → DuckDuckGo instant answer (if available)
    3. Fallback → Ollama general knowledge
    """
    extra_context = ""

    # 1. Real-time weather
    if _is_weather_query(query):
        weather = _fetch_weather(query)
        if weather:
            extra_context = f"[Live weather data] {weather}"
            logger.info(f"Weather data fetched: {weather}")

    # 2. DuckDuckGo instant answer for everything else
    if not extra_context:
        snippet = _web_search(query)
        if snippet:
            extra_context = f"[Web search result] {snippet}"
            logger.info(f"DDG snippet fetched ({len(snippet)} chars)")

    if extra_context:
        prompt = (
            "You are a helpful, direct assistant. Use the data below to answer "
            "the user's question in 1-3 natural sentences.\n"
            "RULES: NEVER start with 'I'm sorry' or any apology. "
            "NEVER end with suggestions to check a website or app.\n\n"
            f"Data: {extra_context}\n\n"
            f"User: {query}\nAssistant:"
        )
    else:
        prompt = (
            "You are a helpful, direct assistant. Answer the user's message from "
            "your general knowledge, naturally and concisely.\n"
            "RULES: NEVER start with 'I'm sorry', 'I apologize', 'Unfortunately', "
            "or 'As an AI'. NEVER end by telling the user to check a website or app. "
            "Just answer directly.\n\n"
            f"User: {query}\nAssistant:"
        )

    answer = _query_ollama(prompt, max_tokens=300)
    if answer:
        answer = _strip_apology(answer)

    # Static fallbacks if Ollama is unavailable
    if not answer:
        q = query.lower()
        if any(w in q for w in ["hi", "hello", "hey"]):
            answer = "Hello! I'm InfoStore, your F1 knowledge assistant. How can I help?"
        elif "how are you" in q:
            answer = "Doing great, thanks! What can I help you with?"
        elif any(w in q for w in ["who are you", "what are you", "what can you do"]):
            answer = (
                "I'm InfoStore — an AI assistant for Formula 1. I can answer questions "
                "about F1 regulations, aerodynamics research, race documents, and more."
            )
        elif any(w in q for w in ["thanks", "thank"]):
            answer = "You're welcome!"
        elif any(w in q for w in ["bye", "goodbye", "see you"]):
            answer = "Goodbye! Feel free to come back with more F1 questions."
        elif _is_weather_query(query):
            loc = _extract_location(query) or "that location"
            answer = f"I couldn't reach the weather service right now. Try weather.com or search for '{loc} weather' for current conditions."
        else:
            answer = "I'm not sure about that one. For F1 questions I'm your go-to — feel free to ask!"

    if note:
        logger.info(f"{note}: {query[:60]}")
    return {
        "answer": answer,
        "sources": [],
        "query": query,
        "evaluation": None,
        "crag_triggered": False,
    }


def _rewrite_query(original_query: str) -> str:
    """Use the LLM to rewrite a query for better retrieval (CRAG step)."""
    prompt = (
        "Rewrite the following search query to be more specific and likely to "
        "match relevant documents. Output ONLY the rewritten query, nothing else.\n\n"
        f"Original query: {original_query}\n\n"
        "Rewritten query:"
    )
    rewritten = _query_ollama(prompt, max_tokens=100)
    if rewritten and len(rewritten) > 5:
        logger.info(f"Query rewritten: '{original_query}' -> '{rewritten}'")
        return rewritten
    return original_query


def _evaluate_retrieval_quality(results: list[dict]) -> str:
    """Evaluate retrieval quality: 'good', 'marginal', or 'poor'."""
    if not results:
        return "poor"

    quality_count = sum(1 for r in results[:5] if _is_quality_result(r))

    if quality_count >= 3:
        return "good"
    elif quality_count >= 1:
        return "marginal"
    return "poor"


def build_context(
    results: list[dict], max_context_chars: int = 5000
) -> str:
    """Build context from retrieved chunks with parent-child expansion.

    For chunked documents, retrieves sibling chunks for richer context.
    """
    context_parts = []
    total = 0
    seen_parents = set()

    for item in results:
        if not _is_quality_result(item):
            continue

        # Use chunk_text (the actual indexed content) for context
        chunk = item.get("chunk_text", item.get("summary", "")).strip()
        parent_id = item.get("parent_id", "")

        # Parent-child expansion: fetch siblings for richer context
        if parent_id and parent_id not in seen_parents:
            seen_parents.add(parent_id)
            siblings = get_sibling_chunks(item["id"], window=1)
            if siblings and len(siblings) > 1:
                chunk = "\n".join(siblings)

        if total + len(chunk) > max_context_chars:
            remaining = max_context_chars - total
            if remaining > 100:
                context_parts.append(chunk[:remaining])
            break

        context_parts.append(chunk)
        total += len(chunk)

    return "\n\n".join(context_parts)


def _deduplicate_by_source(candidates: list[dict], max_per_source: int = 2) -> list[dict]:
    """Limit candidates to max_per_source chunks per unique source file.

    Prevents one document from dominating retrieval when it has many chunks
    or when the same file is indexed from multiple path prefixes.
    Uses just the filename (not full path) as the dedup key.
    """
    source_chunk_seen: set = set()  # (filename, chunk_index) pairs already kept
    source_counts: dict[str, int] = {}
    deduped = []
    for item in candidates:
        src = item.get("source", "")
        filename = src.replace("\\", "/").lower().rsplit("/", 1)[-1]
        chunk_idx = item.get("chunk_index", -1)
        identity = (filename, chunk_idx)
        # Skip exact same (file, chunk) from a duplicate-path entry
        if identity in source_chunk_seen:
            continue
        if source_counts.get(filename, 0) < max_per_source:
            deduped.append(item)
            source_counts[filename] = source_counts.get(filename, 0) + 1
            source_chunk_seen.add(identity)
    return deduped


def _retrieve_and_rerank(
    query: str, top_k: int, fetch_multiplier: int = 3
) -> list[dict]:
    """Retrieve candidates with hybrid search and rerank with cross-encoder."""
    query_embedding = embed_text(query)
    candidates = hybrid_search(
        query, query_embedding, top_k=max(top_k * fetch_multiplier, 15)
    )

    if not candidates:
        return []

    # Deduplicate: cap chunks per source before reranking so diverse documents
    # aren't crowded out by one over-represented file indexed multiple times.
    candidates = _deduplicate_by_source(candidates, max_per_source=2)

    # Rerank with cross-encoder for precision
    reranked = rerank(query, candidates, top_k=top_k)
    return reranked


def answer_query(query: str, top_k: int = 5) -> dict:
    """Full RAG pipeline with Corrective RAG (CRAG):

    0. Detect conversational queries and answer directly (no retrieval)
    1. Embed query -> hybrid search (RRF) -> cross-encoder rerank
    2. Evaluate retrieval quality
    3. If poor: rewrite query (CRAG) -> re-retrieve -> re-rerank
    4. Build context with parent-child chunk expansion
    5. Generate answer with Ollama (Granite 8B)
    6. Optionally evaluate answer quality (RAGAS)
    """
    # Step 0: Short-circuit for conversational / general queries
    if _is_conversational(query):
        return _answer_without_context(query, note="Conversational short-circuit")

    kb_query = _is_kb_query(query)

    # Step 1: Initial retrieval + reranking
    results = _retrieve_and_rerank(query, top_k)

    if not results:
        if kb_query:
            return {
                "answer": (
                    "I couldn't find anything matching that in your knowledge base. "
                    "If it's a bookmark, try syncing first via the sidebar."
                ),
                "sources": [],
                "query": query,
                "evaluation": None,
                "crag_triggered": False,
            }
        return {
            "answer": "No relevant information found in the knowledge base.",
            "sources": [],
            "query": query,
            "evaluation": None,
            "crag_triggered": False,
        }

    # Step 2: Evaluate retrieval quality (CRAG)
    quality = _evaluate_retrieval_quality(results)
    crag_triggered = False

    # Step 3: Only rewrite on clearly poor results (marginal is acceptable)
    if quality == "poor":
        logger.info(f"CRAG triggered: retrieval quality is '{quality}', rewriting query")
        crag_triggered = True
        rewritten_query = _rewrite_query(query)

        if rewritten_query != query:
            new_results = _retrieve_and_rerank(rewritten_query, top_k)
            if new_results:
                new_quality = _evaluate_retrieval_quality(new_results)
                if new_quality != "poor":
                    results = new_results
                    logger.info(
                        f"CRAG: rewritten query improved quality "
                        f"'{quality}' -> '{new_quality}'"
                    )

    # Step 4a: Gate on rerank score — if the best match is too weak AND the query
    # is neither domain-specific nor an explicit KB reference, use the general LLM.
    # KB queries (bookmark/document/note references) always stay in RAG — if nothing
    # was found, tell the user rather than hallucinating a browser-help response.
    max_rerank = max((r.get("rerank_score", 0.0) for r in results), default=0.0)
    if max_rerank < 2.5 and not _is_domain_query(query) and not kb_query:
        logger.info(
            f"KB not relevant for query (max_rerank={max_rerank:.2f}), "
            "falling back to general LLM response"
        )
        return _answer_without_context(query, note="Out-of-domain fallback")

    if max_rerank < 2.5 and kb_query:
        return {
            "answer": (
                "I searched your knowledge base but couldn't find a good match for that. "
                "If it's a bookmark you recently added, try syncing via the sidebar first."
            ),
            "sources": results[:3],
            "query": query,
            "evaluation": None,
            "crag_triggered": crag_triggered,
        }

    # Step 4b: Build context with parent-child expansion
    context = build_context(results)
    quality_results = [r for r in results if _is_quality_result(r)]

    if not context:
        return {
            "answer": (
                "I found some results but none were closely relevant to your "
                "question. Try being more specific, or check the sources below."
            ),
            "sources": results[:top_k],
            "query": query,
            "evaluation": None,
            "crag_triggered": crag_triggered,
        }

    # Step 5: Generate answer with Ollama, fall back to T5 if unavailable
    prompt = (
        "You are a helpful knowledge base assistant. Answer the user's question "
        "using ONLY the information provided below. Be concise, clear, and "
        "conversational. If the information doesn't fully answer the question, "
        "say what you can and note what's missing. Do not make up information.\n\n"
        f"--- Information from knowledge base ---\n{context}\n"
        f"--- End of information ---\n\n"
        f"User question: {query}\n\n"
        f"Answer:"
    )

    answer = _query_ollama(prompt, max_tokens=500)
    if answer:
        answer = _strip_apology(answer)

    if not answer or len(answer) < 10:
        answer = _query_t5(query, context)

    if not answer or len(answer) < 10:
        parts = [r["summary"].strip() for r in quality_results[:3] if r.get("summary")]
        answer = (
            "Here's what I found:\n\n" + "\n\n".join(parts)
            if parts
            else "I couldn't generate an answer. Check the sources below."
        )

    logger.info(f"RAG answer generated for query: {query[:50]}...")

    # Build source list for frontend
    sources = quality_results[:top_k]
    if len(sources) < top_k:
        seen = {r["id"] for r in sources}
        for r in results:
            if r["id"] not in seen:
                sources.append(r)
                if len(sources) >= top_k:
                    break

    # Step 6: Optional RAGAS evaluation
    evaluation = None
    if settings.enable_evaluation:
        try:
            from app.retrieval.evaluator import evaluate_rag

            evaluation = evaluate_rag(query, answer, context, results)
        except Exception as e:
            logger.error(f"Evaluation error: {e}")

    return {
        "answer": answer,
        "sources": sources,
        "query": query,
        "evaluation": evaluation,
        "crag_triggered": crag_triggered,
    }
