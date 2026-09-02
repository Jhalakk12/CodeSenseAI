# CodeSense AI — Intelligent Codebase Assistant & AI DevOps Pipeline

**CodeSense AI** is a developer platform and AI DevOps pipeline designed to accelerate code comprehension, automate code quality and security reviews, and streamline CI/CD workflows using semantic code retrieval (RAG) and LLM orchestration.

---

## 🎯 Architecture Overview

CodeSense AI bridges developer interactive querying with automated DevOps CI checks:

```
                  ┌──────────────────────────────────────────────┐
                  │          Developer / Pull Request            │
                  └──────────────┬───────────────────────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
    [ Interactive Web Console ]     [ Automated CI/CD Trigger ]
          (Streamlit UI)               (GitHub Actions CI)
                 │                               │
                 ▼                               ▼
     Language-Aware AST Chunking       PR Diff & Syntax Linter
                 │                               │
                 ▼                               ▼
      ChromaDB Vector Store          Test Generation & Auditing
                 │                               │
                 └───────────────┬───────────────┘
                                 ▼
                     Groq / Ollama LLM Engine
                                 │
                                 ▼
                 Actionable Output & PR Feedback
```

---

## 🚀 Key Capabilities

1. **Semantic Code Retrieval (RAG):**
   - Syntax-aware code chunking via LangChain (`RecursiveCharacterTextSplitter`).
   - Vector storage and cosine similarity search using **ChromaDB**.
   - Preserves function and class boundaries across Python, TypeScript, and JavaScript.

2. **Automated DevOps & Code Auditing:**
   - **Architecture Explanation:** Synthesizes cross-file dependencies and data flows.
   - **Security Auditing:** Flags unhandled exceptions, token expiration vulnerabilities, and race conditions.
   - **Pytest Test Generation:** Generates unit tests with boundary and mock conditions.

3. **DevOps & Container Ready:**
   - Production multi-stage `Dockerfile`.
   - `docker-compose.yml` for multi-service orchestration.
   - `.github/workflows/ai-check.yml` for automated linting, pytest, and AI reviews.

---

## 🛠️ Quickstart

### Option 1: Running Locally (Fastest for Demos)
1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd CodeSenseAI
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the Streamlit application:
   ```bash
   streamlit run app.py
   ```
5. Enter your Groq API key in the left sidebar and click **Index Codebase**.

---

### Option 2: Running via Docker
1. Ensure Docker Desktop is running.
2. Build and start the container:
   ```bash
   docker compose up --build
   ```
3. Access the web console at: `http://localhost:8501`

---

## 📁 Repository Structure
```
CodeSenseAI/
├── .github/
│   └── workflows/
│       └── ai-check.yml      # Automated GitHub Actions CI pipeline
├── sample_repo/              # Target microservice for live demo
│   ├── api/routes.py         # API endpoints
│   ├── auth/jwt_handler.py   # Auth & token management
│   ├── database/connection.py# DB connection pooling
│   └── services/deployment_service.py # CI/CD deployment orchestrator
├── app.py                    # Streamlit Web Console
├── rag_engine.py             # LangChain + ChromaDB RAG engine
├── Dockerfile                # Multi-stage production container
├── docker-compose.yml        # Orchestration configuration
├── requirements.txt          # Python dependencies
└── README.md
```
