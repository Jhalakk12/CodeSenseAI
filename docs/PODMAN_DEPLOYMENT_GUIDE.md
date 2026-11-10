# 🐋 CodeSense AI — Rootless Podman Deployment Guide
**Course:** CSE 4011: Intelligent Developer Tools & AI DevOps Workflows  
**Institution:** School of Engineering and Technology, BML Munjal University  
**Specification:** End-Semester Feature 6 — Enterprise Rootless Podman Orchestration  
**Addressing Faculty Feedback:** *"Docker should be replaced with Podman. (Run using only Podman)"*  

---

## 1. Executive Summary: Why Podman Replaces Docker in Enterprise DevOps

Traditional Docker relies on a centralized background daemon (`dockerd`) running as `root` (UID 0) on the host machine. In enterprise AI developer platforms, running code analysis and automated PR remediation tools under a root daemon introduces severe security liabilities (container breakout attacks, unauthorized privilege escalation, and Docker Desktop licensing fees).

**CodeSense AI implements an enterprise Rootless Podman configuration featuring:**
1. **100% Rootless Execution (`userns_mode: keep-id`):** Containers run entirely in user namespaces as an unprivileged user (UID 1000). Even if a malicious script breaks out of the container, it possesses **zero root privileges** on the host.
2. **Daemonless Architecture:** No single point of failure. Individual container lifecycles are managed independently via `conmon`.
3. **SELinux Volume Relabeling (`:Z` flags):** Guarantees persistent database writes for SQLite audit logs (`codesense_audit.db`) and ChromaDB vector embeddings across restarts.
4. **Zero-License Freedom:** 100% open-source under Apache 2.0 (CNCF/Red Hat), eliminating the \$5–\$24/user/mo Docker Desktop tax.
5. **Kubernetes-Native Co-location (`podman play kube`):** Single-command deployment of Kubernetes manifests directly inside Podman.

---

## 2. Podman Multi-Service Pod Architecture

CodeSense AI packages the platform into a single co-located rootless Pod:

```
                          ┌────────────────────────────────────────────────────────┐
                          │         PODMAN ROOTLESS POD (codesense-pod)             │
                          │                                                        │
                          │   ┌──────────────────────┐    ┌─────────────────────┐  │
HTTP :8501 (Web Portal) ──┼──>│ codesense-app        │───>│ ollama-service      │  │
                          │   │ (Streamlit, WatchDog,│    │ (Local Air-Gapped   │  │
                          │   │  AST Engine, SQLite) │    │  Inference Engine)  │  │
                          │   └──────────┬───────────┘    └──────────┬──────────┘  │
                          │              │                           │             │
                          │   ┌──────────▼───────────┐    ┌──────────▼──────────┐  │
                          │   │ Volumes (:Z flag)    │    │ Persistent Models   │  │
                          │   │ ./data, ./chroma_db  │    │ ollama_models       │  │
                          │   └──────────────────────┘    └─────────────────────┘  │
                          └────────────────────────────────────────────────────────┘
```

* **Service 1 (`codesense-app`):** Runs Streamlit frontend, LangChain RAG, WatchDog daemon, and SQLite audit logger on port `8501`.
* **Service 2 (`ollama-service`):** Runs the local air-gapped LLM engine on port `11434`.
* **Private Pod Network (`codesense-pod-net`):** Internal DNS routing allows the app to communicate with Ollama privately without exposing model ports to the public host.

---

## 3. How to Deploy Using ONLY Podman

### Method A: Deploy via `podman-compose` (Recommended)

1. **Launch the Podman Stack:**
   ```bash
   podman-compose -f podman-compose.yml up -d
   ```

2. **Inspect Running Rootless Containers:**
   ```bash
   podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
   ```

3. **Verify Rootless User Security (Non-Root UID):**
   ```bash
   podman top codesense-ai-app user huser
   ```
   *(Notice `HUSER` shows your regular host username, NOT root!)*

4. **Access the Application:**
   * Streamlit Dashboard: **`http://localhost:8501`**
   * Ollama Model Engine: **`http://localhost:11434`**

5. **Stop the Podman Stack:**
   ```bash
   podman-compose -f podman-compose.yml down
   ```

---

### Method B: Deploy Natively via Kubernetes Manifest (`podman play kube`)

Podman can deploy Kubernetes Pod manifests directly without needing `podman-compose` or Minikube:

1. **Deploy with Native Podman:**
   ```bash
   podman play kube podman-k8s.yaml
   ```

2. **Verify Pod Status:**
   ```bash
   podman pod ps
   ```

3. **Tear Down the Kubernetes Pod:**
   ```bash
   podman play kube --down podman-k8s.yaml
   ```

---

## 4. One-Click Deployment Automation Scripts

We provide automated launch scripts for both Windows and Linux:

* **Windows PowerShell:**
  ```powershell
  .\scripts\podman_deploy.ps1
  ```
* **Linux / macOS / WSL2:**
  ```bash
  chmod +x scripts/podman_deploy.sh
  ./scripts/podman_deploy.sh
  ```

---

## 5. Switching Between Podman and Docker

Both container configurations coexist peacefully. Both share the exact same underlying persistent data:

| Action | Command |
| :--- | :--- |
| **Run using ONLY Podman** | `podman-compose -f podman-compose.yml up -d` |
| **Stop Podman** | `podman-compose -f podman-compose.yml down` |
| **Run using ONLY Docker** | `docker compose up -d` |
| **Stop Docker** | `docker compose down` |

---

## 6. Verbal Viva Defense Script (Faculty Feedback Response)

> **Evaluator:** *"We gave feedback that Docker should be replaced with Podman. How did you implement this?"*

> **Your Answer:**
> *"Sir, addressing your feedback directly, we engineered a dedicated **Rootless Podman configuration (`podman-compose.yml`)** and a **Native Kubernetes Pod specification (`podman-k8s.yaml`)**:
> 
> 1. **Rootless Security:** Instead of running under Docker’s root daemon (`dockerd`), CodeSense AI runs inside user namespaces (`userns_mode: keep-id`) with `no-new-privileges:true`. Even if untrusted ingested code tries to escape, it has zero root access on the host.
> 2. **Multi-Service Pod:** Podman bundles both `codesense-app` (port 8501) and our local `ollama-service` (port 11434) inside a private pod network with SELinux `:Z` volume relabeling for our SQLite database and ChromaDB vector store.
> 3. **Run on ONLY Podman:** You can deploy it purely using Podman either via `podman-compose` or natively via `podman play kube podman-k8s.yaml` without needing Docker at all. We also retained Docker compose so developers can switch between both runtimes at will."*

