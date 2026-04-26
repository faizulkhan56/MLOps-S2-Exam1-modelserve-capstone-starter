"""
Load training/features.parquet time range and materialize offline -> Redis (Feast).

Prerequisites:
  - docker compose up -d redis  (and stack as needed)
  - training/features.parquet from training/train.py
  - feast -c feast_repo apply   (from repo root)

Run from repository root:
  python scripts/materialize_features.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from feast import FeatureStore

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.example", override=False)

FEAST_REPO = Path(os.environ.get("FEAST_APPLY_PATH", str(ROOT / "feast_repo"))).resolve()
PARQUET = ROOT / "training" / "features.parquet"

from training.feature_schema import EVENT_TIMESTAMP_COL


def main() -> None:
    if not PARQUET.is_file():
        print(
            f"ERROR: missing {PARQUET}. Run training/train.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    df = pd.read_parquet(PARQUET, columns=[EVENT_TIMESTAMP_COL])
    ts = pd.to_datetime(df[EVENT_TIMESTAMP_COL], utc=True, errors="coerce")
    if ts.isna().all():
        print("ERROR: no valid event timestamps in features parquet.", file=sys.stderr)
        sys.exit(1)
    start = ts.min().to_pydatetime()
    end = ts.max().to_pydatetime()
    if start >= end:
        print("ERROR: need start < end for materialize.", file=sys.stderr)
        sys.exit(1)

    store = FeatureStore(repo_path=str(FEAST_REPO))
    print(
        f"Materializing {start.isoformat()} .. {end.isoformat()} (UTC) into online store",
        file=sys.stderr,
    )
    store.materialize(
        start_date=start,
        end_date=end,
    )
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
