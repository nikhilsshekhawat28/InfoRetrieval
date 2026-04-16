# 14 — Testing

## Overview

The project has two testing frameworks:

| Framework | Location | Type | Scope |
|-----------|----------|------|-------|
| Playwright | `frontend/` | E2E (browser) | Full UI interactions |
| Vitest | `frontend/` | Unit | Component logic |

The backend has no automated tests beyond manual API testing. This is a known gap acknowledged in the course project.

---

## Frontend: Playwright E2E Tests

### Configuration (`playwright.config.ts`)

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
  },
});
```

### Running Playwright Tests
```bash
cd frontend
npx playwright test              # Run all tests
npx playwright test --ui         # Interactive test runner
npx playwright show-report       # Show HTML test report
```

### Test Fixtures (`playwright-fixture.ts`)

```typescript
import { test as base, expect } from '@playwright/test';

// Custom fixtures can extend base test
export const test = base.extend({
  // e.g., pre-authenticated page, pre-populated KB
});
export { expect };
```

### What to Test (Recommendations)

Since the project is an AI system, meaningful E2E tests focus on UI behavior rather than AI output correctness:

```typescript
// Example test structure
test('welcome message shows on empty conversation', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Your AI Knowledge Base')).toBeVisible();
});

test('sends a message and shows loading indicator', async ({ page }) => {
  await page.goto('/');
  await page.fill('textarea[placeholder="Ask anything..."]', 'Hello');
  await page.keyboard.press('Enter');
  await expect(page.locator('.animate-typing-dot').first()).toBeVisible();
});

test('sidebar opens and shows ingestion options', async ({ page }) => {
  await page.goto('/');
  await page.click('[data-sidebar="trigger"]');
  await expect(page.getByText('Sync Bookmarks')).toBeVisible();
  await expect(page.getByText('Upload File')).toBeVisible();
});

test('stats bar shows document counts', async ({ page }) => {
  await page.goto('/');
  // Wait for stats to load
  await page.waitForResponse('**/api/stats');
  await expect(page.getByText(/\d+ Files/)).toBeVisible();
});

test('copy button appears on hover', async ({ page }) => {
  // This requires a pre-seeded message in state
  // or mocking the API
});
```

---

## Frontend: Vitest Unit Tests

### Setup
```typescript
// vitest.config.ts (if exists, else in vite.config.ts)
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
  }
})
```

### Running Vitest
```bash
cd frontend
npm run test          # Watch mode
npm run test:run      # Single run
npm run test:coverage # With coverage report
```

### What to Test

**`lib/api.ts`:**
```typescript
import { describe, it, expect, vi } from 'vitest'
import { api } from '../lib/api'

describe('api client', () => {
  it('throws on HTTP error response', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      text: () => Promise.resolve("Internal Server Error")
    })
    await expect(api.health()).rejects.toThrow()
  })
  
  it('includes correct Content-Type for chat', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ answer: "test" })
    })
    await api.chat({ query: "test", top_k: 5 })
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/chat'),
      expect.objectContaining({
        headers: { 'Content-Type': 'application/json' }
      })
    )
  })
})
```

**`lib/types.ts` (SOURCE_TYPE_ICONS):**
```typescript
it('has icons for all known source types', () => {
  const expected = ['document', 'url', 'image_caption', 'text', 'bookmark', 'image_ocr']
  expected.forEach(type => {
    expect(SOURCE_TYPE_ICONS[type]).toBeDefined()
  })
})
```

**Component rendering:**
```typescript
import { render, screen } from '@testing-library/react'
import { ChatMessageBubble } from '../components/ChatMessage'

it('renders user message right-aligned', () => {
  const msg = { role: 'user', content: 'Hello', sources: [], timestamp: new Date() }
  render(<ChatMessageBubble message={msg} />)
  expect(screen.getByText('Hello')).toBeInTheDocument()
})
```

---

## Backend: Manual Testing

### Using the FastAPI Swagger UI
When the backend is running:
- Navigate to `http://localhost:8000/docs`
- All endpoints are interactive with "Try it out" buttons
- Useful for testing individual endpoints without the frontend

### Using curl

```bash
# Health check
curl http://localhost:8000/health

# Store a URL
curl -X POST http://localhost:8000/api/store/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://en.wikipedia.org/wiki/Formula_One", "tags": ["f1"]}'

# Chat query
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is DRS?", "top_k": 5}'

# Get stats
curl http://localhost:8000/api/stats

# Force reindex
curl -X POST http://localhost:8000/api/watchdog/force-reindex
```

### Using HTTPie (more readable)
```bash
pip install httpie

# Chat
http POST localhost:8000/api/chat query="How does KERS work?" top_k:=5

# Store URL
http POST localhost:8000/api/store/url url="https://example.com" tags:='["test"]'
```

---

## Testing the RAG Pipeline

The RAG pipeline is hard to unit test because it integrates multiple ML models. Recommended approach:

### 1. Test query routing independently
```python
# backend/tests/test_rag_routing.py
from app.retrieval.rag_pipeline import (
    _is_conversational, _is_kb_query, _is_domain_query, _is_weather_query
)

def test_conversational_detection():
    assert _is_conversational("hi there") == True
    assert _is_conversational("hello!") == True
    assert _is_conversational("what is DRS in F1?") == False

def test_kb_query_detection():
    assert _is_kb_query("read my bookmark CS 5800") == True
    assert _is_kb_query("i saved a pdf about algorithms") == True
    assert _is_kb_query("what is the weather in boston") == False

def test_weather_query_detection():
    assert _is_weather_query("what's the weather in NYC?") == True
    assert _is_weather_query("boston weather today") == True
    assert _is_weather_query("who is apple's CEO") == False
```

### 2. Test chunker independently
```python
from app.processing.chunker import chunk_text, _split_into_sentences

def test_chunker_no_sentence_cuts():
    text = "First sentence. Second sentence. Third sentence."
    chunks = chunk_text(text, chunk_size=10, overlap=2)
    # Each chunk should end at a sentence boundary
    for chunk in chunks:
        assert chunk.strip()[-1] in ".!?" or chunk == chunks[-1]

def test_short_text_single_chunk():
    text = "This is a short text."
    chunks = chunk_text(text, chunk_size=300)
    assert len(chunks) == 1
    assert chunks[0] == text

def test_overlap_creates_duplicate_sentences():
    text = " ".join([f"Sentence {i}." for i in range(50)])
    chunks = chunk_text(text, chunk_size=30, overlap=10)
    assert len(chunks) > 1
    # First sentence of chunk N+1 should appear in chunk N
```

### 3. Test boilerplate stripping
```python
from app.retrieval.rag_pipeline import _strip_apology

def test_strips_trailing_boilerplate():
    text = "DRS is a drag reduction system. Please check official website for more info."
    result = _strip_apology(text)
    assert "official website" not in result
    assert "DRS is a drag reduction system" in result

def test_strips_leading_apology():
    text = "I'm sorry, but I don't have that information. The race was held in Monaco."
    result = _strip_apology(text)
    assert "I'm sorry" not in result
```

---

## CI/CD Considerations

Currently no CI/CD pipeline exists. For a production setup:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: cd frontend && npm ci
      - run: cd frontend && npm run build   # Type check + build
      - run: cd frontend && npx playwright install --with-deps
      - run: cd frontend && npx playwright test
  
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: cd backend && pip install -r requirements.txt
      - run: cd backend && python -m pytest tests/ -v
```

---

## Known Testing Gaps

1. **No backend unit tests** — All ML-heavy code has no automated tests
2. **No integration tests** — ChromaDB + RAG pipeline not tested end-to-end
3. **No performance tests** — No benchmarks for indexing speed or query latency
4. **AI output not testable deterministically** — LLM outputs vary; tests can only check structure, not content quality
5. **No mock for external services** — Tests would fail without Ollama running
