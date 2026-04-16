import trafilatura
from playwright.async_api import async_playwright
from app.utils.logger import get_logger

logger = get_logger("web_scraper")


def scrape_with_trafilatura(url: str) -> str | None:
    """Fast static HTML extraction using Trafilatura."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            logger.warning(f"Trafilatura fetch failed for {url}")
            return None
        text = trafilatura.extract(
            downloaded,
            include_tables=True,
            include_comments=False,
            favor_precision=True,
        )
        if text and len(text.strip()) > 50:
            logger.info(f"Trafilatura extracted {len(text)} chars from {url}")
            return text.strip()
        return None
    except Exception as e:
        logger.error(f"Trafilatura error for {url}: {e}")
        return None


async def scrape_with_playwright(url: str) -> str | None:
    """Dynamic JS rendering via Playwright for JS-heavy SPAs."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            # Wait for JS rendering and potential Cloudflare challenge
            await page.wait_for_timeout(3000)
            content = await page.inner_text("body")

            # Check if we hit a Cloudflare/bot check page
            if content and "security" in content.lower() and "verification" in content.lower():
                logger.info(f"Cloudflare challenge detected for {url}, waiting...")
                await page.wait_for_timeout(5000)
                content = await page.inner_text("body")

            await browser.close()

            if content and len(content.strip()) > 50:
                # Filter out security/bot check pages
                lower = content.lower()
                if "performing security verification" in lower and len(content) < 200:
                    logger.warning(f"Only got security page for {url}")
                    return None
                logger.info(f"Playwright extracted {len(content)} chars from {url}")
                return content.strip()
            return None
    except Exception as e:
        logger.error(f"Playwright error for {url}: {e}")
        return None


async def extract_from_url(url: str) -> str:
    """Try Trafilatura first (fast), fall back to Playwright (thorough)."""
    # Skip URLs that are unlikely to have useful content
    skip_domains = ["outlook.office.com", "mail.google.com", "accounts.google.com",
                    "login.", "signin.", "auth."]
    if any(d in url.lower() for d in skip_domains):
        raise ValueError(f"Skipping login/mail URL: {url}")

    text = scrape_with_trafilatura(url)
    if text:
        return text

    logger.info(f"Falling back to Playwright for {url}")
    text = await scrape_with_playwright(url)
    if text:
        return text

    raise ValueError(f"Failed to extract content from URL: {url}")
