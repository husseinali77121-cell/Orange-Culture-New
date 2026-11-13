# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Small pure helpers."""
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
import hashlib




def make_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()

def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default

def get_route_label(item: Dict[str, Any]) -> str:
    return "🟢 Oral preferred / PO-friendly" if item.get("high_po") else "💉 IV/IM only"

def uniq_keep_order(items: List[str]) -> List[str]:
    seen:   set       = set()
    result: List[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            result.append(x)
    return result

def best_default_index(options: List[str], preferred: Optional[str]) -> int:
    if preferred and preferred in options:
        return options.index(preferred)
    return 0
