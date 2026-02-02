import argparse
import os
import sys
from pathlib import Path

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent
sys.path.append(str(project_root))

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.database import SessionLocal
from app.models import Knowledge
from app.rag import get_embedding


def load_documents(base_dir: Path, glob_pattern: str) -> list:
    if not base_dir.exists():
        print(f"[skip] directory not found: {base_dir}")
        return []
    loader = DirectoryLoader(
        str(base_dir),
        glob=glob_pattern,
        loader_cls=TextLoader,
        show_progress=True,
    )
    docs = loader.load()
    print(f"Loaded {len(docs)} documents from {base_dir}")
    return docs


def split_documents(documents: list) -> list:
    if not documents:
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    return splitter.split_documents(documents)


def save_chunks(chunks: list) -> None:
    if not chunks:
        print("No chunks to save")
        return
    db = SessionLocal()
    try:
        # clear previous data before inserting
        deleted = db.query(Knowledge).delete()
        if deleted:
            print(f"Cleared {deleted} existing rows from knowledge")
        added = []
        for chunk in chunks:
            source = chunk.metadata.get("source", "unknown")
            filename = os.path.basename(source)
            vector = get_embedding(chunk.page_content)
            added.append(
                Knowledge(
                    filename=filename,
                    content=chunk.page_content,
                    vector=vector,
                )
            )
        db.add_all(added)
        db.commit()
        print(f"Saved {len(added)} chunks to database")
    except Exception as exc:
        print(f"Error saving to database: {exc}")
        db.rollback()
    finally:
        db.close()


def ingest_dirs(dirs: list, glob_pattern: str) -> None:
    all_docs = []
    for d in dirs:
        docs = load_documents(Path(d).resolve(), glob_pattern=glob_pattern)
        all_docs.extend(docs)
    if not all_docs:
        print("No documents loaded. Check directories or glob pattern.")
        return
    chunks = split_documents(all_docs)
    print(f"Total chunks: {len(chunks)}")
    save_chunks(chunks)


def default_dirs() -> list:
    return [project_root / "Workshop" / "KnowledgeBase"]


def parse_args():
    parser = argparse.ArgumentParser(description="Ingest knowledge base text files")
    parser.add_argument(
        "--dirs",
        nargs="*",
        default=None,
        help="Directories to ingest (default: Workshop/KnowledgeBase)",
    )
    parser.add_argument(
        "--glob",
        default="**/*.txt",
        help="Glob pattern for files (default: **/*.txt)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    target_dirs = args.dirs if args.dirs else default_dirs()
    ingest_dirs(target_dirs, glob_pattern=args.glob)
