import argparse
from pathlib import Path

from app.db import SessionLocal
from app.services.master_load import load_masters


def main() -> None:
    parser = argparse.ArgumentParser(description="Idempotently load TALCO tannery masters")
    parser.add_argument("fixture_dir", type=Path)
    args = parser.parse_args()
    with SessionLocal() as session:
        result = load_masters(session, args.fixture_dir)
    print(f"Loaded {result['tanneries']} tanneries; GST mismatches: {result['gst_mismatches']}")


if __name__ == "__main__":
    main()

