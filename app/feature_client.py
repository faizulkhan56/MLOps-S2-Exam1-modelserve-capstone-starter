"""Feast SDK online feature lookup (no direct Redis access)."""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from feast import FeatureStore

from app import metrics

logger = logging.getLogger(__name__)

# Must match feast_repo/feature_definitions.py and training/feature_schema.py
ENTITY_KEY = "cc_num"
FEATURE_VIEW = "fraud_txn_features"
FEAST_NUMERIC_FEATURE_COLS: tuple[str, ...] = (
    "amt",
    "lat",
    "long",
    "city_pop",
    "merch_lat",
    "merch_long",
    "unix_time",
    "zip",
    "gender_code",
)


def _feast_feature_refs() -> list[str]:
    return [f"{FEATURE_VIEW}:{name}" for name in FEAST_NUMERIC_FEATURE_COLS]


def _redis_connection_string_from_env() -> str | None:
    """Build host:port,db=... for Feast YAML from REDIS_URL when set."""
    raw = os.environ.get("REDIS_URL", "").strip()
    if not raw:
        return None
    u = urlparse(raw)
    host = u.hostname
    if not host:
        return None
    port = u.port or 6379
    db = 0
    if u.path and u.path.strip("/").isdigit():
        db = int(u.path.strip("/"))
    return f"{host}:{port},db={db}"


def _resolve_repo_path(base: str) -> str:
    """
    Feast YAML in-repo uses 127.0.0.1 for host-side materialize.
    In Docker, REDIS_URL points at the redis service — copy feast_repo to a temp
    dir and patch connection_string without modifying the git tree.
    """
    base_path = Path(base).resolve()
    yaml_path = base_path / "feature_store.yaml"
    if not yaml_path.is_file():
        return str(base_path)

    conn = _redis_connection_string_from_env()
    if not conn:
        return str(base_path)

    text = yaml_path.read_text(encoding="utf-8")
    if conn in text:
        return str(base_path)

    new_text, n = re.subn(
        r"(?m)^(\s*connection_string:\s*)[\"'][^\"']+[\"']",
        rf'\1"{conn}"',
        text,
        count=1,
    )
    if n != 1:
        logger.warning("Could not patch Feast connection_string; using repo as-is.")
        return str(base_path)

    tmp_root = Path(tempfile.mkdtemp(prefix="feast_repo_"))
    patched = tmp_root / "feast_repo"
    shutil.copytree(base_path, patched)
    (patched / "feature_store.yaml").write_text(new_text, encoding="utf-8")
    return str(patched)


class FeastFeatureClient:
    """Thin wrapper around FeatureStore.get_online_features."""

    def __init__(self, repo_path: str | None = None) -> None:
        raw = repo_path or os.environ.get("FEAST_REPO_PATH", "feast_repo")
        resolved = _resolve_repo_path(raw)
        self._repo_path = resolved
        self._store = FeatureStore(repo_path=resolved)

    def get_features(self, entity_id: int) -> dict[str, float]:
        """
        Return a flat dict of feature column -> float for one cc_num.
        Raises ValueError if online store has no usable row.
        """
        entity_rows = [{ENTITY_KEY: int(entity_id)}]
        resp = self._store.get_online_features(
            features=_feast_feature_refs(),
            entity_rows=entity_rows,
        )
        df = resp.to_df()
        if df.empty:
            metrics.feast_online_store_misses_total.labels(reason="empty").inc()
            raise ValueError("No feature row returned for entity_id")

        row = df.iloc[0]
        # Feast may prefix columns; normalize to bare feature names
        out: dict[str, float] = {}
        for name in FEAST_NUMERIC_FEATURE_COLS:
            val = None
            for key in (name, f"{FEATURE_VIEW}__{name}", f"{FEATURE_VIEW}:{name}"):
                if key in row.index and pd.notna(row[key]):
                    val = row[key]
                    break
            if val is None:
                metrics.feast_online_store_misses_total.labels(reason="missing_field").inc()
                raise ValueError(f"Missing Feast field for {name!r}")
            out[name] = float(val)

        metrics.feast_online_store_hits_total.inc()
        return out
