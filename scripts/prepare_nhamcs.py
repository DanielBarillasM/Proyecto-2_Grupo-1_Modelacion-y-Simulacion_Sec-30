"""Build the processed NHAMCS 2022 calibration tables used by the model.

Usage::

    python scripts/download_nhamcs.py      # once, obtains and verifies raw files
    python scripts/prepare_nhamcs.py       # writes data/processed/nhamcs_2022_*

The transformation is deterministic: running it twice on the same verified raw
files produces byte-identical outputs. See ``docs/05_data_calibration.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from download_nhamcs import MANIFEST_NAME, verify  # noqa: E402
from ed_simulation.calibration import (  # noqa: E402
    NHAMCS_2022_FILES,
    build_calibration_tables,
    build_metadata,
    read_public_use_file,
    validate_public_use_file,
    write_processed_outputs,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "processed")
    args = parser.parse_args(argv)

    sources = {source.key: source for source in NHAMCS_2022_FILES}
    manifest_path = args.raw_dir / MANIFEST_NAME
    accessed = {}
    if manifest_path.exists():
        accessed = {
            entry["filename"]: entry.get("accessed")
            for entry in json.loads(manifest_path.read_text(encoding="utf-8"))["files"]
        }

    source_records = []
    for key in ("data", "dictionary"):
        source = sources[key]
        details = verify(source, args.raw_dir / source.filename)
        source_records.append(
            {
                "filename": source.filename,
                "url": source.url,
                "accessed": accessed.get(source.filename),
                **details,
            }
        )

    frame = read_public_use_file(
        args.raw_dir / sources["data"].filename,
        args.raw_dir / sources["dictionary"].filename,
    )
    checks = validate_public_use_file(frame)
    tables = build_calibration_tables(frame)
    metadata = build_metadata(frame, checks, source_records)
    for path in write_processed_outputs(tables, metadata, args.output_dir):
        print(f"Escrito {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
