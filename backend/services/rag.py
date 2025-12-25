import os
import logging
from typing import List, Optional
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

class RAGService:
    def __init__(self):
        self.persist_directory = "backend/data/chroma_db"
        self.embedding_function = OpenAIEmbeddings()
        # Initialize vector store
        self.vector_store = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embedding_function
        )
        # Ensure persist directory exists
        os.makedirs(self.persist_directory, exist_ok=True)

    def ingest_file(self, file_path: str, file_type: str = "text") -> int:
        """
        Ingests a file into the vector store.
        Returns the number of chunks added.
        """
        try:
            if file_type == "pdf":
                loader = PyPDFLoader(file_path)
            else:
                loader = TextLoader(file_path)
            
            docs = loader.load()
            
            # Split text into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                add_start_index=True,
            )
            splits = text_splitter.split_documents(docs)
            
            # Add to vector store
            self.vector_store.add_documents(documents=splits)
            logger.info(f"Ingested {len(splits)} chunks from {file_path}")
            return len(splits)
            
        except Exception as e:
            logger.error(f"Error ingesting file {file_path}: {e}")
            raise

    def query(self, query_text: str, k: int = 4) -> List[Document]:
        """
        Retrieves relevant documents for a given query.
        """
        results = self.vector_store.similarity_search(query_text, k=k)
        return results

    def clear(self):
        """Clears the vector store."""
        self.vector_store.delete_collection()
        self.vector_store = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embedding_function
        )

rag_service = RAGService()
