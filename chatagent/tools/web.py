"""Web-related tools."""

import json
from typing import Any, Dict
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from .base import Tool


class WebFetchTool(Tool):
    """Tool for fetching web content."""

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "Fetch content from a URL and extract text. Returns the page content as text."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch",
                },
                "extract_text": {
                    "type": "boolean",
                    "description": "Whether to extract only text content (default: True)",
                    "default": True,
                },
            },
            "required": ["url"],
        }

    @property
    def requires_confirmation(self) -> bool:
        """Web fetch requires user confirmation for safety."""
        return True

    def execute(self, url: str, extract_text: bool = True) -> str:
        """Fetch web content."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            with httpx.Client(follow_redirects=True, timeout=30.0) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()

                if extract_text:
                    soup = BeautifulSoup(response.text, "html.parser")

                    # Remove script and style elements
                    for script in soup(["script", "style", "nav", "footer"]):
                        script.decompose()

                    # Get text
                    text = soup.get_text()

                    # Clean up whitespace
                    lines = (line.strip() for line in text.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    text = "\n".join(chunk for chunk in chunks if chunk)

                    # Limit length
                    if len(text) > 10000:
                        text = text[:10000] + "\n\n[Content truncated...]"

                    return f"URL: {url}\nStatus: {response.status_code}\n\n{text}"
                else:
                    content = response.text
                    if len(content) > 10000:
                        content = content[:10000] + "\n\n[Content truncated...]"
                    return f"URL: {url}\nStatus: {response.status_code}\n\n{content}"

        except httpx.TimeoutException:
            return f"Error: Request timed out for {url}"
        except httpx.HTTPError as e:
            return f"Error fetching URL: {str(e)}"
        except Exception as e:
            return f"Error: {str(e)}"


class GoogleSearchTool(Tool):
    """Tool for performing Google searches."""

    @property
    def name(self) -> str:
        return "google_web_search"

    @property
    def description(self) -> str:
        return "Search the web using Google. Returns search results with titles, URLs, and snippets."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    @property
    def requires_confirmation(self) -> bool:
        """Web search requires user confirmation for safety."""
        return True

    def execute(self, query: str, num_results: int = 5) -> str:
        """Perform Google search."""
        try:
            # Use DuckDuckGo HTML as a Google alternative (no API key required)
            encoded_query = quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")
                results = []

                # Parse DuckDuckGo results
                for result_div in soup.find_all("div", class_="result", limit=num_results):
                    title_elem = result_div.find("a", class_="result__a")
                    snippet_elem = result_div.find("a", class_="result__snippet")

                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link = title_elem.get("href", "")
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

                        results.append({
                            "title": title,
                            "url": link,
                            "snippet": snippet,
                        })

                if not results:
                    return f"No search results found for: {query}"

                output = f"Search results for: {query}\n\n"
                for i, result in enumerate(results, 1):
                    output += f"{i}. {result['title']}\n"
                    output += f"   URL: {result['url']}\n"
                    if result['snippet']:
                        output += f"   {result['snippet']}\n"
                    output += "\n"

                return output

        except httpx.HTTPError as e:
            return f"Error performing search: {str(e)}"
        except Exception as e:
            return f"Error: {str(e)}"
