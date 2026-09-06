# CodeSense AI — Intelligent Codebase Assistant & AI DevOps Pipeline
**Course:** CSE 4011: Intelligent Developer Tools and AI DevOps Workflows (7th Sem, BMU)

**CodeSense AI** is a developer intelligence platform and AI DevOps pipeline designed to accelerate code comprehension, automate code quality and security reviews, and streamline CI/CD workflows using semantic code retrieval (RAG) and LLM orchestration.

---

## 🎯 Realistic Tech Stack Summary

| Layer | Tool / Technology | Purpose |
| :--- | :--- | :--- |
| **Code Search (Phase 1)** | **Sourcegraph OSS** (Docker) | Self-hosted structural & regex codebase search (`scripts/run_sourcegraph.bat`) |
| **AST Chunking & Orchestration** | **LangChain** (`RecursiveCharacterTextSplitter`) | Language-aware code parsing preserving functions and classes |
| **Vector Database** | **ChromaDB** | In-process persistent dense vector database |
| **Embedding Model** | **sentence-transformers/all-MiniLM-L6-v2** | Free, local, 384-dimensional Hugging Face embeddings (runs on CPU) |
| **LLM Inference** | **Groq LPU** (Cloud) & **Ollama** (Local) | Ultra-fast inference with Qwen, Llama-3, DeepSeek models |
| **Automation & CI/CD** | **GitHub Actions** & **Sweep.dev** | Automated YAML pipeline for linting, pytest, and AI reviews (`.github/workflows/ai-check.yml`) |
| **UI Automation & E2E** | **Selenium WebDriver** | Headless Chrome/Edge automated browser testing (`tests/test_ui_selenium.py`) |
| **Test Generation & Auditing** | **CodiumAI** / `scripts/ai_pr_reviewer.py` | Automated PR diff analysis, bug flagging, and unit test generation |
| **Frontend UI** | **Streamlit** | High-performance DevOps console with dynamic model selection and reasoning traces |
| **Containerization** | **Docker & Podman Compose** | OCI-compliant multi-stage containerization with persistent volumes |

---

## 🏗️ Architecture Overview

```
                  ┌──────────────────────────────────────────────┐
                  │          Developer / Pull Request            │
                  └──────────────┬───────────────────────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
    [ Interactive Web Console ]     [ Automated CI/CD Trigger ]
     Streamlit UI (Port 8501)          GitHub Actions Pipeline
                 │                               │
                 ▼                               ▼
     Dynamic Codebase Ingestion         PR Diff & Flake8 Linting
  (Sample Repo / GitHub Clone / Dir)             │
                 │                               ▼
                 ▼                    ai_pr_reviewer.py
     AST-Aware Code Chunking         Automated Risk & Bug Audit
                 │                               │
                 ▼                               ▼
      ChromaDB Vector Store           Pytest & Selenium Suites
                 │                               │
                 └───────────────┬───────────────┘
                                 ▼
                     Groq LPU Engine (Qwen / Llama 3)
                                 │
                                 ▼
                 Actionable Output & PR Feedback
```

---

## 🚀 Key Capabilities

1. **Semantic Code Retrieval (RAG):**
   - Syntax-aware code chunking via LangChain (`RecursiveCharacterTextSplitter.from_language(Language.PYTHON)`).
   - Local dense embeddings with `sentence-transformers/all-MiniLM-L6-v2`.
   - Vector storage and cosine similarity search using **ChromaDB**.
   - Direct source citations with line numbers and similarity scores.

2. **Dynamic GitHub Repository Cloning & Indexing:**
   - Clone and index any public GitHub repository on demand using shallow Git clones.
   - Instantly switch between built-in sample microservice, custom local directories, and remote GitHub repositories.

3. **Automated DevOps & CI/CD Quality Gates:**
   - **GitHub Actions (`ai-check.yml`):** Automatically triggers on pushes and pull requests.
   - **Flake8 Linting:** Enforces PEP 8 and detects syntax errors.
   - **Pytest Unit Testing:** Automated microservice unit tests (`tests/test_sample_repo.py`).
   - **AI PR Diff Reviewer (`scripts/ai_pr_reviewer.py`):** Automatically inspects git diffs, flags OWASP vulnerabilities, and generates recommended test cases.

4. **Selenium Automated UI Testing:**
   - Headless browser verification using **Selenium WebDriver** (`tests/test_ui_selenium.py`).
   - Automatically validates Streamlit web UI elements, responsiveness, and page layout.

5. **Container-Ready (Docker & Podman):**
   - Production multi-stage `Dockerfile`.
   - OCI-compliant `docker-compose.yml` supporting both `docker compose up` and `podman-compose up`.

---

## 🛠️ Quickstart Guide

### 1. Running Locally (Fastest for Presentations)
```powershell
# 1. Activate virtual environment
.\.venv\Scripts\activate

# 2. Install dependencies (if not already installed)
pip install -r requirements.txt

# 3. Launch the Streamlit application
streamlit run app.py
```
* Access the web UI at: `http://localhost:8501`
* Paste your Groq API key in the left sidebar, choose your model (e.g. `qwen/qwen3.8-27b`), and click **"🚀 Index / Re-Index Codebase"**.

---

### 2. Running Automated Tests

#### A. Run Microservice Unit Tests (Pytest)
```powershell
pytest tests/test_sample_repo.py -v
```

#### B. Run Selenium Automated UI Tests
```powershell
pytest tests/test_ui_selenium.py -v
```

#### C. Run AI PR Diff Reviewer (CLI)
```powershell
python scripts/ai_pr_reviewer.py
```

---

### 3. Running with Containers (Docker or Podman)

#### Using Docker:
```bash
docker compose up --build
```

#### Using Podman (Daemonless / Rootless):
```bash
podman-compose up --build
```
* Both commands run the exact same OCI container definition on port `8501`.

---

### 4. Running Sourcegraph OSS (Phase 1 Code Search)
* **On Windows:**
  ```cmd
  scripts\run_sourcegraph.bat
  ```
* **On Linux / VM:**
  ```bash
  chmod +x scripts/run_sourcegraph.sh
  ./scripts/run_sourcegraph.sh
  ```
* Access Sourcegraph at: `http://localhost:7080`

---

## 📁 Repository Structure
```
CodeSenseAI/
├── .github/
│   └── workflows/
│       └── ai-check.yml            # Automated GitHub Actions CI pipeline
├── sample_repo/                    # Target microservice for live demo
│   ├── api/routes.py               # API endpoints
│   ├── auth/jwt_handler.py         # Auth & token management
│   ├── database/connection.py      # DB connection pooling
│   └── services/deployment_service.py # CI/CD deployment orchestrator
├── scripts/
│   ├── ai_pr_reviewer.py           # Automated AI PR review & diff scanner
│   ├── run_sourcegraph.bat         # Sourcegraph OSS runner (Windows)
│   └── run_sourcegraph.sh          # Sourcegraph OSS runner (Linux/Podman)
├── tests/
│   ├── test_sample_repo.py         # Pytest unit tests for microservice
│   └── test_ui_selenium.py         # Selenium automated UI browser test
├── app.py                          # Streamlit Web Console
├── rag_engine.py                   # LangChain + ChromaDB RAG engine
├── Dockerfile                      # Multi-stage production container
├── docker-compose.yml              # Orchestration configuration
├── PROJECT_CHARTER.md              # Academic Project Charter & A1 Synopsis
├── DEMO_GUIDE.md                   # Presentation guide & viva Q&A
├── requirements.txt                # Python dependencies
└── README.md
```
