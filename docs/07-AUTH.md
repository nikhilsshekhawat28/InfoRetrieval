# 07 — Authentication & Security

## Current Auth Posture

InfoStore v2 is a **single-user, local-first application**. There is no user authentication, authorization, or session management. All endpoints are publicly accessible on `localhost`.

This is an intentional design decision for the course project scope — the threat model is a developer running this on their own machine, not a multi-tenant production deployment.

---

## CORS Configuration

The backend allows cross-origin requests only from the frontend dev server:

```python
# backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

This means:
- Requests from `http://localhost:5173` (Vite dev server) are allowed
- All other origins are blocked by the browser's Same-Origin Policy
- API is still accessible from curl, Postman, or any non-browser client (CORS is browser-only)

---

## Security Considerations

### What is protected?
- Nothing, currently. The API is open on localhost.

### What data is at risk?
- ChromaDB contents (indexed knowledge base)
- File paths of watched documents
- Chrome Bookmarks (URL list)
- Configured `.env` values (model paths, directories)

### Input Validation
Pydantic models validate all incoming JSON requests. Malformed requests return `422 Unprocessable Entity`. There is no SQL injection risk (ChromaDB uses its own Python API, not raw SQL queries to user inputs).

### File Upload Safety
- Uploads are written to `backend/uploads/` temporarily
- File extension is checked before processing (only known types are handled)
- No execution of uploaded files

### URL Scraping Safety
- Login/mail/oauth URLs are blocked in `web_scraper.extract_from_url()`
- Playwright runs in headless mode with no credential storage

---

## What Would Be Needed for Production

| Concern | Current | Production Recommendation |
|---------|---------|---------------------------|
| Authentication | None | JWT or session cookie with login flow |
| Authorization | None | Role-based access to different knowledge base sections |
| HTTPS | No (HTTP only) | TLS termination via nginx/Caddy reverse proxy |
| Rate limiting | None | FastAPI middleware or nginx limit_req |
| API keys | None | Bearer token header for API access |
| CORS | localhost only | Configure for actual deployment domain |
| Secrets management | Plain `.env` file | Environment secrets manager (Vault, AWS SSM) |
| Multi-user | Not supported | User-scoped ChromaDB collections |

---

## Environment Secrets

The `.env` file contains no actual secrets (no API keys, no passwords) because the system uses entirely local/free services. The `.env` is still git-ignored for good practice, since it contains:
- File paths (user-specific)
- Directory paths to user's personal document library
- Chrome Bookmarks file path (reveals user's OS and username)

Template is provided in `.env.example`.
