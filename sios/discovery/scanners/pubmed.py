"""PubMed scanner — fetch biomedical literature via NCBI E-utilities."""

from __future__ import annotations

import time
from typing import List

import requests

from .base import BaseScanner, RawDocument

_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_SUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


class PubMedScanner(BaseScanner):
    source_name = "pubmed"

    def __init__(self, timeout: int = 20, rate_limit_s: float = 0.4) -> None:
        self.timeout = timeout
        self.rate_limit_s = rate_limit_s

    def scan(self, query: str = "machine learning", max_results: int = 30) -> List[RawDocument]:
        try:
            resp = requests.get(
                _SEARCH,
                params={"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"},
                timeout=self.timeout,
            )
            ids = resp.json().get("esearchresult", {}).get("idlist", [])
        except Exception:
            return []

        docs: List[RawDocument] = []
        for pmid in ids[:max_results]:
            try:
                data = requests.get(
                    _SUMMARY,
                    params={"db": "pubmed", "id": pmid, "retmode": "json"},
                    timeout=self.timeout,
                ).json()
                article = data.get("result", {}).get(pmid, {})
                title = article.get("title", "")
                if not title:
                    continue
                docs.append(RawDocument(
                    source=self.source_name,
                    source_id=pmid,
                    title=title,
                    domain="biomedical",
                    metadata=article,
                ))
                time.sleep(self.rate_limit_s)
            except Exception:
                continue

        return docs
