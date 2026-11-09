# 🎯 CodeSense AI — Faculty Demo Guide & Viva Preparation (CSE 4011)

**Course:** CSE 4011: Intelligent Developer Tools and AI DevOps Workflows  
**Faculty:** Dr. Kiran Khatter & Mr. Naveen Singh (School of Engineering and Technology, BMU)

---

## ⏱️ 3-Minute Live Demo Walkthrough

### 1. The Opening (30 Seconds)
> *"Good morning/afternoon, Sir. For our CSE 4011 project, we are building **CodeSense AI** — an AI-powered codebase assistant and DevOps automation pipeline.*
> 
> *Our system decomposes into a **7-service micro-orchestration topology** combining AST-aware semantic code retrieval (RAG) with automated CI/CD quality gates, live multi-mode repository ingestion, input/output guardrails, Selenium UI testing, and OCI containerization with Docker and Podman."*

---

## 🧪 2. In-Depth Live Testing & Demonstration Sequence

### Step 1: Launch the System (Choose Mode: Web UI or Pure CLI)

#### Option A: Interactive Web Console (Streamlit)
```powershell
.\.venv\Scripts\streamlit run app.py
```
Open `http://localhost:8501` in your browser.

#### Option B: Pure Command Line Interface (CLI Machine / Linux)
If the faculty requests demonstration strictly on a **CLI / terminal machine without a browser**:
```bash
# 1. Direct interactive CLI shell
python cli.py

# 2. Or run individual subcommands:
python cli.py index ./sample_repo
python cli.py query "Explain the JWT authentication architecture"
python cli.py security "Check for SQL vulnerabilities or unhandled exceptions"
python cli.py test "Generate pytest unit tests for database connection pool"
python cli.py review

# 3. For pure Linux CLI (WSL Ubuntu):
wsl
cd /mnt/c/Users/jhala/OneDrive/Projects/CodeSenseAI
python3 cli.py
```
*(Runs 100% in the terminal with full ASCII banner, vector search, Groq LPU streaming, and source citations!)*

---

### Step 2: Ingestion Testing (Demonstrate All 4 Input Modes)
In the left sidebar under **📁 Repository Indexing**, show the faculty that CodeSense AI dynamically ingests codebases from any source:

1. **Mode 1: Built-in Microservice (`sample_repo`)**
   * Select `Built-in Sample Microservice (sample_repo)` → Click **"🚀 Index Codebase"**.
   * Shows: *Files Indexed: 4, Code Chunks: 16, ChromaDB: Active*.
2. **Mode 2: Live GitHub URL Cloner**
   * Select `Clone from GitHub URL` → URL: `https://github.com/pallets/flask`.
   * Click **"🚀 Index Codebase"** → Clones shallow Git repo and indexes live.
3. **Mode 3: Upload Codebase (.ZIP Archive)**
   * Select `Upload Codebase (.ZIP Archive)` → Drag-and-drop any code `.zip` archive.
4. **Mode 4: Custom Local Directory**
   * Select `Custom Local Directory` → Path: e.g. `D:\Downloads\polycode-master`.
   * Indexes 60+ files and 600+ chunks in seconds.

> **Key Talking Point for Faculty:**
> *"Sir, we don't just split text by raw characters or line counts. We use LangChain's code-aware AST splitter (`RecursiveCharacterTextSplitter.from_language`) to ensure Python class and function definitions stay semantically intact inside our 384-dimensional dense vectors."*

---

### Step 3: Run the 6 In-Depth Query Test Scenarios

Demonstrate the distinct types of intelligent developer queries supported by the engine:

#### 🔹 Test Scenario A: Architectural Synthesis & Cross-File Dataflow
* **Prompt to Run:** Click **"🏗️ Explain Architecture"** (or type: *"Explain the overall architecture and main components of this codebase."*)
* **What to Show the Faculty:**
  * The LLM synthesizes dependencies across `routes.py`, `jwt_handler.py`, `connection.py`, and `deployment_service.py`.
  * Open the collapsible **"🔍 Source Citations"** box below the response: Show the exact retrieved file names, chunk IDs, and cosine relevance scores (e.g. `Relevance: 1.134`).

#### 🔹 Test Scenario B: Security Auditing & Vulnerability Remediation
* **Prompt to Run:** Click **"🛡️ Security & Bug Audit"** (or type: *"Audit the codebase for security edge-cases, unhandled exceptions, and authentication vulnerabilities."*)
* **What to Show the Faculty:**
  * It detects **Hardcoded Credentials** (`devops_admin / secure_pass_123`) in `api/routes.py`.
  * It detects **Hardcoded JWT Secret Keys** in `auth/jwt_handler.py`.
  * It flags the lack of password hashing and **timing attack vulnerabilities**, outputting a production-hardened refactor using `secrets.compare_digest` and dependency-injected `UserService`.

#### 🔹 Test Scenario C: Automated Pytest Unit Test Generation
* **Prompt to Run:** Click **"🧪 Generate Unit Tests"** (or type: *"Generate comprehensive pytest test cases for the core functions in this repository."*)
* **What to Show the Faculty:**
  * It generates complete, ready-to-run `pytest` test suites.
  * Shows framework-specific test logic: mocking token verification with `@patch("auth.jwt_handler.jwt.decode")`, testing valid tokens, expired tokens (`ExpiredSignatureError`), invalid signatures, and `None` inputs.

#### 🔹 Test Scenario D: Deep Control Flow & Business Logic Navigation
* **Prompt to Run:** Type in the chat box:
  ```text
  How does the emergency rollback logic work in the deployment service?
  ```
* **What to Show the Faculty:**
  * The model pinpoints the exact method `emergency_rollback` in `deployment_service.py`.
  * Explains how health check failure triggers automatic rollback to previous stable commit without manual intervention.

#### 🔹 Test Scenario E: Zero-Hallucination & Scope Control (Negative Test Case)
* **Prompt to Run:** Type in the chat box:
  ```text
  How do I process payments using Stripe in this codebase?
  ```
* **What to Show the Faculty:**
  * **Strict Groundedness:** The assistant truthfully states that Stripe or payment logic does not exist in the indexed codebase.
  * **Scope Control:** It refuses to invent fake APIs or hallucinate code, satisfying the course's Responsible AI and Guardrailing criteria.

#### 🔹 Test Scenario F: General Technical Explanations vs Code Context
* **Prompt to Run:** Type in the chat box:
  ```text
  What is DevOps and how does it relate to this codebase?
  ```
* **What to Show the Faculty:**
  * Explains DevOps principles (CI/CD, IaC, Automation) and links them back to specific repository files (`.github/workflows/ai-check.yml`, pre-commit hooks, deployment orchestrators).

---

### 3. Demonstrating DevOps & CI/CD Capabilities (Terminal Demo)

#### A. Run Selenium Automated Browser/UI Tests
```powershell
pytest tests/test_ui_selenium.py -v
```
* **Expected Result:** `2 passed in ~8s`.
* **What it proves:** Headless Chrome/Edge WebDriver automates end-to-end browser testing, validates Streamlit React DOM mounting, and verifies page elements asynchronously using `WebDriverWait`.

#### B. Run the Pytest Microservice Test Suite
```powershell
pytest tests/test_sample_repo.py -v
```
* **Expected Result:** `3 passed in 0.19s`.
* **What it proves:** Validates JWT creation/verification, DB connection pooling, and deployment rollback logic.

#### C. Run the AI PR Diff Reviewer (Automated Quality Gate)
```powershell
python scripts/ai_pr_reviewer.py
```
* **Expected Result:** Generates [pr_review_report.md](file:///c:/Users/jhala/OneDrive/Desktop/CodeSenseAI/pr_review_report.md) live.
* **What it proves:** Analyzes the active `git diff`, evaluates risk level (`LOW / MEDIUM / HIGH`), flags specific lines, and recommends regression test cases before code merges.

---

### 4. Faculty Viva Q&A Cheat Sheet

#### Q1: *"Explain the service architecture of your application."*
> **Answer:** *"Our system is organized into a **7-service topology**:
> 1. **Application Service:** Streamlit UI managing user interaction and prompt suggestions.
> 2. **Data & Knowledge Service:** 4-mode ingestion pipeline for local dirs, zips, microservices, and Git URLs.
> 3. **Embedding Service:** 384-dimensional dense vector generation via `all-MiniLM-L6-v2`.
> 4. **RAG / Retrieval Service:** In-process ChromaDB vector store with AST cosine similarity ranking.
> 5. **LLM Service:** Cloud Groq LPUs (`qwen`, `llama3`) and local Ollama model management.
> 6. **Git & CI/CD Service:** Boundary service running `ai_pr_reviewer.py` and GitHub Actions.
> 7. **Orchestration Layer:** LangChain pipelines connecting retrieval context to structured prompts."*

#### Q2: *"How do you handle guardrails and hallucination?"*
> **Answer:** *"We enforce dual guardrails:
> - **Scope & Input Guardrail:** Out-of-domain queries (e.g. Stripe or weather) trigger grounded refusals rather than invented code.
> - **Output Guardrail:** Every response surfaces interactive Source Citations with file paths and cosine relevance scores, allowing developers to mathematically verify claims.
> - **Rate Limit Guardrail:** Dynamic 600/800 token ceilings with automatic fallback prevent API rate throttling."*

#### Q3: *"Is your container setup compatible with Podman or only Docker?"*
> **Answer:** *"Our `Dockerfile` and `docker-compose.yml` strictly adhere to **OCI (Open Container Initiative)** standards. They are completely engine-agnostic and run identically with `docker compose up` on Windows or `podman-compose up` on Linux/Ubuntu VMs for daemonless, rootless container security."*

#### Q4: *"What if the port you are running on (8501) stops working or is blocked?"*
> **Answer:** *"The system is decoupled from static ports. Streamlit has automatic port fallback to 8502, Docker allows instant port re-mapping (e.g. `8502:8501`) without rebuilding, and our Dockerfile includes native health checks (`/_stcore/health`) compatible with production load balancers."*
