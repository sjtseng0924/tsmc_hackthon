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
from app.services.case_parser import parse_case_text
from app.models import Knowledge
from app.services.rag import get_embedding


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


def ingest_dirs(dirs: list, glob_pattern: str) -> None:
    all_docs = []
    for d in dirs:
        docs = load_documents(Path(d).resolve(), glob_pattern=glob_pattern)
        all_docs.extend(docs)
    
    if not all_docs:
        print("No documents loaded. Check directories or glob pattern.")
        return

    print(f"Found {len(all_docs)} documents. Parsing and saving...")
    
    from app.services.cases_service import save_case_report_structured

    success_count = 0
    fail_count = 0
    
    for doc in all_docs:
        try:
            filename = os.path.basename(doc.metadata.get("source", ""))
            print(f"Processing {filename}...")
            
            # Parse the text into structured dictionary
            parsed_data = parse_case_text(doc.page_content)
            
            # Ensure filename matches if not present in text (fallback)
            if not parsed_data.get("filename"):
                parsed_data["filename"] = filename

            # Save via service (handles validation, vector embedding, etc.)
            saved_id = save_case_report_structured(parsed_data)
            print(f"  -> Saved as {saved_id}")
            success_count += 1
            
        except Exception as e:
            print(f"  -> Failed to process {filename}: {e}")
            fail_count += 1

    print(f"\nIngestion Complete. Success: {success_count}, Failed: {fail_count}")


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
