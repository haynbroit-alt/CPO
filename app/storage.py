import json
from pathlib import Path
from typing import Dict, List, Optional

from config import LEDGER_FILE as _DEFAULT_LEDGER

_ledger = Path(_DEFAULT_LEDGER)


def append(record: Dict) -> None:
    with open(_ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def all_cpos() -> List[Dict]:
    if not _ledger.exists():
        return []
    with open(_ledger, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def find_by_hash(content_hash: str) -> Optional[Dict]:
    for record in all_cpos():
        if record.get("content_hash") == content_hash:
            return record
    return None


def find_by_id(cpo_id: str) -> Optional[Dict]:
    for record in all_cpos():
        if record.get("cpo_id") == cpo_id:
            return record
    return None
