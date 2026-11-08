"""Download the official NHAMCS 2022 ED files and verify them by SHA-256.

Usage (from any directory)::

    python scripts/download_nhamcs.py                 # download missing files
    python scripts/download_nhamcs.py --verify-only   # only check local files
    python scripts/download_nhamcs.py --force         # download again

Files are stored in ``data/raw/`` (not versioned). A ``download_manifest.json``
records URL, access date, size and checksum of each file. A checksum mismatch
means the file is not the one this project was calibrated with; the script
stops instead of processing it.

By downloading these files you accept the NCHS data use restrictions printed in
https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHAMCS/readme2022.txt
(statistical use only, no attempt to identify persons or establishments).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ed_simulation.calibration import NHAMCS_2022_FILES, SourceFile  # noqa: E402

DEFAULT_RAW_DIR = ROOT / "data" / "raw"
MANIFEST_NAME = "download_manifest.json"
USER_AGENT = "ed-resource-optimizer/0.1 (academic project; python-urllib)"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(source: SourceFile, destination: Path) -> None:
    request = urllib.request.Request(source.url, headers={"User-Agent": USER_AGENT})
    temporary = destination.with_suffix(destination.suffix + ".part")
    with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as out:
        while chunk := response.read(1 << 20):
            out.write(chunk)
    temporary.replace(destination)


def verify(source: SourceFile, path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"falta {path}")
    size = path.stat().st_size
    checksum = sha256_of(path)
    if checksum != source.sha256 or size != source.size_bytes:
        raise ValueError(
            f"{path.name} no coincide con el archivo oficial esperado "
            f"(sha256 {checksum}, {size} bytes). Elimínelo y vuelva a descargarlo; "
            "si CDC publicó una nueva versión, actualice NHAMCS_2022_FILES y "
            "documente el cambio antes de calibrar."
        )
    return {"size_bytes": size, "sha256": checksum}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--skip-documentation",
        action="store_true",
        help="No descarga el PDF de documentación (no lo requiere el pipeline).",
    )
    args = parser.parse_args(argv)
    args.raw_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = args.raw_dir / MANIFEST_NAME
    previous = {}
    if manifest_path.exists():
        previous = {
            entry["filename"]: entry
            for entry in json.loads(manifest_path.read_text(encoding="utf-8"))["files"]
        }

    entries = []
    for source in NHAMCS_2022_FILES:
        if args.skip_documentation and not source.required:
            continue
        path = args.raw_dir / source.filename
        accessed = previous.get(source.filename, {}).get("accessed")
        if not args.verify_only and (args.force or not path.exists()):
            print(f"Descargando {source.url}")
            download(source, path)
            accessed = date.today().isoformat()
        details = verify(source, path)
        if accessed is None:
            accessed = date.fromtimestamp(path.stat().st_mtime).isoformat()
        print(f"OK {source.filename} sha256={details['sha256'][:12]}…")
        entries.append(
            {
                "key": source.key,
                "filename": source.filename,
                "url": source.url,
                "description": source.description,
                "accessed": accessed,
                **details,
            }
        )

    manifest_path.write_text(
        json.dumps({"files": entries}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Manifiesto: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
