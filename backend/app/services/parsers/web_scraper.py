"""Scrape web page content."""

import re


async def parse_url(url: str) -> dict:
    """Fetch and extract content from a URL."""
    try:
        import httpx
        from bs4 import BeautifulSoup
    except ImportError:
        return {
            "title": url,
            "raw_text": f"[网页抓取需要安装 httpx 和 beautifulsoup4: {url}]",
            "char_count": 0,
            "word_count": 0,
            "error": "Dependencies not installed",
        }

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # Extract title
        title = ""
        if soup.title:
            title = soup.title.get_text(strip=True)

        # Remove scripts, styles, nav, footer
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # Try to find main content
        main = soup.find("main") or soup.find("article") or soup.body
        if main:
            raw_text = main.get_text(separator="\n", strip=True)
        else:
            raw_text = soup.get_text(separator="\n", strip=True)

        # Clean up: collapse multiple newlines
        raw_text = re.sub(r"\n{3,}", "\n\n", raw_text)

        return {
            "title": title or url,
            "raw_text": raw_text,
            "source_url": url,
            "char_count": len(raw_text),
            "word_count": len(raw_text.split()),
        }
    except Exception as e:
        return {
            "title": url,
            "raw_text": f"[抓取失败: {e}]",
            "source_url": url,
            "char_count": 0,
            "word_count": 0,
            "error": str(e),
        }
