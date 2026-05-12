"""自实现本地向量库（hash 向量 + jsonl 持久化）。

TODO: 后续可替换为正式的向量数据库（Chroma/FAISS/Pinecone）。
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List

from core.config import get_config

from web_console.utils import _safe_name


def _local_store_dir(project_dir: str) -> Path:
    _ = project_dir
    cfg = get_config()
    return Path(cfg.data_dir_abs) / "local_store"


def _ip_asset_dir(project_dir: str, novel_id: str) -> Path:
    return _local_store_dir(project_dir) / "ip_assets" / _safe_name(novel_id)


def _vector_store_file(project_dir: str) -> Path:
    return _local_store_dir(project_dir) / "vector_store.jsonl"


def _hash_vector(text: str, dim: int = 64) -> List[float]:
    tokens = re.findall(r"[一-龥]|[A-Za-z0-9_]+", text.lower())
    if not tokens:
        return [0.0] * dim

    vec = [0.0] * dim
    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:8], "big") % dim
        vec[idx] += 1.0

    norm = sum(v * v for v in vec) ** 0.5
    if norm == 0:
        return vec
    return [round(v / norm, 6) for v in vec]


def _upsert_vector_docs(project_dir: str, docs: List[dict]) -> int:
    store_file = _vector_store_file(project_dir)
    store_file.parent.mkdir(parents=True, exist_ok=True)

    records: Dict[str, dict] = {}
    if store_file.exists():
        for line in store_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            rec_id = str(rec.get("id") or "")
            if rec_id:
                records[rec_id] = rec

    upserted = 0
    for doc in docs:
        rec_id = str(doc.get("id") or "")
        if not rec_id:
            continue
        records[rec_id] = doc
        upserted += 1

    with open(store_file, "w", encoding="utf-8") as fout:
        for rec in records.values():
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return upserted
