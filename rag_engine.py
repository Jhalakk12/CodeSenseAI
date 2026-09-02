"""
CodeSense AI - Core RAG Engine & Codebase Indexer
Provides language-aware chunking, vector embeddings, and LLM orchestration.
"""
import os
import glob
from typing import List, Dict, Any, Optional
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Mapping extensions to LangChain languages
EXT_TO_LANG = {
    ".py": Language.PYTHON,
    ".js": Language.JS,
    ".ts": Language.TS,
    ".html": Language.HTML,
    ".md": Language.MARKDOWN,
}

SUPPORTED_EXTS = [".py", ".js", ".ts", ".json", ".yaml", ".yml", ".md", ".sql", ".sh"]

class CodeSenseEngine:
    def __init__(self, persist_dir: str = "./chroma_db", embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.persist_dir = persist_dir
        self.embedding_model_name = embedding_model_name
        self._embeddings = None
        self._vector_store = None

    @property
    def embeddings(self):
        if self._embeddings is None:
            self._embeddings = HuggingFaceEmbeddings(
                model_name=self.embedding_model_name,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True}
            )
        return self._embeddings

    @property
    def vector_store(self):
        if self._vector_store is None:
            self._vector_store = Chroma(
                persist_directory=self.persist_dir,
                embedding_function=self.embeddings,
                collection_name="codesense_index"
            )
        return self._vector_store

    def index_codebase(self, target_dir: str) -> Dict[str, Any]:
        """
        Scans, extracts, and indexes code files using code-aware AST/recursive chunking.
        """
        if not os.path.exists(target_dir):
            raise ValueError(f"Directory {target_dir} does not exist.")

        all_files = []
        for root, _, files in os.walk(target_dir):
            # Skip hidden or environment directories
            if any(part.startswith(".") or part in ["node_modules", "venv", "__pycache__"] for part in root.split(os.sep)):
                continue
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in SUPPORTED_EXTS:
                    all_files.append(os.path.join(root, f))

        if not all_files:
            return {"status": "warning", "message": "No supported code files found.", "indexed_files": 0, "total_chunks": 0}

        docs = []
        total_chunks = 0

        for file_path in all_files:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read()
                
                if not content.strip():
                    continue

                ext = os.path.splitext(file_path)[1].lower()
                rel_path = os.path.relpath(file_path, target_dir)

                # Use language-aware splitter if applicable
                if ext in EXT_TO_LANG:
                    splitter = RecursiveCharacterTextSplitter.from_language(
                        language=EXT_TO_LANG[ext],
                        chunk_size=750,
                        chunk_overlap=120
                    )
                else:
                    splitter = RecursiveCharacterTextSplitter(
                        chunk_size=750,
                        chunk_overlap=120
                    )

                chunks = splitter.split_text(content)
                for i, chunk in enumerate(chunks):
                    docs.append({
                        "text": chunk,
                        "metadata": {
                            "source": rel_path,
                            "file_path": file_path,
                            "chunk_id": i,
                            "extension": ext
                        }
                    })
                total_chunks += len(chunks)
            except Exception as e:
                print(f"Error processing {file_path}: {e}")

        # Clear existing collection and add new documents
        texts = [d["text"] for d in docs]
        metadatas = [d["metadata"] for d in docs]

        # Reset vector store
        try:
            self.vector_store.delete_collection()
        except Exception:
            pass

        self._vector_store = Chroma.from_texts(
            texts=texts,
            embedding=self.embeddings,
            metadatas=metadatas,
            persist_directory=self.persist_dir,
            collection_name="codesense_index"
        )

        return {
            "status": "success",
            "indexed_files": len(all_files),
            "total_chunks": total_chunks,
            "files": [os.path.relpath(p, target_dir) for p in all_files]
        }

    def query_codebase(
        self,
        query: str,
        api_key: str,
        model_name: str = "llama-3.3-70b-versatile",
        provider: str = "Groq",
        top_k: int = 4,
        task_mode: str = "general"
    ) -> Dict[str, Any]:
        """
        Executes similarity search on ChromaDB, compiles context, and runs LLM inference.
        """
        # Similarity search
        results = self.vector_store.similarity_search_with_relevance_scores(query, k=top_k)
        
        context_blocks = []
        citations = []
        for doc, score in results:
            source = doc.metadata.get("source", "Unknown file")
            chunk_id = doc.metadata.get("chunk_id", 0)
            citations.append({
                "source": source,
                "score": round(float(score), 3) if score is not None else 0.0,
                "snippet": doc.page_content[:250] + ("..." if len(doc.page_content) > 250 else "")
            })
            context_blocks.append(f"--- File: {source} (Chunk {chunk_id}) ---\n{doc.page_content}")

        context_str = "\n\n".join(context_blocks)

        # Task-specific system prompt injection
        system_prompts = {
            "general": (
                "You are CodeSense AI, an expert AI DevOps and software engineering assistant. "
                "Analyze the provided codebase context and answer the developer's question accurately. "
                "Always cite the relevant file names and explain the underlying architecture clearly."
            ),
            "security": (
                "You are CodeSense AI Security Auditor. Examine the provided code chunks for security flaws, "
                "edge-case vulnerabilities (e.g. unhandled exceptions, race conditions, expired tokens, auth bypasses), "
                "and suggest hardened refactored code."
            ),
            "testing": (
                "You are CodeSense AI Test Engineering Assistant. Based on the provided code chunks, generate "
                "comprehensive, production-grade pytest test cases. Include happy-path, boundary conditions, "
                "and mock-based tests for external dependencies."
            )
        }

        system_message = system_prompts.get(task_mode, system_prompts["general"])

        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "{system_message}\n\nCodebase Context:\n{context}"),
            ("human", "{question}")
        ])

        # Provider initialization
        if provider == "Groq":
            if not api_key:
                raise ValueError("Groq API Key is required. Please provide it in the sidebar.")
            llm = ChatGroq(
                groq_api_key=api_key,
                model_name=model_name,
                temperature=0.2,
                max_tokens=2048
            )
        else:
            # Fallback for Ollama
            from langchain_community.chat_models import ChatOllama
            llm = ChatOllama(
                model=model_name,
                temperature=0.2
            )

        chain = prompt_template | llm | StrOutputParser()

        response_text = chain.invoke({
            "system_message": system_message,
            "context": context_str,
            "question": query
        })

        return {
            "answer": response_text,
            "citations": citations,
            "context_used": context_str
        }
