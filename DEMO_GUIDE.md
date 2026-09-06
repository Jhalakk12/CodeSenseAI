# 🎯 CodeSense AI — Faculty Demo Guide & Viva Preparation (CSE 4011)

**Course:** CSE 4011: Intelligent Developer Tools and AI DevOps Workflows  
**Faculty:** Dr. Kiran Khatter & Mr. Naveen Singh (School of Engineering and Technology, BMU)

---

## ⏱️ 3-Minute Live Demo Walkthrough

### 1. The Opening (30 Seconds)
> *"Good morning/afternoon, Sir. For our CSE 4011 project, we are building **CodeSense AI** — an AI-powered codebase assistant and DevOps automation pipeline.*
> 
> *Our system combines AST-aware semantic code retrieval (RAG) with automated CI/CD quality gates, live GitHub repository cloning, Selenium UI testing, and OCI containerization with Docker and Podman."*

---

### 2. Live Demonstration Sequence (2 Minutes)

#### Step 1: Launch the Interactive Web Console
```powershell
.\.venv\Scripts\streamlit run app.py
```
Open `http://localhost:8501` in your browser.

#### Step 2: Show Repository Ingestion & Dynamic GitHub Cloner
* Point out the **Repository Indexing** section in the left sidebar.
* Show the three flexible source modes:
  1. **Built-in Sample Microservice (`sample_repo`)**: Contains real production services (Auth/JWT, DB connection pool, Deployment orchestrator).
  2. **Clone from GitHub URL**: Select this option to prove the system works on ANY public repository (e.g. `https://github.com/pallets/flask`). Clicking **"🚀 Index Codebase"** triggers a shallow Git clone and generates AST vector embeddings live!
  3. **Custom Local Directory**: For scanning any repository on the developer machine.
* Click **"🚀 Index / Re-Index Codebase"** on `sample_repo`.
* Show the stats badge updating: **Files Indexed: 4**, **Code Chunks: ~14**, **Vector DB: ChromaDB (Active)**.

> **Key Talking Point for Faculty:**
> *"Sir, we don't just split text by lines. We use LangChain's code-aware AST splitter (`RecursiveCharacterTextSplitter.from_language`) to ensure Python class and function definitions stay semantically intact inside our 384-dimensional dense vectors."*

#### Step 3: Run Interactive Quick Actions
1. **Click "🏗️ Explain Architecture"**:
   - The LLM synthesizes cross-file dependencies and explains the service interaction.
   - **Open the collapsible "🔍 Source Citations" box:** Show the faculty the exact source code files and cosine similarity rankings!
2. **Click "🛡️ Security & Bug Audit"**:
   - The model highlights real security vulnerabilities, such as JWT token replay risks and rollback edge cases.
3. **Click "🧪 Generate Unit Tests"**:
   - The model generates comprehensive `pytest` test suites testing happy paths and boundary conditions.

---

### 3. Demonstrating DevOps & CI/CD Capabilities (Terminal Demo)

#### A. Run the Pytest Microservice Test Suite
```powershell
pytest tests/test_sample_repo.py -v
```
*(Runs in 0.2s, showing 3 passed tests verifying JWT, DB pooling, and rollback management).*

#### B. Run Selenium Automated Browser/UI Tests
```powershell
pytest tests/test_ui_selenium.py -v
```
*(Uses headless Chrome/Edge to verify browser driver initialization and live Streamlit DOM rendering).*
> **Talking Point:** *"We added Selenium WebDriver automation to guarantee that our Streamlit UI stays regression-free across CI/CD deployments."*

#### C. Run the AI PR Diff Reviewer
```powershell
python scripts/ai_pr_reviewer.py
```
*(Demonstrates Section 4b/5b of the project: dynamically inspects git diffs, sends them to Groq, flags OWASP vulnerabilities, and generates suggested test cases).*

---

### 4. Faculty Viva Q&A Cheat Sheet

#### Q1: *"Is your container setup compatible with Podman or only Docker?"*
> **Answer:** *"Our container manifests (`Dockerfile` and `docker-compose.yml`) are built strictly to **OCI (Open Container Initiative)** standards. They are completely engine-agnostic and run identically with `docker compose up` on Windows or `podman-compose up` on Linux/Ubuntu VMs for daemonless, rootless container security."*

#### Q2: *"How did you handle Sourcegraph OSS from Phase 1?"*
> **Answer:** *"In Phase 1, we set up self-hosted Sourcegraph OSS via Docker (`docker run -d -p 7080:7080 sourcegraph/server`) for structural AST and regex code search. For Phase 2, we advanced to dense semantic retrieval using LangChain, Hugging Face embeddings, and ChromaDB to understand natural language developer intent."*

#### Q3: *"What embedding model and vector database are you using?"*
> **Answer:** *"We use `sentence-transformers/all-MiniLM-L6-v2` from Hugging Face, which generates 384-dimensional dense vector embeddings. Embeddings are indexed into an in-process persistent ChromaDB vector store, eliminating external cloud database latency and cost."*

#### Q4: *"Can I deploy this on a Linux Virtual Machine?"*
> **Answer:** *"Yes, Sir! Since everything is version-controlled in Git and containerized with multi-stage Docker/Podman files, deploying to our Ubuntu VM is as simple as running `git clone` and `docker compose up`."*
