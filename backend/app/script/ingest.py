import os
import sys
from pathlib import Path

current_file = Path(__file__).resolve() # absolute path of current file
project_root = current_file.parent.parent.parent # backend/
sys.path.append(str(project_root)) # add backend to path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.database import SessionLocal
from app.models import Knowledge

def ingest_data():
    # find knowledge_base folder
    base_dir = project_root / "Workshop" / "KnowledgeBase"
    
    print(f"Loading documents from: {base_dir}")
    
    # Check if directory exists
    if not os.path.exists(base_dir):
        print(f"Directory not found: {base_dir}")
        return

    loader = DirectoryLoader(
        base_dir, 
        glob="**/*.txt", 
        loader_cls=TextLoader,
        show_progress=True
    )
    documents = loader.load()
    print(f"Loaded {len(documents)} documents.")

    if not documents:
        print("No documents found. Please check if there are .txt files in the directory.")
        return

    # Split documents into chunks (1000 chars per chunk, 200 chars overlap)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Split into {len(chunks)} chunks.")

    # Store into database
    db = SessionLocal()
    try:
        count = 0
        added_chunks = []
        for i, chunk in enumerate(chunks):
            # source_filename from metadata
            source = chunk.metadata.get("source", "unknown")
            filename = os.path.basename(source)
            
            # create db object
            db_obj = Knowledge(
                filename=filename,
                content=chunk.page_content,
                # vector=... # Todo: compute embedding if needed, or let it be null if allowed
            )
            added_chunks.append(db_obj)
            count += 1
            
        db.add_all(added_chunks)
        db.commit()
        print(f"Successfully saved {count} chunks to database!")
        
    except Exception as e:
        print(f"Error saving to database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    ingest_data()
