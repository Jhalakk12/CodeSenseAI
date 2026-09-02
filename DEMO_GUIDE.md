# 🎯 CodeSense AI — Faculty Demo Guide (CSE 4011)

Use this guide during your meeting with **Dr. Kiran Khatter** and **Mr. Naveen Singh** tomorrow.

---

## ⏱️ 3-Minute Demo Script

### 1. The Opening (30 Seconds)
> *"Good morning/afternoon, Sir. For our CSE 4011 project, we are building **CodeSense AI** — an AI-powered codebase assistant and DevOps automation pipeline.*
> 
> *To prove our progress and validate the core architecture early, we have built a working prototype of our **semantic code retrieval (RAG) engine** and containerized the system with Docker and GitHub Actions."*

---

### 2. Live Demo Steps (90 Seconds)

1. **Launch the Web Console:**
   Run in your terminal:
   ```bash
   .\.venv\Scripts\streamlit run app.py
   ```
   Open `http://localhost:8501` in your browser.

2. **Show Code Ingestion & ChromaDB Indexing:**
   - Point out the left sidebar: show that it targets `sample_repo` (a Python microservice containing auth, DB pooling, deployment services, and API routes).
   - Click **"🚀 Index / Re-Index Codebase"**.
   - Show the stats badge updating: **Files Indexed: 4**, **Code Chunks: ~14**, **Vector DB: ChromaDB (Active)**.
   - **Key point to tell the professor:**
     > *"We are not just splitting text arbitrarily. We are using LangChain's code-aware AST recursive splitter (`RecursiveCharacterTextSplitter.from_language`) to ensure function and class definitions are preserved intact in ChromaDB vectors."*

3. **Click Quick Action: "🏗️ Explain Architecture"**
   - The LLM will immediately analyze the retrieved code chunks and output a structured breakdown of the components: `jwt_handler.py`, `connection.py`, `deployment_service.py`, and `routes.py`.
   - **Click the collapsible "🔍 Source Citations" box:** Show the professor the exact retrieved file names and similarity relevance scores!

4. **Click Quick Action: "🛡️ Security & Bug Audit"**
   - The LLM will audit the code and flag the JWT token expiration edge case or unhandled rollback exception in `sample_repo`.
   - **Key point to tell the professor:**
     > *"This demonstrates our semantic search identifying critical paths in the codebase to assist developers before code reaches production."*

5. **Click Quick Action: "🧪 Generate Unit Tests"**
   - The LLM will output full `pytest` test suites testing happy paths, expired token scenarios, and connection pool exhaustion.
   - **Key point to tell the professor:**
     > *"This addresses the AI-driven test generation objective of CO3 and Phase 2."*

---

### 3. How to Answer: *"Is it Dockerized? Where is the DevOps part?"*

If the professor asks why it is running locally or about Docker:
> *"Yes, Sir! We have already configured the entire DevOps containerization pipeline.*
> 
> *(Show them the files in VS Code / File Explorer):*
> 1. `Dockerfile` - *Multi-stage production container for the service.*
> 2. `docker-compose.yml` - *Multi-container orchestration for the app and ChromaDB volume persistence.*
> 3. `.github/workflows/ai-check.yml` - *Automated CI/CD pipeline for GitHub Actions.*
> 
> *For this early milestone demonstration, we are validating the embedding cosine similarity thresholds locally before spinning up the multi-container Docker cluster and Sourcegraph OSS container."*

---

### 4. Alignment with CSE 4011 Rubrics (Cheat Sheet)

| Rubric Component | Your Evidence in the Project |
| :--- | :--- |
| **CO1: Model Capabilities** | Dual toggle between Groq (Llama 3.3/DeepSeek) and local Ollama models. |
| **CO2: Semantic Code Search** | AST-based chunking + ChromaDB vector embeddings + cosine similarity search. |
| **CO3: AI-Assisted Testing** | Automated Pytest test generation button based on retrieved code context. |
| **CO3: CI/CD Automation** | `.github/workflows/ai-check.yml` configured for linting and AI review hooks. |
| **Containerization** | `Dockerfile` & `docker-compose.yml` ready in the project root. |
