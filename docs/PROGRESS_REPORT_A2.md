# CodeSense AI — Phase 2 Progress Report (A2 Evaluation)
**Course:** CSE 4011: Intelligent Developer Tools and AI DevOps Workflows  
**Institution:** School of Engineering and Technology, BML Munjal University  
**Team Members:** Jhalak Kapila, Khushi Hooda  
**Evaluation Schedule:** Mid-Term Examination (October 2026)  
**Evaluation Component:** A2 — Project Phase Evaluation 2 (Weightage: 30%)  

---

## 1. Executive Summary & Progress vs. Plan (C6)

CodeSense AI has progressed **ahead of schedule**, achieving 100% completion of both Phase 1 (A1: Code Understanding & Navigation) and Phase 2 (A2: Tool Integration, RAG, & CI/CD Workflows) deliverables. All core functional modules, containerization layers, and automated testing pipelines are fully operational.

### Milestone Tracking (Progress vs. Plan)

| Component / Deliverable | Planned Timeline | Current Status | Demonstrated Evidence |
| :--- | :--- | :--- | :--- |
| **Problem Definition & Charter** | Week 1–2 (Aug) | **Completed (100%)** | `PROJECT_CHARTER.md` (7-Service Topology) |
| **Sourcegraph OSS Setup** | Week 3–4 (Sep) | **Completed (100%)** | `scripts/run_sourcegraph.bat` & `.sh` |
| **AST Semantic RAG Engine** | Week 5 (Sep) | **Completed (100%)** | LangChain + ChromaDB in `rag_engine.py` |
| **Groq LPU Acceleration** | Week 5–6 (Sep) | **Completed (100%)** | Sub-second Qwen/Llama inference pipeline |
| **Sweep.dev & CodiumAI Automation**| Week 6–7 (Oct) | **Completed (100%)** | `scripts/ai_pr_reviewer.py` & `.github/workflows/ai-check.yml` |
| **Dual User Interface** | Week 7 (Oct) | **Completed (100%)** | Streamlit Web Console (`app.py`) + Linux CLI (`cli.py`) |
| **E2E & Unit Test Automation** | Week 7–8 (Oct) | **Completed (100%)** | 5/5 tests passing (Pytest + Selenium WebDriver) |
| **OCI Containerization** | Week 8 (Oct) | **Completed (100%)** | Docker & Podman Compose with CPU-optimized PyTorch |

---

## 2. Technical Architecture & Problem Solving (C7 & C8)

### A. RAG-Based Code Q&A Bot (LangChain + ChromaDB + Groq)
* **Code-Aware Chunking:** Instead of naive character chunking, CodeSense AI uses `RecursiveCharacterTextSplitter.from_language(Language.PYTHON)`, ensuring class definitions, decorators, and function bodies remain semantically intact.
* **Vector Embeddings:** Employs `sentence-transformers/all-MiniLM-L6-v2` generating 384-dimensional dense embeddings stored locally in persistent ChromaDB collections.
* **LPU Hardware Acceleration:** Orchestrated through `langchain-groq` utilizing cloud LPUs (`qwen/qwen3.8-27b`) delivering ~300 tokens/sec with strict token ceiling guardrails (600–800 tokens) to guarantee zero HTTP 429 throttling.

### B. CI/CD Automation & Automated PR Reviews (Sweep.dev Workflow)
* **GitHub Actions Pipeline (`.github/workflows/ai-check.yml`):** Automatically triggers on pull requests and pushes to `main`.
* **Automated Code Reviewer (`scripts/ai_pr_reviewer.py`):** Emulates Sweep.dev by extracting `git diff`, inspecting code changes, identifying security regressions, and enforcing automated quality gates.
* **Artifact Upload:** Automatically saves structured audit reports (`pr_review_report.md`) directly into GitHub Actions artifacts.

### C. Test Generation (CodiumAI Methodology)
* **Automated Test Synthesis:** Implements CodiumAI's behavior-driven testing paradigm via `rag_engine.py` (task mode: `testing`) and `cli.py test`.
* **Regression Coverage:** Synthesizes isolated, production-grade `pytest` test cases covering happy paths, boundary constraints, and mocked external dependencies.

### D. Headless Linux CLI Machine Execution
* **Faculty Requirement Addressed:** Built a pure Command Line Interface (`cli.py`) executable inside a Debian Linux Docker container (`codesenseai-codesense-app`) or WSL2 Ubuntu terminal, eliminating Windows GUI/browser dependencies.

---

## 3. Demo-Based Evidence & Working Prototype (C9)

```text
======================================================================
  ____          _      ____                            _     ___ 
 / ___|___   __| | ___/ ___|  ___ _ __  ___  ___      / \   |_ _|
| |   / _ \ / _` |/ _ \___ \ / _ \ '_ \/ __|/ _ \    / _ \   | | 
| |__| (_) | (_| |  __/___) |  __/ | | \__ \  __/   / ___ \  | | 
 \____\___/ \__,_|\___|____/ \___|_| |_|___/\___|  /_/   \_\___|
      Terminal CLI Assistant & AI DevOps Quality Gate
======================================================================
```

### Verified Test Suite Execution (5/5 Passing)
```text
tests/test_sample_repo.py::test_jwt_create_and_verify PASSED             [ 20%]
tests/test_sample_repo.py::test_database_connection_pool PASSED          [ 40%]
tests/test_sample_repo.py::test_deployment_manager_health_and_deploy PASSED [ 60%]
tests/test_ui_selenium.py::test_selenium_webdriver_initialization PASSED [ 80%]
tests/test_ui_selenium.py::test_streamlit_ui_live_render PASSED          [100%]
============================= 5 passed in 34.45s ==============================
```

### OCI Container Verification
* **Image Tag:** `codesenseai-codesense-app:latest` (3.55 GB)
* **Health Check:** `HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health`
* **Cached Build Speed:** `< 5 seconds` via multi-stage layer caching and `.dockerignore`.

---

## 4. Team Contributions & Individual Breakdown (C10)

| Team Member | Role | Key Deliverables & Modules Owned |
| :--- | :--- | :--- |
| **Jhalak Kapila** *(Lead)* | Lead AI & DevOps Architect | • Core LangChain RAG pipeline & AST-aware code parser (`rag_engine.py`)<br>• Local ChromaDB dense vector store & Groq LPU sub-second inference engine<br>• GitHub Actions CI/CD Quality Gate & Automated PR Reviewer (`scripts/ai_pr_reviewer.py`)<br>• Overall 7-service micro-orchestration & Linux CLI containerization (`cli.py`, `Dockerfile`) |
| **Khushi Hooda** | Testing, Automation & QA Lead | • Behavior-driven test generation engine (CodiumAI workflow in `task_mode="testing"`)<br>• Backend microservice unit test suite (`tests/test_sample_repo.py`)<br>• Headless Chrome Selenium WebDriver E2E test suite (`tests/test_ui_selenium.py`)<br>• Flake8 static code analysis, PEP8 enforcement, and quality gate linting rules |

---
**GitHub Repository:** [https://github.com/Jhalakk12/CodeSenseAI](https://github.com/Jhalakk12/CodeSenseAI)
