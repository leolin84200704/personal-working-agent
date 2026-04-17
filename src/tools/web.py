"""
Web tools - HTTP fetch and DuckDuckGo search for the agent.

Provides web_fetch() and web_search() functions, plus WEB_TOOL_DEFINITIONS
for registering with the Anthropic tool_use API.

No new dependencies beyond httpx (already in requirements.txt).
"""
from __future__ import annotations

import re
from html import unescape
from urllib.parse import quote_plus

import httpx

# ─── Constants ────────────────────────────────────────────────────

_TIMEOUT = 30  # seconds
_DEFAULT_MAX_CHARS = 80_000
_DEFAULT_MAX_RESULTS = 5

_USER_AGENT = (
    "Mozilla/5.0 (compatible; LISCodeAgent/1.0; +https://github.com/lis-code-agent)"
)

# ─── Helpers ──────────────────────────────────────────────────────


def _strip_html(html: str) -> str:
    """Remove HTML tags and decode entities. Simple regex approach."""
    # Remove script/style blocks entirely
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode HTML entities
    text = unescape(text)
    # Collapse whitespace (preserve single newlines for readability)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ─── web_fetch ────────────────────────────────────────────────────


def web_fetch(url: str, max_chars: int = _DEFAULT_MAX_CHARS) -> str:
    """
    Fetch a URL via HTTP GET and return its text content.

    HTML pages are stripped of tags for cleaner output.
    Content is truncated to *max_chars*.
    Errors are returned as descriptive strings (never raises).
    """
    try:
        with httpx.Client(
            timeout=_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        text = resp.text

        # Strip HTML if the response looks like HTML
        if "html" in content_type or text.lstrip().lower().startswith("<!doctype") or text.lstrip().startswith("<html"):
            text = _strip_html(text)

        # Truncate
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n... (truncated, showing {max_chars} of {len(text)} chars)"

        return text

    except httpx.TimeoutException:
        return f"Error: Request timed out after {_TIMEOUT}s for URL: {url}"
    except httpx.HTTPStatusError as exc:
        return f"Error: HTTP {exc.response.status_code} for URL: {url}"
    except httpx.RequestError as exc:
        return f"Error: Request failed for URL: {url} - {exc}"
    except Exception as exc:
        return f"Error: Unexpected error fetching {url} - {exc}"


# ─── web_search ───────────────────────────────────────────────────

_DDG_URL = "https://html.duckduckgo.com/html/"


def web_search(query: str, max_results: int = _DEFAULT_MAX_RESULTS) -> str:
    """
    Search the web via DuckDuckGo HTML lite endpoint.

    Returns formatted text with title, URL, and snippet for each result.
    Errors are returned as descriptive strings (never raises).
    """
    try:
        with httpx.Client(
            timeout=_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            resp = client.post(
                _DDG_URL,
                data={"q": query},
            )
            resp.raise_for_status()

        html = resp.text
        results = _parse_ddg_results(html, max_results)

        if not results:
            return f"No results found for: {query}"

        lines = [f"Search results for: {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}")
            lines.append(f"   URL: {r['url']}")
            if r["snippet"]:
                lines.append(f"   {r['snippet']}")
            lines.append("")

        return "\n".join(lines).strip()

    except httpx.TimeoutException:
        return f"Error: Search timed out after {_TIMEOUT}s for query: {query}"
    except httpx.HTTPStatusError as exc:
        return f"Error: HTTP {exc.response.status_code} during search for: {query}"
    except httpx.RequestError as exc:
        return f"Error: Search request failed for: {query} - {exc}"
    except Exception as exc:
        return f"Error: Unexpected error searching for: {query} - {exc}"


def _parse_ddg_results(html: str, max_results: int) -> list[dict[str, str]]:
    """
    Parse DuckDuckGo HTML lite results page.

    Each result block looks roughly like:
      <a rel="nofollow" class="result__a" href="...">Title</a>
      <a class="result__snippet" href="...">Snippet text</a>
    """
    results: list[dict[str, str]] = []

    # Find result links: class="result__a"
    link_pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]*)"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    snippet_pattern = re.compile(
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        re.DOTALL,
    )

    link_matches = list(link_pattern.finditer(html))
    snippet_matches = list(snippet_pattern.finditer(html))

    for i, link_match in enumerate(link_matches):
        if len(results) >= max_results:
            break

        raw_url = link_match.group(1)
        title = _strip_html(link_match.group(2)).strip()

        # DuckDuckGo wraps URLs in a redirect; extract the actual URL
        url = _extract_ddg_url(raw_url)

        snippet = ""
        if i < len(snippet_matches):
            snippet = _strip_html(snippet_matches[i].group(1)).strip()

        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet})

    return results


def _extract_ddg_url(raw_url: str) -> str:
    """
    Extract the actual URL from DuckDuckGo's redirect wrapper.

    DDG links look like: //duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com&rut=...
    """
    from urllib.parse import unquote, urlparse, parse_qs

    if "uddg=" in raw_url:
        parsed = urlparse(raw_url)
        qs = parse_qs(parsed.query)
        if "uddg" in qs:
            return unquote(qs["uddg"][0])

    # If it's already a direct URL
    if raw_url.startswith("http"):
        return raw_url

    # Fallback: strip leading //
    if raw_url.startswith("//"):
        return "https:" + raw_url

    return raw_url


# ─── Tool Definitions (Anthropic tool_use schema) ────────────────

WEB_TOOL_DEFINITIONS = [
    {
        "name": "web_fetch",
        "description": (
            "Fetch a web page by URL and return its text content. "
            "HTML tags are stripped for cleaner output. "
            "Use this to read documentation, API references, or any web page."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch (must include scheme, e.g. https://...)",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to return (default 80000)",
                    "default": 80000,
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Search the web using DuckDuckGo and return results with title, URL, "
            "and snippet. Use this to find documentation, solutions, or information "
            "that is not available in local files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
]
