"""
Fetch URL — Hal9-style stdin/stdout MCP.

Reads a URL (or a natural language request containing a URL) via input(),
fetches the page, strips HTML to plain text, and prints the content.
"""

import re
import os
import requests
from bs4 import BeautifulSoup

MAX_CHARS = int(os.environ.get("FETCH_MAX_CHARS", "4000"))
TIMEOUT   = int(os.environ.get("FETCH_TIMEOUT", "15"))
UA        = "mcp.build/fetch-url (+https://mcp.build/fetch-url/)"

URL_RE = re.compile(r"https?://[^\s]+")


def extract_url(text: str):
    m = URL_RE.search(text)
    return m.group(0).rstrip(".,;)'\"\\>") if m else None


def fetch_url(url: str) -> str:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        return f"Failed to fetch {url}: {e}"

    ct = r.headers.get("content-type", "")
    if "html" not in ct and "text" not in ct:
        return f"URL returned non-text content ({ct}). Only HTML and plain-text pages are supported."

    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    lines = [l.strip() for l in soup.get_text("\n", strip=True).splitlines() if l.strip()]
    text  = "\n".join(lines)

    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + f"\n\n[content truncated — showing first {MAX_CHARS} characters]"

    return f"Content from {url}:\n\n{text}"


if __name__ == "__main__":
    prompt = input()
    url = extract_url(prompt)
    if not url:
        print("Please provide a URL. Example: fetch https://example.com")
    else:
        print(fetch_url(url))
