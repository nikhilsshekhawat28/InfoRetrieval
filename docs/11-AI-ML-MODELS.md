# 11 — AI/ML Models

## Overview

InfoStore uses five distinct AI/ML models, each serving a specific purpose in the pipeline:

| Model | Role | Size | Fine-tuned? | Where loaded |
|-------|------|------|-------------|--------------|
| T5 (fine-tuned) | Text summarization & tagging | ~250MB | Yes (CNN/DailyMail) | `summarizer.py`, `tagger.py` |
| BLIP + LoRA | Image captioning | ~1.4GB | Yes (Flickr8k) | `image_captioning.py` |
| BGE-base-en-v1.5 | Text embeddings | ~440MB | No | `embedder.py` |
| ms-marco-MiniLM-L-6-v2 | Cross-encoder reranking | ~65MB | No | `reranker.py` |
| Granite 3.1 Dense 2B | LLM answer generation | ~2GB | No | Ollama (separate process) |

---

## 1. T5 Summarizer (Fine-tuned)

### Base Model
`google/flan-t5-base` — A variant of T5 (Text-to-Text Transfer Transformer) fine-tuned on instruction-following tasks. Used here for seq2seq summarization.

### Fine-tuning
The model was fine-tuned on **CNN-DailyMail** dataset:
- Task: News article → headline/summary generation
- Training script: `training/` directory
- Checkpoint: `backend/app/models/t5_finetuned/final_model_h200/`
- Hardware used: H200 GPU (based on directory name)

### Architecture
- Encoder-decoder transformer
- 250M parameters
- Input: "summarize: {text}" (T5's prefix format)
- Output: Summary text (beam search, 4 beams)

### Generation Parameters
```python
model.generate(
    **inputs,
    max_length=150,
    min_length=30,
    num_beams=4,
    repetition_penalty=1.2,     # Discourages repeating phrases
    no_repeat_ngram_size=3,     # Prevents 3-gram repetition
    early_stopping=True
)
```

### Smart Truncation
Input text is truncated at sentence boundaries to max 2000 characters before tokenization:
```python
def smart_truncate(text: str, max_chars=2000) -> str:
    if len(text) <= max_chars:
        return text
    # Find last sentence boundary before max_chars
    truncated = text[:max_chars]
    last_period = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'))
    return truncated[:last_period+1] if last_period > 0 else truncated
```

### Dual Use
The same T5 model serves both:
1. **Summarization** (`summarizer.py`): "summarize: {text}" → 1–3 sentence summary
2. **Tagging** (`tagger.py`): "Generate N short topic tags for this text, separated by commas: {text[:500]}" → comma-separated tags

---

## 2. BLIP Image Captioning (Fine-tuned with LoRA)

### Base Model
`Salesforce/blip-image-captioning-base` — BLIP (Bootstrapping Language-Image Pretraining). A vision-language model that generates text descriptions of images.

### Fine-tuning Method: LoRA
**LoRA (Low-Rank Adaptation)** inserts small trainable matrices into frozen model layers. This allows fine-tuning with a fraction of the parameters.

Configuration used:
```python
lora_config = LoraConfig(
    r=16,              # Rank of adaptation matrices
    lora_alpha=32,     # Scaling factor
    target_modules=["query", "value"],  # Which attention layers to adapt
    lora_dropout=0.1,
    bias="none",
    task_type="SEQ_2_SEQ_LM"
)
```

### Fine-tuning Dataset
**Flickr8k** — 8,000 images with 5 captions each. Specialized for diverse image descriptions.

### Inference
```python
def generate_caption(image_path: str) -> str:
    image = Image.open(image_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt").to(DEVICE)
    generated_ids = model.generate(**inputs, max_new_tokens=100)
    return processor.decode(generated_ids[0], skip_special_tokens=True)
```

### Model Loading with LoRA
```python
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
lora_path = settings.blip_model_path  # ../models/blip_finetuned

if Path(lora_path).exists():
    model = PeftModel.from_pretrained(model, lora_path)
    model = model.merge_and_unload()   # Merge LoRA weights into base model for inference
else:
    logger.warning("LoRA adapter not found, using base BLIP")
```

### When BLIP Is Used vs OCR
```python
def _process_image(file_path: str):
    ocr_text, method = ocr_pipeline.run_ocr(file_path)
    
    if len(ocr_text.strip()) >= 20:
        # Image contains significant text → use OCR result
        return ocr_text, "image_ocr"
    else:
        # Image is primarily visual → use BLIP caption
        caption = image_captioning.generate_caption(file_path)
        return caption, "image_caption"
```

---

## 3. BGE-base-en-v1.5 (Embeddings)

### What It Is
`BAAI/bge-base-en-v1.5` — A sentence embedding model from Beijing Academy of AI. MTEB (Massive Text Embedding Benchmark) leader for its size class.

- **Dimensions:** 768
- **Max sequence length:** 512 tokens
- **Normalization:** L2-normalized (required for cosine similarity)
- **Architecture:** BERT-based transformer

### Why BGE?
- Top MTEB performance at ~440MB
- Outperforms OpenAI Ada on many retrieval benchmarks
- L2-normalized embeddings = cosine similarity = dot product (fast)
- No API calls needed (runs locally)

### Query vs Document Encoding
BGE requires a specific prefix for queries (but not documents):
```python
# Document encoding (stored in ChromaDB)
embedding = model.encode(chunk_text, normalize_embeddings=True)

# Query encoding (at retrieval time)
query_with_prefix = f"Represent this sentence for searching relevant passages: {query}"
query_embedding = model.encode(query_with_prefix, normalize_embeddings=True)
```

**Note:** The codebase should apply this prefix in `embedder.py` or `rag_pipeline.py`. If not applied, retrieval quality degrades ~15–20% per BGE's documentation.

### Batched Encoding
```python
def embed_texts(texts: list[str], batch_size=32) -> list[list[float]]:
    return model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > 100
    ).tolist()
```

---

## 4. Cross-Encoder Reranker

### What It Is
`cross-encoder/ms-marco-MiniLM-L-6-v2` — A BERT-based cross-encoder trained on the MS MARCO passage retrieval dataset. Trained to predict query-document relevance.

- **Architecture:** 6-layer MiniLM (lightweight)
- **Input:** concatenated `[CLS] query [SEP] document [SEP]`
- **Output:** Single relevance score (higher = more relevant)
- **Size:** ~65MB

### Bi-encoder vs Cross-encoder

| Aspect | Bi-encoder (BGE) | Cross-encoder (ms-marco) |
|--------|-----------------|--------------------------|
| Encoding | Query and doc separately | Query + doc jointly |
| Speed | Fast (pre-computed embeddings) | Slow (can't pre-compute) |
| Accuracy | Good (approximate) | Excellent (precise) |
| Use case | Initial retrieval over all docs | Re-scoring top-k candidates |

This two-stage approach is the standard retrieval pattern:
1. Bi-encoder retrieves top 15 candidates from all N documents (fast)
2. Cross-encoder re-scores the 15 candidates (slow but precise)

### Code
```python
_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device=DEVICE)

def rerank(query: str, documents: list[dict], top_k=5) -> list[dict]:
    texts = [doc.get("chunk_text") or doc.get("summary", "") for doc in documents]
    pairs = [(query, text) for text in texts]
    scores = _model.predict(pairs)
    for doc, score in zip(documents, scores):
        doc["rerank_score"] = float(score)
    return sorted(documents, key=lambda x: x["rerank_score"], reverse=True)[:top_k]
```

### Score Interpretation
Cross-encoder scores are raw logits, not probabilities:
- Score > 3.0: Highly relevant
- Score 1.0 – 3.0: Relevant
- Score < 1.0: Marginally relevant
- Score < -1.0: Not relevant

The RAG pipeline uses `2.5` as the threshold for "not relevant enough for RAG" fallback.

---

## 5. IBM Granite 3.1 Dense 2B (LLM via Ollama)

### What It Is
Granite 3.1 Dense is IBM's open-source language model, 2 billion parameters. It's accessed via Ollama's local inference API.

- **Parameters:** 2B
- **Context window:** 128K tokens
- **Strengths:** Instruction following, multilingual, code understanding
- **License:** Apache 2.0

### Why Granite?
- Small enough to run on consumer hardware (6–8GB VRAM or CPU)
- Fast inference for interactive responses
- Good instruction following for RAG prompting
- Free and open-source

### Prompt Format
```python
# RAG prompt (with context)
prompt = f"""Context information:
{context}

Based ONLY on the context above, answer this question:
{query}

If the context doesn't contain enough information, say so clearly.
Answer:"""

# Conversational prompt (no context)
prompt = query  # Direct pass-through
```

### Ollama API Call
```python
import httpx

response = httpx.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "granite3.1-dense:2b",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,     # Low temperature for factual answers
            "top_p": 0.9,
        }
    },
    timeout=60.0
)
answer = response.json()["response"]
```

### Fallback Chain
```
1. Ollama (granite3.1-dense:2b) → preferred
2. T5 model (_query_t5) → if Ollama unavailable
3. Concatenate top-3 summaries → if T5 fails
```

---

## Model Loading Strategy

All models use **lazy loading** — they're loaded on first use, not at import time. This prevents unnecessary VRAM usage if only some features are needed:

```python
_summarizer = None

def _load_summarizer():
    global _summarizer
    if _summarizer is None:
        _summarizer = pipeline("summarization", model=settings.summarizer_model)
    return _summarizer
```

**Exception:** BGE and cross-encoder are loaded at module import time (since they're always needed for any query). This adds ~2–5 seconds to server startup but ensures zero latency on the first query.

---

## Hardware Requirements

| Configuration | Min VRAM | Recommended |
|---------------|----------|-------------|
| T5 + BGE + reranker | 2GB GPU or CPU | 4GB GPU |
| + BLIP | 4GB GPU | 8GB GPU |
| + Ollama Granite 2B | 6GB total | 8GB GPU |
| Full stack on CPU | N/A | 16GB RAM |

**Current deployment:** Windows machine, `DEVICE_PREFERENCE=auto` (resolves to CUDA if available, else CPU).

---

## Training Scripts

Located in `training/`:
- `train_t5_summarizer.py` — CNN/DailyMail seq2seq fine-tuning
- `train_blip_captioner.py` — Flickr8k image captioning with LoRA

Both scripts save checkpoints to `models/` directory. The `final_model_h200` directory name suggests training was done on an H200 instance.
