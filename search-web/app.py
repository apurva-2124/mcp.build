"""
Search Web — Hal9-style stdin/stdout MCP.

Reads a natural language search query via input(), calls the Exa API,
and prints a formatted summary of the top results.
"""

import os
import requests

NUM_RESULTS = int(os.environ.get("SEARCH_NUM_RESULTS", "5"))
EXA_API_URL = "https://api.exa.ai/search"


def search_web(query: str, num_results: int = NUM_RESULTS) -> str:
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        return "Error: EXA_API_KEY environment variable is not set."

    try:
        response = requests.post(
            EXA_API_URL,
            json={
                "query": query,
                "numResults": num_results,
                "contents": {"summary": True, "highlights": True},
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        return f"Search failed: {e}"

    results = data.get("results", [])
    if not results:
        return f"No results found for: {query}"

    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        title   = r.get("title", "Untitled")
        url     = r.get("url", "")
        summary = (r.get("summary") or "").strip()
        lines.append(f"{i}. {title}")
        lines.append(f"   {url}")
        if summary:
            lines.append(f"   {summary}")
        lines.append("")

    return "\n".join(lines).strip()


if __name__ == "__main__":
    query = input()
    print(search_web(query))
