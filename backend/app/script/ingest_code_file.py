import argparse
import sys
from pathlib import Path

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent
sys.path.append(str(project_root))

from app.database import SessionLocal
from app.models import Code


def iter_code_files(base: Path, patterns: list[str]) -> list[Path]:
    files: list[Path] = []
    for pat in patterns:
        files.extend(base.glob(pat))
    # remove duplicates while preserving order
    seen = set()
    unique: list[Path] = []
    for f in files:
        if f not in seen and f.is_file():
            seen.add(f)
            unique.append(f)
    return unique


def upsert_code(db, path: Path) -> None:
    content = path.read_text(encoding="utf-8", errors="ignore")
    existing = db.query(Code).filter_by(filename=path.name).first()
    if existing:
        existing.content = content
        existing.vector = None
        return
    db.add(Code(filename=path.name, content=content, vector=None))


def ingest(paths: list[Path]) -> None:
    db = SessionLocal()
    try:
        for p in paths:
            if not p.exists():
                print(f"[skip] {p} not found")
                continue
            upsert_code(db, p)
            print(f"saved {p.name}")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def default_dir() -> Path:
    return project_root / "Workshop" / "CodeFolder"


def parse_args():
    parser = argparse.ArgumentParser(description="Ingest code files into database")
    parser.add_argument(
        "--dir",
        default=None,
        help="Directory to scan (default: Workshop/CodeFolder)",
    )
    parser.add_argument(
        "--patterns",
        nargs="*",
        default=["*.sh", "*.py", "*.sql", "*.txt"],
        help="Glob patterns to include (default: *.sh *.py *.sql *.txt)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    base = Path(args.dir).resolve() if args.dir else default_dir()
    targets = iter_code_files(base, args.patterns)
    if not targets:
        print(f"no files found in {base}")
    else:
        ingest(targets)
