"""Wikipedia scanner — extract concept links from topic pages."""

from __future__ import annotations

from typing import List

import requests

from .base import BaseScanner, RawDocument

_API = "https://en.wikipedia.org/w/api.php"


class WikipediaScanner(BaseScanner):
    source_name = "wikipedia"

    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout

    def scan(self, topics: List[str] | None = None) -> List[RawDocument]:
        topics = topics or ["Artificial intelligence", "Neuroscience"]
        docs: List[RawDocument] = []

        for topic in topics:
            try:
                # Fetch page extract (short description)
                extract_resp = requests.get(
                    _API,
                    params={
                        "action": "query",
                        "titles": topic,
                        "prop": "extracts",
                        "exintro": True,
                        "explaintext": True,
                        "format": "json",
                    },
                    timeout=self.timeout,
                )
                pages = extract_resp.json().get("query", {}).get("pages", {})
                body = ""
                for page in pages.values():
                    body = (page.get("extract") or "")[:1000]

                # Fetch linked titles
                link_resp = requests.get(
                    _API,
                    params={
                        "action": "query",
                        "titles": topic,
                        "prop": "links",
                        "pllimit": 50,
                        "format": "json",
                    },
                    timeout=self.timeout,
                )
                link_pages = link_resp.json().get("query", {}).get("pages", {})
                linked: List[str] = []
                for page in link_pages.values():
                    linked = [lk["title"] for lk in page.get("links", [])]

                docs.append(RawDocument(
                    source=self.source_name,
                    title=topic,
                    body=body,
                    url=f"https://en.wikipedia.org/wiki/{topic.replace(' ', '_')}",
                    domain="encyclopedia",
                    metadata={"linked_topics": linked},
                ))
            except Exception:
                continue

        return docs
