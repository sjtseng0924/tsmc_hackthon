import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent
sys.path.append(str(project_root))

from app.database import SessionLocal
from app.models import LogEntry, LogFile


LOG_TIME_PATTERNS = [
    "%Y-%m-%dT%H:%M:%SZ",  # 2023-10-26T23:45:00Z
    "%Y-%m-%d %H:%M:%S.%f %Z",  # 2023-10-26 23:45:12.100 UTC
    "%Y-%m-%d %H:%M:%S %Z",  # 2023-10-26 23:45:12 UTC
    "%Y-%m-%dT%H:%M:%S%z",  # 2023-10-26T23:45:00+08:00
    "%Y-%m-%d %H:%M:%S%z",  # 2023-10-26 23:45:12+08:00
]


def parse_timestamp(candidate: str) -> Optional[datetime]:
    s = candidate.strip()
    if s.startswith("[") and "]" in s:
        s = s.lstrip("[")
        s = s.split("]", 1)[0]
    for pattern in LOG_TIME_PATTERNS:
        try:
            return datetime.strptime(s, pattern)
        except ValueError:
            continue
    return None


def iter_lines(file_path: Path) -> Iterable[tuple[int, str]]:
    with file_path.open("r", encoding="utf-8", errors="ignore") as f:
        for idx, line in enumerate(f, start=1):
            yield idx, line.rstrip("\n")


def upsert_logfile(db, filename: str) -> LogFile:
    existing = db.query(LogFile).filter_by(filename=filename).first()
    if existing:
        db.query(LogEntry).filter_by(file_id=existing.id).delete()
        return existing
    lf = LogFile(filename=filename)
    db.add(lf)
    db.flush()
    return lf


def ingest_file(db, file_path: Path) -> None:
    filename = file_path.name
    logfile = upsert_logfile(db, filename)

    entries = []
    for line_no, line in iter_lines(file_path):
        ts = None
        if line:
            parts = line.split()
            # try single token, then first 2, then first 3 tokens to cover postgres style
            candidates = [" ".join(parts[:k]) for k in (1, 2, 3) if len(parts) >= k]
            for cand in candidates:
                ts = parse_timestamp(cand)
                if ts:
                    break
        entries.append(
            LogEntry(
                file=logfile,
                line_number=line_no,
                timestep=ts,
                raw_content=line,
            )
        )
    db.add_all(entries)
    db.commit()
    print(f"Saved {len(entries)} lines from {filename}")


def ingest_paths(paths: list[Path]) -> None:
    db = SessionLocal()
    try:
        deleted_entries = db.query(LogEntry).delete()
        deleted_files = db.query(LogFile).delete()
        if deleted_entries or deleted_files:
            print(f"Cleared {deleted_entries} entries and {deleted_files} files")
        for p in paths:
            if not p.exists():
                print(f"[skip] {p} not found")
                continue
            ingest_file(db, p)
    finally:
        db.close()


def default_logs() -> list[Path]:
    base = project_root / "Workshop" / "ScenarioLogFolder"
    return [
        base / "firewall.log",
        base / "postgresql.log",
        base / "tNote_app_server_v1.log",
    ]


def parse_args():
    parser = argparse.ArgumentParser(description="Ingest log files into database")
    parser.add_argument(
        "--files",
        nargs="*",
        default=None,
        help="Specific log files to ingest (default: known files in ScenarioLogFolder)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    targets = [Path(p).resolve() for p in args.files] if args.files else default_logs()
    ingest_paths(targets)
