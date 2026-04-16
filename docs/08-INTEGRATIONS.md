# 08 — External Integrations

## Overview

InfoStore uses five external integrations, all free and requiring no API keys:

| Integration | Purpose | Module | Key Endpoint/Path |
|-------------|---------|--------|-------------------|
| Ollama | Local LLM inference | `rag_pipeline.py` | `http://localhost:11434/api/generate` |
| wttr.in | Weather data | `rag_pipeline.py` | `https://wttr.in/{location}?format=...` |
| DuckDuckGo | General web answers | `rag_pipeline.py` | `https://api.duckduckgo.com/?q=...` |
| Chrome Bookmarks | Bookmark ingestion | `bookmark_sync.py` | Local file: `~/.../Bookmarks` |
| Playwright | JS-heavy web scraping | `web_scraper.py` | Headless Chromium |

---

## 1. Ollama (Local LLM)

### What It Is
Ollama is a tool for running large language models locally. It exposes a local HTTP API at `http://localhost:11434`. InfoStore uses it for:
- Answering user queries with retrieved context (RAG)
- Answering conversational/general queries without context
- Rewriting queries (CRAG)
- Adding context prefixes to chunks (contextual retrieval, when enabled)

### Model Used
`granite3.1-dense:2b` — IBM Granite 3.1 Dense, 2 billion parameters. Fast enough for real-time responses, good instruction following.

### Configuration
```ini
# .env
RAG_LLM_MODEL=granite3.1-dense:2b
```

### API Call
```python
def _query_ollama(prompt: str, context: str = "", model: str = None) -> str:
    model = model or settings.rag_llm_model
    payload = {
        "model": model,
        "prompt": f"Context:\n{context}\n\nQuestion: {prompt}\nAnswer:" if context else prompt,
        "stream": False
    }
    response = httpx.post(
        "http://localhost:11434/api/generate",
        json=payload,
        timeout=60.0
    )
    return response.json().get("response", "").strip()
```

### Warmup
On startup, `main.py` calls `_warmup_ollama()` which sends a trivial prompt to pre-load the model into memory, avoiding a 10-30s cold start on the first user query.

### Fallback
If Ollama is unavailable or returns an error, the pipeline falls back to `_query_t5()` which uses the locally loaded T5 model for generation (lower quality but always available).

### Model Availability Check
```python
def _ollama_has_model(model_name: str) -> bool:
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=5)
        models = r.json().get("models", [])
        return any(m["name"].startswith(model_name) for m in models)
    except Exception:
        return False
```

---

## 2. wttr.in (Weather API)

### What It Is
`wttr.in` is a free weather API with no authentication required. It returns weather data in plain text format, suitable for LLM consumption.

### When Used
When `_is_weather_query(query)` returns `True`, the pipeline calls `_fetch_weather()`.

### Location Extraction
```python
def _extract_location(query: str) -> str:
    """Extract city/location name from a weather query."""
    # Remove common weather words and return the remaining location
    cleaned = re.sub(r"\b(weather|temperature|forecast|in|at|for|today|tomorrow|"
                     r"current|what|is|the|how|hot|cold|warm|rain|sunny)\b",
                     "", query, flags=re.IGNORECASE).strip()
    return cleaned or "Boston"  # Default to Boston
```

### API Call
```python
FORMAT_STRING = "%l: %C, %t (feels like %f), humidity %h, wind %w"

def _fetch_weather(location: str) -> str:
    encoded = urllib.parse.quote(location)
    url = f"https://wttr.in/{encoded}?format={urllib.parse.quote(FORMAT_STRING)}"
    response = httpx.get(url, timeout=10.0)
    return response.text.strip()
    # Example: "Boston: Partly cloudy, +12°C (feels like +9°C), humidity 65%, wind 15km/h N"
```

### LLM Formatting
The raw wttr.in string is passed as context to Ollama, which formats it as a natural language response. This gives responses like:
> "It's currently partly cloudy in Boston with a temperature of 12°C (feels like 9°C). Humidity is at 65% and winds are coming from the north at 15 km/h."

---

## 3. DuckDuckGo Instant Answers

### What It Is
DuckDuckGo's free, no-key Instant Answers API returns brief factual summaries for many queries.

### When Used
In `_answer_without_context()` for non-weather, non-KB, non-domain queries that don't have strong KB matches (e.g., "Who is Apple's CEO?").

### API Call
```python
def _web_search(query: str) -> str:
    """Query DuckDuckGo Instant Answers API."""
    params = {
        "q": query,
        "format": "json",
        "no_html": "1",
        "skip_disambig": "1"
    }
    url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(params)
    response = httpx.get(url, timeout=10.0)
    data = response.json()
    
    abstract = data.get("Abstract", "")
    answer = data.get("Answer", "")
    return answer or abstract or ""
```

### Fallback Behavior
If DDG returns no result (empty abstract/answer), the pipeline falls back to pure Ollama generation with no external context (using the model's training knowledge).

---

## 4. Chrome Bookmarks

### What It Is
Chrome stores all bookmarks in a local JSON file. On Windows, its location is:
`C:\Users\{username}\AppData\Local\Google\Chrome\User Data\Default\Bookmarks`

### Configuration
```ini
# .env
BOOKMARK_PATH=C:/Users/nikhi/AppData/Local/Google/Chrome/User Data/Default/Bookmarks
```

### File Format
Chrome Bookmarks is a JSON file with this structure:
```json
{
  "roots": {
    "bookmark_bar": {
      "children": [
        {
          "type": "url",
          "url": "https://example.com",
          "name": "Example",
          "date_added": "13374747474747"
        },
        {
          "type": "folder",
          "name": "Research",
          "children": [...]
        }
      ]
    },
    "other": { "children": [...] },
    "synced": { "children": [...] }
  }
}
```

### Parsing
`bookmark_sync.py` recursively traverses the tree, collecting all `type: "url"` nodes. The `date_added` field uses Chrome's epoch (microseconds since Jan 1, 1601) which is converted to Unix time.

### Sync Process
1. Parse bookmarks file → list of `{url, title, folder, date_added}`
2. For each bookmark: check `is_source_indexed(url)` in ChromaDB
3. If not indexed: scrape URL via `web_scraper.extract_from_url(url)`
4. Process and store as `source_type="bookmark"`
5. Track synced/skipped/failed counts

---

## 5. Playwright (Web Scraping)

### What It Is
Playwright is an end-to-end browser automation library. InfoStore uses it as a fallback scraper for JavaScript-heavy web pages that Trafilatura can't extract text from.

### When Used
After Trafilatura fails (`len(text) < 50 chars`), Playwright launches a headless Chromium browser.

### Key Details
- **Headless mode**: No visible browser window
- **3-second wait**: `page.wait_for_timeout(3000)` allows JavaScript to render
- **Cloudflare handling**: Wait gives time for Cloudflare challenges to resolve
- **Content extraction**: After rendering, Trafilatura extracts text from the rendered HTML

### Installation
Playwright requires a separate browser download:
```bash
playwright install chromium
```

### Code
```python
async def scrape_with_playwright(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(3000)
        html = await page.content()
        await browser.close()
    return trafilatura.extract(html) or ""
```

### URLs Skipped
The scraper refuses to process:
- URLs containing: `login`, `signin`, `sign-in`, `oauth`, `mail`, `auth`
- This avoids hanging on login pages or sending requests to auth endpoints

---

## Trafilatura (Primary Scraper)

While not an "external" service (it's a local Python library), Trafilatura is the primary extraction method:

```python
import trafilatura

def scrape_with_trafilatura(url: str) -> str:
    downloaded = trafilatura.fetch_url(url)
    return trafilatura.extract(downloaded) or ""
```

Trafilatura uses heuristics to extract main content (article text) from HTML, removing navigation, ads, footers, etc. It's much faster than Playwright (~1s vs ~5s) and works for most static or server-rendered pages.
