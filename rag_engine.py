"""
CodeSense AI - Core RAG Engine & Codebase Indexer
Provides language-aware chunking, vector embeddings, and LLM orchestration.
"""
import os
import glob
import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


def check_ollama_status(base_url: str = "http://localhost:11434", timeout: float = 1.5) -> Dict[str, Any]:
    """
    Probes the local Ollama daemon to check connectivity and list available models.
    Returns:
        dict: {'running': bool, 'models': List[str], 'error': Optional[str]}
    """
    clean_url = base_url.rstrip("/")
    endpoint = f"{clean_url}/api/tags"
    try:
        req = urllib.request.Request(endpoint, headers={"User-Agent": "CodeSenseAI"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                return {"running": True, "models": models, "error": None}
    except Exception as e:
        return {"running": False, "models": [], "error": str(e)}
    return {"running": False, "models": [], "error": "Unknown status"}


def select_best_fallback_model(installed: List[str], preferred_model: str = "") -> str:
    """
    Intelligently selects the best instruction-tuned coding model from local Ollama for failover.
    Avoids base completion models (like raw starcoder) and pure vision/embedding models.
    """
    if preferred_model and preferred_model in installed:
        return preferred_model

    preferred_candidates = [
        "qwen2.5-coder:1.5b",
        "qwen2.5-coder:7b-instruct-q6_k",
        "codellama:latest",
        "deepseek-r1:1.5b",
        "gemma3:1b",
        "gemma3:4b",
        "deepseek-r1:latest",
        "qwen2.5:1.5b"
    ]
    for cand in preferred_candidates:
        for m in installed:
            if cand == m:
                return m

    for m in installed:
        m_lower = m.lower()
        if ("coder" in m_lower or "instruct" in m_lower or "chat" in m_lower) and not any(k in m_lower for k in ["vision", "vl", "embed", "caption"]):
            return m

    for m in installed:
        m_lower = m.lower()
        if not any(bad in m_lower for bad in ["embed", "vision", "moondream", "vl-", "vl:", "caption"]):
            return m

    return installed[0] if installed else "qwen2.5-coder:1.5b"


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

    @staticmethod
    def _create_ollama_chat(model: str, base_url: str = "http://localhost:11434"):
        """
        Initializes an Ollama chat model using langchain-ollama with fallback.
        """
        clean_url = base_url.rstrip("/")
        try:
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=model,
                base_url=clean_url,
                temperature=0.2
            )
        except ImportError:
            from langchain_community.chat_models import ChatOllama
            return ChatOllama(
                model=model,
                base_url=clean_url,
                temperature=0.2
            )

    def query_codebase(
        self,
        query: str,
        api_key: Optional[str] = None,
        model_name: str = "qwen/qwen3.8-27b",
        provider: str = "Groq",
        top_k: int = 4,
        task_mode: str = "general",
        max_tokens: int = 1200,
        ollama_base_url: str = "http://localhost:11434",
        enable_failover: bool = True
    ) -> Dict[str, Any]:
        """
        Executes similarity search on ChromaDB, compiles context, and runs LLM inference
        across Cloud Turbo (Groq LPU) or Local Privacy (Ollama) with automatic failover.
        """
        # Similarity search
        results = self.vector_store.similarity_search_with_score(query, k=top_k)
        
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

        # Provider routing normalization
        prov_clean = (provider or "groq").strip().lower()
        is_groq = ("groq" in prov_clean) or ("cloud" in prov_clean)
        is_ollama = ("ollama" in prov_clean) or ("local" in prov_clean)

        provider_used = "Groq" if is_groq else "Ollama"
        model_used = model_name
        failover_info = None

        if is_groq:
            if not api_key:
                raise ValueError("Groq API Key is required for Cloud Turbo mode. Please provide it in the sidebar.")
            # Qwen on Groq free tier enforces a strict 1000 OTPM ceiling. Cap Qwen at 600 tokens.
            limit_ceiling = 600 if "qwen" in model_name.lower() else min(max_tokens, 1024)
            llm = ChatGroq(
                groq_api_key=api_key.strip(),
                model_name=model_name,
                temperature=0.2,
                max_tokens=limit_ceiling
            )
        elif is_ollama:
            ollama_status = check_ollama_status(ollama_base_url)
            if not ollama_status["running"]:
                raise ConnectionError(
                    f"Local Ollama daemon is not responding at {ollama_base_url}. "
                    f"Please start Ollama (`ollama serve`) or switch to Groq Cloud Turbo."
                )
            llm = self._create_ollama_chat(model=model_name, base_url=ollama_base_url)
        else:
            raise ValueError(f"Unsupported inference provider: '{provider}'. Supported providers are 'Groq' and 'Ollama'.")

        chain = prompt_template | llm | StrOutputParser()

        try:
            response_text = chain.invoke({
                "system_message": system_message,
                "context": context_str,
                "question": query
            })
        except Exception as e:
            err_msg = str(e).lower()
            # If rate limited on output tokens per minute (OTPM), first attempt token reduction
            if is_groq and ("rate_limit" in err_msg or "429" in err_msg or "otpm" in err_msg or "tokens" in err_msg) and not enable_failover:
                retry_llm = ChatGroq(
                    groq_api_key=api_key.strip(),
                    model_name=model_name,
                    temperature=0.2,
                    max_tokens=500
                )
                retry_chain = prompt_template | retry_llm | StrOutputParser()
                response_text = retry_chain.invoke({
                    "system_message": system_message,
                    "context": context_str,
                    "question": query
                })
            elif is_groq and enable_failover:
                # Automatic Failover to Local Air-Gapped Ollama
                ollama_status = check_ollama_status(ollama_base_url)
                if ollama_status["running"]:
                    installed = ollama_status.get("models", [])
                    fallback_model = select_best_fallback_model(installed, model_name)
                    try:
                        fallback_llm = self._create_ollama_chat(model=fallback_model, base_url=ollama_base_url)
                        fallback_chain = prompt_template | fallback_llm | StrOutputParser()
                        response_text = fallback_chain.invoke({
                            "system_message": system_message,
                            "context": context_str,
                            "question": query
                        })
                        failover_info = {
                            "triggered": True,
                            "reason": f"Groq error ({str(e)[:80]}...). Seamlessly failed over to local private Ollama ({fallback_model}).",
                            "original_provider": "Groq",
                            "fallback_provider": "Ollama",
                            "fallback_model": fallback_model
                        }
                        provider_used = f"Ollama (Auto-Failover from Groq)"
                        model_used = fallback_model
                    except Exception as fallback_err:
                        # If failover also errors, raise informative compound error
                        raise RuntimeError(f"Groq failed ({str(e)}) and Ollama failover failed ({str(fallback_err)})")
                else:
                    # Ollama not running, fallback to token-reduced retry if 429
                    if "rate_limit" in err_msg or "429" in err_msg or "otpm" in err_msg or "tokens" in err_msg:
                        retry_llm = ChatGroq(
                            groq_api_key=api_key.strip(),
                            model_name=model_name,
                            temperature=0.2,
                            max_tokens=500
                        )
                        retry_chain = prompt_template | retry_llm | StrOutputParser()
                        response_text = retry_chain.invoke({
                            "system_message": system_message,
                            "context": context_str,
                            "question": query
                        })
                    else:
                        raise e
            else:
                raise e

        return {
            "answer": response_text,
            "citations": citations,
            "context_used": context_str,
            "provider_used": provider_used,
            "model_used": model_used,
            "failover": failover_info
        }

