"""arXiv scanner — fetch recent preprints by category."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from typing import List

import requests

from .base import BaseScanner, RawDocument

_NS = "http://www.w3.org/2005/Atom"
_API = "https://export.arxiv.org/api/query"


class ArxivScanner(BaseScanner):
    source_name = "arxiv"

    def __init__(self, timeout: int = 20, rate_limit_s: float = 1.0) -> None:
        self.timeout = timeout
        self.rate_limit_s = rate_limit_s

    def scan(
        self,
        categories: List[str] | None = None,
        query: str = "",
        max_results: int = 50,
    ) -> List[RawDocument]:
        categories = categories or ["cs.AI", "physics.gen-ph"]
        docs: List[RawDocument] = []

        for cat in categories:
            q = f"cat:{cat}" if not query else f"cat:{cat} AND all:{query}"
            params = {
                "search_query": q,
                "sortBy": "submittedDate",
                "start": 0,
                "max_results": max_results,
            }
            try:
                resp = requests.get(_API, params=params, timeout=self.timeout)
                resp.raise_for_status()
                root = ET.fromstring(resp.content)
                for entry in root.findall(f"{{{_NS}}}entry"):
                    title_el = entry.find(f"{{{_NS}}}title")
                    summary_el = entry.find(f"{{{_NS}}}summary")
                    id_el = entry.find(f"{{{_NS}}}id")
                    if title_el is None:
                        continue
                    title = (title_el.text or "").strip().replace("\n", " ")
                    body = (summary_el.text if summary_el is not None else "").strip()
                    url = (id_el.text or "").strip() if id_el is not None else ""
                    docs.append(RawDocument(
                        source=self.source_name,
                        title=title,
                        body=body,
                        url=url,
                        domain=cat,
                        metadata={"category": cat},
                    ))
            except Exception:
                pass
            time.sleep(self.rate_limit_s)

        return docs
