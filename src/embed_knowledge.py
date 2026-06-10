"""
Phase 2: Embedding generator & Vector DB uploader.
Reads the knowledge.md rules, chunks them, generates embeddings,
and stores them in a local Qdrant Vector database.
Supports both Google Gemini API and a local fallback Mock Embedding mode.
"""

import os
import re
import hashlib
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("embed_knowledge")

KNOWLEDGE_FILE = "rag/knowledge.md"
QDRANT_PATH = "data/qdrant_db"
COLLECTION_NAME = "company_rules"
VECTOR_DIMENSION = 768  # Standard dimension for Google text-embedding-004

def get_qdrant_client() -> QdrantClient:
    """
    Returns a QdrantClient.
    First tries to connect to a running Qdrant Docker instance (on localhost:6333).
    Falls back to local file storage if Docker is unavailable.
    """
    import socket
    docker_host = os.getenv("QDRANT_HOST", "localhost")
    docker_port = int(os.getenv("QDRANT_PORT", "6333"))
    
    # Simple check if port is open
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect((docker_host, docker_port))
        s.close()
        logger.info(f"Qdrant Docker service detected at {docker_host}:{docker_port}. Connecting to Docker Client.")
        return QdrantClient(url=f"http://{docker_host}:{docker_port}")
    except Exception:
        logger.info(f"Qdrant Docker service not active at {docker_host}:{docker_port}. Falling back to local file storage client ({QDRANT_PATH}).")
        return QdrantClient(path=QDRANT_PATH)

def get_mock_embedding(text: str, dimensions: int = VECTOR_DIMENSION) -> List[float]:
    """
    Generates a stable, normalized mock embedding vector for a given text.
    Ensures that identical text always yields the same vector.
    """
    # Use SHA-256 hash of the text to seed numpy's random generator
    hasher = hashlib.sha256(text.encode('utf-8'))
    seed = int(hasher.hexdigest()[:8], 16)  # Use first 8 hex characters as integer seed
    
    # We generate a deterministic random vector based on the seed
    import numpy as np
    rng = np.random.default_rng(seed)
    vector = rng.standard_normal(dimensions)
    
    # Normalize to unit length
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector.tolist()

def get_embedding(text: str) -> List[float]:
    """
    Generates an embedding vector using Gemini API if key is present,
    otherwise falls back to the deterministic local mock embedding.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.info("GEMINI_API_KEY not found. Using local deterministic Mock Embedding.")
        return get_mock_embedding(text)
        
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        # Call Gemini embedding service
        response = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_document"
        )
        return response['embedding']
    except Exception as e:
        logger.warning(f"Error generating embedding via Gemini API: {e}. Falling back to Mock Embedding.")
        return get_mock_embedding(text)

def chunk_markdown_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Reads a markdown file and splits it into logical sections/chunks based on headers.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Knowledge file not found at {file_path}")
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Split content by markdown level 2 headers (##)
    sections = re.split(r'\n(##\s+)', content)
    
    chunks = []
    # The first element is the document header/metadata
    doc_header = sections[0].strip()
    
    i = 1
    while i < len(sections):
        header_marker = sections[i]  # "## "
        section_content = sections[i+1]
        
        # Reconstruct the section text
        full_text = header_marker + section_content.strip()
        
        # Clean title
        title_match = re.match(r'##\s+(.+)', full_text)
        title = title_match.group(1).strip() if title_match else "General Rules"
        
        chunks.append({
            "title": title,
            "content": full_text,
            "source": file_path
        })
        i += 2
        
    # If no headers found, return the entire document as a single chunk
    if not chunks and content.strip():
        chunks.append({
            "title": "General Operations Standard",
            "content": content.strip(),
            "source": file_path
        })
        
    logger.info(f"Chunked knowledge document into {len(chunks)} sections.")
    return chunks

def build_vector_db():
    """Reads rules, generates embeddings, and indexes them in Qdrant Local/Docker."""
    client = get_qdrant_client()
    
    # 1. Parse and chunk rules
    chunks = chunk_markdown_file(KNOWLEDGE_FILE)
    if not chunks:
        logger.error("No rules chunks to index.")
        return
        
    # 2. Re-create Qdrant collection
    logger.info(f"Recreating collection '{COLLECTION_NAME}'...")
    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=VECTOR_DIMENSION,
            distance=models.Distance.COSINE
        )
    )
    
    # 3. Generate embeddings and upload
    points = []
    for idx, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {idx + 1}/{len(chunks)}: {chunk['title']}")
        vector = get_embedding(chunk["content"])
        
        points.append(
            models.PointStruct(
                id=idx,
                vector=vector,
                payload={
                    "title": chunk["title"],
                    "content": chunk["content"],
                    "source": chunk["source"]
                }
            )
        )
        
    client.upsert(
        collection_name=COLLECTION_NAME,
        wait=True,
        points=points
    )
    logger.info(f"Successfully uploaded {len(points)} knowledge vectors to Qdrant local storage.")

if __name__ == "__main__":
    build_vector_db()
