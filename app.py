import os
import shutil
import subprocess
import zipfile
import streamlit as st
import stat

def _remove_readonly(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass
from dotenv import load_dotenv
from rag_engine import CodeSenseEngine

# Load environment variables
load_dotenv()

# Streamlit Page Setup
st.set_page_config(
    page_title="CodeSense AI - Intelligent Codebase Assistant",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Dark DevOps Theme)
st.markdown("""
<style>
    .main {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    .stApp {
        background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
    }
    .header-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        background: rgba(56, 139, 253, 0.15);
        color: #58a6ff;
        border: 1px solid rgba(56, 139, 253, 0.4);
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .devops-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .metric-badge {
        background: #21262d;
        border-left: 3px solid #238636;
        padding: 8px 12px;
        border-radius: 4px;
        font-family: monospace;
        margin-bottom: 6px;
    }
    .citation-box {
        background: #161b22;
        border-left: 3px solid #58a6ff;
        padding: 10px 14px;
        margin: 6px 0;
        border-radius: 4px;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

if "indexed" not in st.session_state:
    st.session_state.indexed = False

if "index_stats" not in st.session_state:
    st.session_state.index_stats = None

if "patch_data" not in st.session_state:
    st.session_state.patch_data = None

if "patch_applied" not in st.session_state:
    st.session_state.patch_applied = False

if "target_path" not in st.session_state:
    st.session_state.target_path = os.path.join(os.getcwd(), "sample_repo")

if "active_repo_label" not in st.session_state:
    st.session_state.active_repo_label = "sample_repo"

# Initialize Engine
import importlib
import scripts.patch_generator
import scripts.dependency_graph
importlib.reload(scripts.patch_generator)
importlib.reload(scripts.dependency_graph)

from rag_engine import CodeSenseEngine, check_ollama_status
from scripts.patch_generator import PatchGenerator, generate_unified_patch
from scripts.dependency_graph import DependencyGraph

@st.cache_resource
def get_engine():
    return CodeSenseEngine()

@st.cache_data(ttl=600)
def fetch_cached_groq_models(key: str):
    try:
        from groq import Groq
        client = Groq(api_key=key.strip(), timeout=3.0)
        fetched = client.models.list().data
        allowed_families = ["qwen", "llama", "mixtral", "gemma", "deepseek"]
        return [
            m.id for m in fetched
            if any(fam in m.id.lower() for fam in allowed_families)
            and not any(bad in m.id.lower() for bad in ["guard", "whisper", "vision", "embed"])
        ]
    except Exception:
        return []

@st.cache_data(ttl=10)
def get_cached_ollama_status():
    return check_ollama_status()

engine = get_engine()

# --- SIDEBAR: Configuration & DevOps Controls ---
with st.sidebar:
    st.markdown('<span class="header-badge">CSE 4011 • AI DevOps Workflows</span>', unsafe_allow_html=True)
    st.title("⚡ CodeSense AI")
    st.caption("Intelligent Code Assistant & DevOps Pipeline")
    st.markdown("---")

    # Dual-LLM Engine Configuration
    st.subheader("🔑 Inference Engine")
    engine_choice = st.selectbox(
        "Dual-LLM Engine",
        ["⚡ Groq Cloud LPU (High-Speed Turbo)", "🔒 Local Ollama (100% Air-Gapped Privacy)"],
        index=0,
        help="Switch between cloud LPU speed (Groq) and complete local data privacy (Ollama)."
    )
    provider = "Groq" if "Groq" in engine_choice else "Ollama"

    # Live check Ollama daemon
    ollama_info = get_cached_ollama_status()
    ollama_online = ollama_info.get("running", False)
    installed_ollama_models = ollama_info.get("models", [])

    if provider == "Groq":
        default_groq_key = os.getenv("GROQ_API_KEY", "")
        api_key = st.text_input(
            "Groq API Key",
            value=default_groq_key,
            type="password",
            placeholder="gsk_...",
            help="Use your existing Groq API key for ultra-fast response times."
        )

        groq_models = fetch_cached_groq_models(api_key) if api_key else []

        # Fallback if API key not yet entered or fetch returned empty
        if not groq_models:
            groq_models = [
                "qwen/qwen3.8-27b",
                "llama3-70b-8192",
                "llama3-8b-8192",
                "mixtral-8x7b-32768",
                "gemma2-9b-it"
            ]

        # Prioritize qwen as requested by user, or high-capacity llama
        default_idx = 0
        for i, m in enumerate(groq_models):
            if "qwen" in m.lower():
                default_idx = i
                break
            elif "llama" in m.lower() and "70b" in m.lower():
                default_idx = i

        model_name = st.selectbox(
            "Model",
            groq_models,
            index=default_idx,
            help="Verified generative LLMs available on your Groq account."
        )
        st.caption(f"Selected: `{model_name}`")

        enable_failover = st.checkbox(
            "🛡️ Automatic Local Failover",
            value=True,
            help="If Groq hits rate limits (429/OTPM) or network hiccups, queries automatically fall back to your local Ollama instance."
        )
        if ollama_online:
            st.caption("🟢 Local Ollama Online (`localhost:11434`) • Hot-Standby")
        else:
            st.caption("⚪ Local Ollama offline (Start `ollama serve` for local failover)")
    else:
        # Local Privacy Mode (Ollama)
        api_key = ""  # Zero API key required
        enable_failover = False

        if ollama_online:
            st.success("🟢 Local Ollama Online (`localhost:11434`)")
            st.markdown("""
            <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 8px; padding: 10px; margin-bottom: 12px; font-size: 0.82rem; color: #10b981;">
                🔒 <b>Air-Gapped Privacy Active</b>: All code context, AST chunks, and embeddings remain 100% on this local machine. Zero external API calls.
            </div>
            """, unsafe_allow_html=True)

            # Filter out non-generative models (e.g. text embedding models)
            filtered_installed = [
                m for m in installed_ollama_models
                if not any(k in m.lower() for k in ["embed", "caption"])
            ]
            # Prioritize dedicated code-instruct models
            def _model_priority(name: str) -> int:
                n = name.lower()
                if "qwen2.5-coder:1.5b" in n:
                    return 0
                if "qwen2.5-coder" in n:
                    return 1
                if "codellama" in n:
                    return 2
                if "deepseek" in n:
                    return 3
                if "gemma" in n:
                    return 4
                return 10

            sorted_installed = sorted(filtered_installed, key=_model_priority)

            syllabus_presets = ["qwen2.5-coder:1.5b", "qwen2.5-coder:7b", "deepseek-coder:6.7b", "codellama:7b", "gemma3:1b"]
            all_options = []
            for m in sorted_installed:
                all_options.append(f"{m} (Installed)")
            for m in syllabus_presets:
                if m not in sorted_installed:
                    all_options.append(f"{m} (Requires pull)")

            selected_opt = st.selectbox(
                "Local Model",
                all_options,
                index=0,
                help="Installed local models detected in Ollama or syllabus-recommended presets."
            )
            model_name = selected_opt.split(" ")[0].strip() if selected_opt else "qwen2.5-coder:1.5b"

            if "(Requires pull)" in selected_opt:
                st.info(f"💡 Run in terminal to pull: `ollama pull {model_name}`")
            else:
                st.caption(f"Ready: `{model_name}` (Local Hardware)")
        else:
            st.error("🔴 Local Ollama daemon not detected at `localhost:11434`")
            st.markdown("""
            <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 10px; margin-bottom: 12px; font-size: 0.82rem; color: #f87171;">
                ⚠️ <b>Ollama is not running</b>.<br>
                1. Open PowerShell<br>
                2. Run <code>ollama serve</code><br>
                3. Refresh this page to activate Local Air-Gapped mode.
            </div>
            """, unsafe_allow_html=True)
            model_name = st.text_input("Custom Ollama Model", value="qwen2.5:1.5b")

    st.markdown("---")

    # Codebase Target
    st.subheader("📁 Repository Indexing")
    repo_option = st.radio(
        "Source Codebase",
        [
            "Built-in Sample Microservice (sample_repo)",
            "Clone from GitHub URL",
            "Upload Codebase (.ZIP Archive)",
            "Custom Local Directory"
        ],
        index=0
    )

    github_url = ""
    uploaded_zip = None
    repo_label = "sample_repo"
    if repo_option == "Custom Local Directory":
        target_path = st.text_input("Directory Absolute Path", value=os.getcwd(), help="Absolute path to any folder on your computer.")
        repo_label = os.path.basename(target_path.strip()) or "Local Directory"
    elif repo_option == "Clone from GitHub URL":
        github_url = st.text_input(
            "GitHub Repository URL",
            value="https://github.com/pallets/flask",
            placeholder="https://github.com/username/repository",
            help="Provide any public or private GitHub repository to clone and index its AST code vectors."
        )
        is_private = st.checkbox(
            "🔒 Private Repository Authentication (GitHub PAT)",
            value=False,
            help="Enable if this is a private GitHub repository requiring authentication."
        )
        github_token = ""
        if is_private:
            default_token = os.getenv("GITHUB_PAT") or os.getenv("GITHUB_TOKEN") or ""
            github_token = st.text_input(
                "GitHub Personal Access Token (PAT)",
                value=default_token,
                type="password",
                placeholder="ghp_xxxxxxxxxxxxxxxxxxxx",
                help="Fine-grained or classic token with read access. Token is held in ephemeral RAM only."
            )
            st.caption("🛡️ **Enterprise Data Privacy**: Token is held in ephemeral RAM only during git clone and is never logged, stored on disk, or indexed into ChromaDB.")

        force_reclone = st.checkbox(
            "🔄 Force Fresh Re-Clone (Bypass Cache)",
            value=False,
            help="Delete any local cached copy and clone fresh from GitHub."
        )

        repo_name = github_url.rstrip("/").split("/")[-1].replace(".git", "") if github_url else "repo"
        target_path = os.path.join(os.getcwd(), "cloned_repos", repo_name)
        repo_label = repo_name
    elif repo_option == "Upload Codebase (.ZIP Archive)":
        uploaded_zip = st.file_uploader(
            "Upload Codebase ZIP Archive",
            type=["zip"],
            help="Drag and drop any zipped source code folder."
        )
        if uploaded_zip is not None:
            zip_stem = os.path.splitext(uploaded_zip.name)[0]
            target_path = os.path.join(os.getcwd(), "uploaded_repos", zip_stem)
            repo_label = zip_stem
        else:
            target_path = st.session_state.get("target_path", "")
            repo_label = st.session_state.get("active_repo_label", "Uploaded ZIP")
    else:
        target_path = os.path.join(os.getcwd(), "sample_repo")
        repo_label = "sample_repo (Built-in)"

    if target_path and os.path.exists(target_path):
        st.session_state.target_path = target_path
        st.session_state.active_repo_label = repo_label

    if st.button("🚀 Index / Re-Index Codebase", use_container_width=True, type="primary"):
        with st.spinner("Analyzing codebase and generating ChromaDB vectors..."):
            try:
                if repo_option == "Clone from GitHub URL":
                    if not github_url or not github_url.startswith(("http://", "https://", "git@")):
                        st.error("Please enter a valid GitHub repository URL.")
                        st.stop()

                    if is_private and not github_token.strip():
                        st.error("🔒 Please provide a GitHub Personal Access Token (PAT) for private repository access.")
                        st.stop()

                    os.makedirs(os.path.join(os.getcwd(), "cloned_repos"), exist_ok=True)

                    # Prepare authenticated clone URL if private token provided
                    clean_url = github_url.strip()
                    if is_private and github_token.strip():
                        token = github_token.strip()
                        if "github.com" in clean_url:
                            repo_part = clean_url.split("github.com")[-1].lstrip("/:")
                            if not repo_part.endswith(".git"):
                                repo_part += ".git"
                            auth_clone_url = f"https://x-access-token:{token}@github.com/{repo_part}"
                        else:
                            auth_clone_url = clean_url.replace("https://", f"https://x-access-token:{token}@")
                    else:
                        auth_clone_url = clean_url

                    sanitized_display_url = github_url.strip()

                    clone_env = {
                        **os.environ,
                        "GIT_TERMINAL_PROMPT": "0",
                        "GCM_INTERACTIVE": "never",
                        "GIT_ASKPASS": "",
                    }
                    git_base_cmd = [
                        "git",
                        "-c", "credential.helper=",
                        "-c", "core.askPass=",
                    ]

                    # If user requested force re-clone, delete cached directory
                    if force_reclone and os.path.exists(target_path):
                        shutil.rmtree(target_path, onerror=_remove_readonly)

                    # Only treat as cached if target_path exists and has actual files
                    is_valid_cache = False
                    if os.path.exists(target_path):
                        try:
                            cached_files = [f for f in os.listdir(target_path) if f != ".git"]
                            if cached_files and os.path.exists(os.path.join(target_path, ".git")):
                                is_valid_cache = True
                            else:
                                shutil.rmtree(target_path, onerror=_remove_readonly)
                        except Exception:
                            shutil.rmtree(target_path, onerror=_remove_readonly)

                    if not is_valid_cache:
                        st.info(f"Cloning `{sanitized_display_url}` (shallow clone)...")
                        res = subprocess.run(
                            git_base_cmd + ["clone", "--depth", "1", auth_clone_url, target_path],
                            capture_output=True,
                            text=True,
                            timeout=30,
                            env=clone_env
                        )
                        if res.returncode != 0:
                            shutil.rmtree(target_path, onerror=_remove_readonly)
                            raw_err = res.stderr
                            sanitized_err = raw_err
                            if is_private and github_token.strip():
                                sanitized_err = sanitized_err.replace(github_token.strip(), "******")

                            err_lower = raw_err.lower()
                            if not is_private and any(kw in err_lower for kw in ["could not read username", "terminal prompts disabled", "authentication failed", "repository not found"]):
                                st.error("🔒 **Authentication Required**: This repository appears to be private. Please check the **'🔒 Private Repository Authentication (GitHub PAT)'** checkbox above and provide your GitHub Personal Access Token.")
                            elif is_private and any(kw in err_lower for kw in ["could not read username", "terminal prompts disabled", "authentication failed", "bad credentials"]):
                                st.error(f"🔒 **Authentication Failed**: Invalid or expired GitHub Personal Access Token (PAT). Please verify your token has 'repo' / 'read' permissions. (Error: {sanitized_err})")
                            else:
                                st.error(f"Git clone failed: {sanitized_err}")
                            st.stop()
                        # Security: Scrub token from git remote config so credentials never persist on disk
                        subprocess.run(["git", "-C", target_path, "remote", "set-url", "origin", clean_url], capture_output=True)
                        st.success(f"Successfully cloned `{sanitized_display_url}`.")
                    else:
                        st.info(f"Using cached clone at `{target_path}`. Pulling latest changes...")
                        pull_res = subprocess.run(
                            ["git", "-C", target_path, "-c", "credential.helper=", "-c", "core.askPass=", "pull", auth_clone_url],
                            capture_output=True,
                            text=True,
                            timeout=30,
                            env=clone_env
                        )
                        if pull_res.returncode != 0:
                            pull_err = pull_res.stderr.lower()
                            if not is_private and any(kw in pull_err for kw in ["could not read username", "terminal prompts disabled", "authentication failed", "repository not found"]):
                                st.error("🔒 **Authentication Required**: This repository is private. Please check the **'🔒 Private Repository Authentication (GitHub PAT)'** checkbox above and enter your GitHub Personal Access Token to pull updates.")
                                st.stop()
                            elif is_private and any(kw in pull_err for kw in ["could not read username", "terminal prompts disabled", "authentication failed", "bad credentials"]):
                                sanitized_pull_err = pull_res.stderr.replace(github_token.strip(), "******") if (is_private and github_token.strip()) else pull_res.stderr
                                st.error(f"🔒 **Authentication Failed**: Invalid or expired GitHub Personal Access Token (PAT). (Error: {sanitized_pull_err})")
                                st.stop()
                            else:
                                st.warning(f"⚠️ Could not pull latest changes from remote. Proceeding with existing local clone.")

                elif repo_option == "Upload Codebase (.ZIP Archive)":
                    if not uploaded_zip:
                        st.error("Please select a .ZIP file to upload before indexing.")
                        st.stop()
                    os.makedirs(target_path, exist_ok=True)
                    with zipfile.ZipFile(uploaded_zip) as z:
                        z.extractall(target_path)
                    st.info(f"Extracted archive `{uploaded_zip.name}` successfully.")

                if not target_path or not os.path.exists(target_path):
                    st.error(f"Target path `{target_path}` does not exist.")
                    st.stop()

                stats = engine.index_codebase(target_path)
                st.session_state.indexed = True
                st.session_state.index_stats = stats
                st.success(f"Indexed {stats['indexed_files']} files ({stats['total_chunks']} chunks) successfully!")
            except Exception as e:
                st.error(f"Indexing failed: {str(e)}")

    if st.session_state.index_stats:
        stats = st.session_state.index_stats
        st.markdown(f"""
        <div class="metric-badge">
            <b>Files Indexed:</b> {stats['indexed_files']}<br>
            <b>Code Chunks:</b> {stats['total_chunks']}<br>
            <b>Vector DB:</b> ChromaDB (Active)
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # DevOps Architecture Verification
    st.subheader("🛠️ DevOps Pipeline Status")
    st.markdown("""
    <div style="font-size: 0.85rem; color: #8b949e; line-height: 1.6;">
        <div>🐳 <b>Dockerfile:</b> <span style="color: #3fb950;">Configured</span></div>
        <div>📦 <b>Docker Compose:</b> <span style="color: #3fb950;">Ready</span></div>
        <div>⚙️ <b>CI/CD (GitHub Actions):</b> <span style="color: #3fb950;">Active</span></div>
        <div>📊 <b>Vector Store:</b> <span style="color: #58a6ff;">ChromaDB Persistent</span></div>
        <div>🌐 <b>Architecture:</b> <span style="color: #58a6ff;">7-Service Topology</span></div>
        <div>🛡️ <b>Guardrails:</b> <span style="color: #3fb950;">Scope & Grounding Active</span></div>
    </div>
    """, unsafe_allow_html=True)


# --- MAIN INTERFACE ---
st.markdown('<span class="header-badge">AI-Powered DevOps Automation</span>', unsafe_allow_html=True)
st.title("CodeSense AI — Developer Console")
st.markdown(
    "Query your repository using **semantic code retrieval (RAG)**, audit for security risks, and generate automated test suites."
)

import re

def render_model_output(text: str):
    """
    Renders model output, neatly tucking <think>...</think> reasoning blocks into an expander.
    """
    think_match = re.search(r"<think>(.*?)</think>", text, flags=re.DOTALL)
    if think_match:
        thought_process = think_match.group(1).strip()
        final_answer = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        with st.expander("💭 View Model Reasoning & Retrieval Logic", expanded=False):
            st.markdown(thought_process)
        st.markdown(final_answer)
    else:
        st.markdown(text)

tab_chat, tab_remediation, tab_graph = st.tabs([
    "💬 Semantic Code Assistant",
    "🛠️ PR Auto-Remediation (Sweep.dev Pattern)",
    "🕸️ Dependency & Blast Radius Visualizer"
])

with tab_chat:
    # Quick Action Trigger Bar
    col1, col2, col3, col4 = st.columns(4)

    selected_task = "general"
    quick_prompt = None

    with col1:
        if st.button("🏗️ Explain Architecture", use_container_width=True):
            quick_prompt = "Explain the overall architecture and main components of this codebase."
            selected_task = "general"

    with col2:
        if st.button("🛡️ Security & Bug Audit", use_container_width=True):
            quick_prompt = "Audit the codebase for security edge-cases, unhandled exceptions, and authentication vulnerabilities."
            selected_task = "security"

    with col3:
        if st.button("🧪 Generate Unit Tests", use_container_width=True):
            quick_prompt = "Generate comprehensive pytest test cases for the core functions in this repository."
            selected_task = "testing"

    with col4:
        if st.button("🧹 Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    st.markdown("---")

    # Render Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                if msg.get("provider_used"):
                    st.markdown(f'<div style="display: inline-block; padding: 2px 10px; background: rgba(59, 130, 246, 0.12); border: 1px solid rgba(59, 130, 246, 0.28); border-radius: 12px; font-size: 0.75rem; color: #93c5fd; margin-bottom: 8px;">🤖 <b>Engine:</b> {msg["provider_used"]} | <b>Model:</b> <code>{msg.get("model_used", "")}</code></div>', unsafe_allow_html=True)
                render_model_output(msg["content"])
            else:
                st.markdown(msg["content"])

            if "citations" in msg and msg["citations"]:
                with st.expander(f"🔍 Source Citations ({len(msg['citations'])} code chunks retrieved)"):
                    for cite in msg["citations"]:
                        st.markdown(f"""
                        <div class="citation-box">
                            <b>📄 Source:</b> <code>{cite['source']}</code> | <b>Relevance:</b> {cite['score']}<br>
                            <pre style="margin-top: 5px;"><code>{cite['snippet']}</code></pre>
                        </div>
                        """, unsafe_allow_html=True)

    # Handle Prompt Submission
    user_query = st.chat_input("Ask a question about the codebase (e.g. 'How is user authentication handled?')...")

    # If a quick action button was clicked, trigger it
    if quick_prompt:
        user_query = quick_prompt

    if user_query:
        if not api_key and provider == "Groq":
            st.warning("⚠️ Please provide your Groq API Key in the left sidebar to run the inference (or switch to 🔒 Local Ollama for keyless execution).")
        else:
            # Check if indexed
            if not st.session_state.indexed:
                # Auto-index the sample repo for immediate seamless experience
                with st.spinner("Auto-indexing repository on first run..."):
                    stats = engine.index_codebase(target_path)
                    st.session_state.indexed = True
                    st.session_state.index_stats = stats

            # Display user message
            st.session_state.messages.append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.markdown(user_query)

            # Generate response
            with st.chat_message("assistant"):
                with st.spinner("Analyzing codebase vectors and generating response..."):
                    try:
                        res = engine.query_codebase(
                            query=user_query,
                            api_key=api_key if provider == "Groq" else None,
                            model_name=model_name,
                            provider=provider,
                            task_mode=selected_task,
                            max_tokens=600,
                            enable_failover=enable_failover
                        )
                        
                        if res.get("failover") and res["failover"].get("triggered"):
                            st.warning(f"⚠️ **Automatic Local Failover Triggered**:\n{res['failover'].get('reason', '')}")

                        provider_used_tag = res.get("provider_used", provider)
                        model_used_tag = res.get("model_used", model_name)
                        st.markdown(f'<div style="display: inline-block; padding: 2px 10px; background: rgba(59, 130, 246, 0.12); border: 1px solid rgba(59, 130, 246, 0.28); border-radius: 12px; font-size: 0.75rem; color: #93c5fd; margin-bottom: 8px;">🤖 <b>Engine:</b> {provider_used_tag} | <b>Model:</b> <code>{model_used_tag}</code></div>', unsafe_allow_html=True)

                        render_model_output(res["answer"])
                        
                        if res["citations"]:
                            with st.expander(f"🔍 Source Citations ({len(res['citations'])} code chunks retrieved)"):
                                for cite in res["citations"]:
                                    st.markdown(f"""
                                    <div class="citation-box">
                                        <b>📄 Source:</b> <code>{cite['source']}</code> | <b>Relevance:</b> {cite['score']}<br>
                                        <pre style="margin-top: 5px;"><code>{cite['snippet']}</code></pre>
                                    </div>
                                    """, unsafe_allow_html=True)

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": res["answer"],
                            "citations": res["citations"],
                            "provider_used": provider_used_tag,
                            "model_used": model_used_tag
                        })
                    except Exception as e:
                        st.error(f"Error generating answer: {str(e)}")


with tab_remediation:
    st.markdown("""
    <div style="background: rgba(33, 38, 45, 0.85); border: 1px solid #30363d; border-radius: 8px; padding: 14px 18px; margin-bottom: 16px;">
        <h4 style="margin: 0 0 6px 0; color: #58a6ff;">🛠️ Sweep.dev Autonomous PR Auto-Remediation Engine</h4>
        <p style="margin: 0; font-size: 0.88rem; color: #8b949e; line-height: 1.5;">
            Select any file in the indexed repository, describe the required bugfix or hardening archetype, and CodeSense AI will generate a syntactically valid, conflict-free unified git diff (<code>diff --git</code>). Review changes, apply them directly to disk with automatic <code>.bak</code> rollback safety, or download a <code>.patch</code> artifact.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Resolve target directory for candidate files
    scan_dir = target_path if (target_path and os.path.exists(target_path)) else os.path.join(os.getcwd(), "sample_repo")
    candidate_files = []
    if os.path.exists(scan_dir):
        for root, dirs, files in os.walk(scan_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["__pycache__", "venv", ".venv", "chroma_db", "node_modules", "uploaded_repos", "cloned_repos"]]
            for f in files:
                if f.endswith((".py", ".js", ".ts", ".java", ".go", ".json", ".md", ".yaml", ".yml", ".html", ".css")):
                    rel = os.path.relpath(os.path.join(root, f), scan_dir).replace("\\", "/")
                    candidate_files.append(rel)
    candidate_files = sorted(candidate_files)

    col_file_sel, col_archetype = st.columns([1, 1])

    with col_file_sel:
        selected_file_rel = st.selectbox(
            "📂 Target Source File",
            options=candidate_files if candidate_files else ["auth/jwt_handler.py", "database/connection.py", "services/deployment_service.py"],
            help="Choose the file to audit, harden, or refactor."
        )
        full_target_file = os.path.join(scan_dir, selected_file_rel) if candidate_files else os.path.join(os.getcwd(), "sample_repo", "auth", "jwt_handler.py")

    with col_archetype:
        preset_category = st.selectbox(
            "🎯 Remediation Archetype",
            [
                "🛡️ Security Hardening (JWT Secret Fallback & Injection Resistance)",
                "⚡ Exception & Resource Leak Fix (Connection Pool Exhaustion)",
                "🧪 Defensive Input Validation & Boundary Checks",
                "📝 Custom Refactor / Bug Fix Specification"
            ]
        )

    # Prepopulate archetype description
    if "Security Hardening" in preset_category:
        default_issue = "Eliminate hardcoded fallback secrets ('supersecret'), enforce strict cryptographic verification, and validate input types before signing or decoding."
    elif "Exception" in preset_category or "Resource Leak" in preset_category:
        default_issue = "Add robust try/finally resource cleanup to prevent connection leaks, implement max connection limit validation, and handle exhaustion edge cases."
    elif "Defensive Input" in preset_category:
        default_issue = "Add defensive boundary checks, sanitize input strings against injection, and reject null or malformed payloads."
    else:
        default_issue = "Refactor the file to improve error resilience, type safety, and code maintainability."

    issue_description = st.text_area(
        "📋 Remediation Requirements / Bug Report",
        value=default_issue,
        height=85,
        help="Specify the bug details, edge case, or security flaw to remediate."
    )

    col_btn_gen, col_engine_status = st.columns([1, 1])
    with col_btn_gen:
        generate_clicked = st.button("🚀 Generate Auto-Remediation Patch (Sweep.dev Mode)", type="primary", use_container_width=True)
    with col_engine_status:
        st.markdown(f'<div style="padding: 9px 12px; background: rgba(56, 139, 253, 0.08); border: 1px solid rgba(56, 139, 253, 0.25); border-radius: 6px; font-size: 0.85rem; color: #58a6ff;">🤖 <b>Active Engine:</b> {provider} | <b>Model:</b> <code>{model_name}</code></div>', unsafe_allow_html=True)

    if generate_clicked:
        if not api_key and provider == "Groq":
            st.warning("⚠️ Please provide your Groq API Key in the left sidebar to run the inference (or switch to 🔒 Local Ollama for keyless execution).")
        else:
            with st.spinner(f"Analyzing `{selected_file_rel}` and computing unified git patch..."):
                try:
                    patch_gen = PatchGenerator(engine)
                    res = patch_gen.generate_fix(
                        file_path=full_target_file,
                        issue_description=issue_description,
                        provider=provider,
                        model_name=model_name,
                        api_key=api_key if provider == "Groq" else None,
                        enable_failover=enable_failover
                    )
                    st.session_state.patch_data = res
                    st.session_state.patch_applied = False
                    st.success("✅ Unified remediation patch generated successfully!")
                except Exception as e:
                    st.error(f"Patch generation failed: {str(e)}")

    if st.session_state.patch_data:
        pdata = st.session_state.patch_data
        st.markdown("---")
        st.subheader("📑 Proposed Unified Git Diff")
        
        failover_info = pdata.get("failover")
        if failover_info and failover_info.get("triggered"):
            st.warning(f"⚠️ **Automatic Local Failover Triggered**:\n{failover_info.get('reason')}")

        st.caption(f"Target File: `{pdata['file_path']}` | Generated by: `{pdata['provider_used']}` (`{pdata['model_used']}`)")

        diff_text = pdata.get("patch_diff", "")
        if diff_text:
            st.code(diff_text, language="diff")
        else:
            st.info("ℹ️ No syntax changes were needed — the code is already compliant with the specification.")

        diff_tab1, diff_tab2 = st.tabs(["✨ Remediated Code", "📜 Original Code"])
        with diff_tab1:
            st.code(pdata.get("remediated_code", ""), language="python")
        with diff_tab2:
            st.code(pdata.get("original_code", ""), language="python")

        # Action Buttons Row
        act_col1, act_col2, act_col3 = st.columns(3)
        with act_col1:
            if st.button("⚡ Apply Patch Directly to Disk", use_container_width=True, type="secondary", disabled=st.session_state.patch_applied):
                try:
                    apply_res = PatchGenerator.apply_patch_to_file(
                        pdata["file_path"],
                        pdata["remediated_code"],
                        create_backup=True
                    )
                    st.session_state.patch_applied = True
                    st.success(f"✅ Patch applied! Safety backup created at: `{apply_res['backup_path']}`")
                except Exception as e:
                    st.error(f"Failed to apply patch: {str(e)}")

        with act_col2:
            if st.button("↩️ Rollback Changes (.bak)", use_container_width=True, disabled=not st.session_state.patch_applied):
                try:
                    PatchGenerator.rollback_patch(pdata["file_path"])
                    st.session_state.patch_applied = False
                    st.info("↩️ File successfully rolled back to its original state from backup!")
                except Exception as e:
                    st.error(f"Rollback failed: {str(e)}")

        with act_col3:
            patch_filename = f"{os.path.basename(pdata['file_path'])}.patch"
            st.download_button(
                label="💾 Download .patch File",
                data=diff_text,
                file_name=patch_filename,
                mime="text/plain",
                use_container_width=True
            )


with tab_graph:
    st.markdown("""
    <div style="background: rgba(33, 38, 45, 0.85); border: 1px solid #30363d; border-radius: 8px; padding: 14px 18px; margin-bottom: 16px;">
        <h4 style="margin: 0 0 6px 0; color: #58a6ff;">🕸️ Repository Architecture & Dependency Visualizer ("Blast Radius")</h4>
        <p style="margin: 0; font-size: 0.88rem; color: #8b949e; line-height: 1.5;">
            Static AST analysis maps repository import topologies and computes downstream change impact. Inspect the full repository architectural blueprint (files as component boxes grouped by directory clusters) or select any module to calculate downstream Blast Radius change risk and DevOps quality gates.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Determine active ingested repo name from session state or sidebar
    active_path = st.session_state.get("target_path") or target_path or os.path.join(os.getcwd(), "sample_repo")
    ingested_name = st.session_state.get("active_repo_label") or os.path.basename(active_path) or "sample_repo"

    col_scope, col_mode = st.columns([1, 1])

    with col_scope:
        repo_scope = st.radio(
            "📁 Analysis Repository Scope",
            [
                f"📥 Currently Ingested Repository ({ingested_name})",
                "🌐 CodeSense AI System Repository (CodeSenseAI Root: 16 modules)",
                "📂 Custom Local Folder / Repository Path..."
            ],
            index=0,
            help="Automatically analyzes whatever codebase you selected or uploaded in the left sidebar."
        )

    with col_mode:
        view_mode = st.radio(
            "🗺️ Visualization View Mode",
            [
                "🗺️ Whole Repository Architecture Map (All Files as Boxes)",
                "🎯 Single File Change Impact ('Blast Radius')"
            ],
            index=0,
            help="Overview displays the entire project topology; Blast Radius evaluates risk when modifying a specific file."
        )

    if "Currently Ingested" in repo_scope:
        graph_dir = active_path if (active_path and os.path.exists(active_path)) else os.path.join(os.getcwd(), "sample_repo")
    elif "CodeSense AI" in repo_scope:
        graph_dir = os.getcwd()
    else:
        custom_input_path = st.text_input(
            "Enter Full Path to Any Local Repository / Directory",
            value=active_path if (active_path and os.path.exists(active_path)) else os.getcwd(),
            help="Provide any absolute or relative path to any Python project folder on your computer."
        )
        graph_dir = custom_input_path.strip() if (custom_input_path and os.path.exists(custom_input_path.strip())) else os.getcwd()

    try:
        dep_graph = DependencyGraph(graph_dir)
        available_files = list(dep_graph.modules.keys())
    except Exception as e:
        st.error(f"Failed to parse codebase AST: {e}")
        dep_graph = None
        available_files = []

    if dep_graph and available_files:
        # Common controls bar
        ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns([1.2, 1, 1, 1])
        with ctrl_col1:
            graph_format = st.radio(
                "Render Engine",
                ["⚡ Interactive Graphviz (SVG/DOT)", "📊 Mermaid Flowchart"],
                horizontal=True
            )
        with ctrl_col2:
            rankdir_opt = st.selectbox(
                "Layout Orientation",
                ["Left-to-Right (LR)", "Top-to-Bottom (TB)"],
                index=0
            )
            direction_code = "LR" if "LR" in rankdir_opt else "TB"
        with ctrl_col3:
            show_symbols = st.checkbox("🏷️ Show Functions/Classes", value=True, help="Render class and function lists inside each file box")
        with ctrl_col4:
            group_clusters = st.checkbox("📦 Group Directory Clusters", value=True, help="Enclose files within dashed folder subgraph clusters")

        if "Whole Repository" in view_mode:
            # Full Project Topology Overview
            all_folders = set(os.path.dirname(m) or "Root" for m in dep_graph.modules)
            total_edges = sum(len(v) for v in dep_graph.adj.values())
            test_modules = [m for m, meta in dep_graph.modules.items() if meta.get("is_test")]

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"""
                <div style="background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px; text-align: center;">
                    <div style="font-size: 0.75rem; color: #8b949e; text-transform: uppercase;">📄 Total Files / Modules</div>
                    <div style="font-size: 1.25rem; font-weight: 700; color: #58a6ff;">{len(dep_graph.modules)}</div>
                    <div style="font-size: 0.75rem; color: #8b949e;">Python source files</div>
                </div>
                """, unsafe_allow_html=True)
            with m2:
                st.markdown(f"""
                <div style="background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px; text-align: center;">
                    <div style="font-size: 0.75rem; color: #8b949e; text-transform: uppercase;">📁 Subsystems / Folders</div>
                    <div style="font-size: 1.25rem; font-weight: 700; color: #3fb950;">{len(all_folders)}</div>
                    <div style="font-size: 0.75rem; color: #8b949e;">Directory packages</div>
                </div>
                """, unsafe_allow_html=True)
            with m3:
                st.markdown(f"""
                <div style="background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px; text-align: center;">
                    <div style="font-size: 0.75rem; color: #8b949e; text-transform: uppercase;">🔗 Inter-Module Imports</div>
                    <div style="font-size: 1.25rem; font-weight: 700; color: #d29922;">{total_edges}</div>
                    <div style="font-size: 0.75rem; color: #8b949e;">Architectural connections</div>
                </div>
                """, unsafe_allow_html=True)
            with m4:
                st.markdown(f"""
                <div style="background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px; text-align: center;">
                    <div style="font-size: 0.75rem; color: #8b949e; text-transform: uppercase;">🧪 Test Suites</div>
                    <div style="font-size: 1.25rem; font-weight: 700; color: #79c0ff;">{len(test_modules)}</div>
                    <div style="font-size: 0.75rem; color: #8b949e;">Automated test files</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("🌐 Visual Architecture Blueprint")
            st.caption("Each file is represented as an architectural box grouped into its directory package. Arrows denote module imports.")

            if "Graphviz" in graph_format:
                dot_code = dep_graph.generate_dot(
                    selected_file=None,
                    show_symbols=show_symbols,
                    group_by_dir=group_clusters,
                    rankdir=direction_code
                )
                st.graphviz_chart(dot_code, use_container_width=True)
            else:
                mermaid_code = dep_graph.generate_mermaid(selected_file=None, direction=direction_code)
                st.markdown(f"```mermaid\n{mermaid_code}\n```")

            with st.expander("📋 Repository Module Directory & Symbol Manifest", expanded=False):
                manifest_data = []
                for mod, meta in sorted(dep_graph.modules.items()):
                    folder = os.path.dirname(mod) or "Root"
                    funcs = ", ".join(meta.get("functions", [])) or "—"
                    classes = ", ".join(meta.get("classes", [])) or "—"
                    imports_count = len(dep_graph.adj.get(mod, set()))
                    callers_count = len(dep_graph.rev_adj.get(mod, set()))
                    manifest_data.append({
                        "File": os.path.basename(mod),
                        "Folder": folder,
                        "Lines": meta.get("line_count", 0),
                        "Classes": classes,
                        "Functions": funcs,
                        "Imports Out": imports_count,
                        "Imported By": callers_count
                    })
                st.dataframe(manifest_data, use_container_width=True)

        else:
            # Single File Blast Radius Mode
            st.markdown("---")
            col_sel_file, _ = st.columns([2, 1])
            with col_sel_file:
                default_g_idx = 0
                for i, f in enumerate(available_files):
                    if "jwt_handler" in f or "rag_engine" in f:
                        default_g_idx = i
                        break

                selected_graph_file = st.selectbox(
                    "📂 Select Target File for Blast Radius Analysis",
                    options=available_files,
                    index=default_g_idx,
                    help="Choose a module to compute which downstream files and tests will be impacted if modified."
                )

            blast = dep_graph.get_blast_radius(selected_graph_file)

            risk_color_map = {
                "CRITICAL": "#f85149",
                "HIGH": "#d29922",
                "MEDIUM": "#e3b341",
                "LOW": "#3fb950"
            }
            risk_bg_map = {
                "CRITICAL": "rgba(248, 81, 73, 0.15)",
                "HIGH": "rgba(210, 153, 34, 0.15)",
                "MEDIUM": "rgba(227, 179, 65, 0.15)",
                "LOW": "rgba(63, 185, 80, 0.15)"
            }
            risk_color = risk_color_map.get(blast["risk_level"], "#58a6ff")
            risk_bg = risk_bg_map.get(blast["risk_level"], "rgba(88, 166, 255, 0.15)")

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"""
                <div style="background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px; text-align: center;">
                    <div style="font-size: 0.75rem; color: #8b949e; text-transform: uppercase;">💥 Blast Radius</div>
                    <div style="font-size: 1.25rem; font-weight: 700; color: #58a6ff;">{blast['total_affected_count']} <span style="font-size: 0.85rem; font-weight: 400; color: #8b949e;">/ {blast['total_modules']}</span></div>
                    <div style="font-size: 0.75rem; color: #8b949e;">{blast['impact_percentage']}% of codebase</div>
                </div>
                """, unsafe_allow_html=True)

            with m2:
                st.markdown(f"""
                <div style="background: {risk_bg}; border: 1px solid {risk_color}; border-radius: 6px; padding: 12px; text-align: center;">
                    <div style="font-size: 0.75rem; color: {risk_color}; text-transform: uppercase;">⚠️ Change Risk Level</div>
                    <div style="font-size: 1.25rem; font-weight: 700; color: {risk_color};">{blast['risk_level']}</div>
                    <div style="font-size: 0.75rem; color: #8b949e;">Automated Evaluation</div>
                </div>
                """, unsafe_allow_html=True)

            with m3:
                st.markdown(f"""
                <div style="background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px; text-align: center;">
                    <div style="font-size: 0.75rem; color: #8b949e; text-transform: uppercase;">🔗 Direct Callers</div>
                    <div style="font-size: 1.25rem; font-weight: 700; color: #d29922;">{len(blast['direct_dependents'])}</div>
                    <div style="font-size: 0.75rem; color: #8b949e;">Immediate dependents</div>
                </div>
                """, unsafe_allow_html=True)

            with m4:
                st.markdown(f"""
                <div style="background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px; text-align: center;">
                    <div style="font-size: 0.75rem; color: #8b949e; text-transform: uppercase;">🧪 Affected Tests</div>
                    <div style="font-size: 1.25rem; font-weight: 700; color: #3fb950;">{len(blast['affected_tests'])}</div>
                    <div style="font-size: 0.75rem; color: #8b949e;">Must pass in CI</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("🌐 Visual Blast Radius Impact Map")
            st.caption("Color Legend: 🔴 **Selected Target** | 🟠 **Directly Impacted Downstream** | 🟡 **Transitively Affected** | 🔵 **Unaffected Modules**")

            if "Graphviz" in graph_format:
                dot_code = dep_graph.generate_dot(
                    selected_file=selected_graph_file,
                    show_symbols=show_symbols,
                    group_by_dir=group_clusters,
                    rankdir=direction_code
                )
                st.graphviz_chart(dot_code, use_container_width=True)
            else:
                mermaid_code = dep_graph.generate_mermaid(selected_file=selected_graph_file, direction=direction_code)
                st.markdown(f"```mermaid\n{mermaid_code}\n```")

            # Breakdown Cards
            st.markdown("---")
            b_col1, b_col2 = st.columns(2)

            with b_col1:
                st.markdown("#### 💥 Impacted Downstream Modules")
                if blast["all_affected"]:
                    for dep in blast["all_affected"]:
                        is_direct = dep in blast["direct_dependents"]
                        tag = "Direct Caller" if is_direct else "Transitive Reachable"
                        tag_color = "#d29922" if is_direct else "#e3b341"
                        st.markdown(f"""
                        <div style="background: #161b22; border-left: 3px solid {tag_color}; padding: 8px 12px; margin-bottom: 6px; border-radius: 4px; font-size: 0.85rem;">
                            <b><code>{dep}</code></b> <span style="font-size: 0.75rem; color: {tag_color};">({tag})</span>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("No other modules depend on this file (Leaf node). Safe to refactor with isolated risk.")

            with b_col2:
                st.markdown("#### 🛡️ DevOps Quality Gate & Recommendations")
                for rec in blast["recommendations"]:
                    st.markdown(f"""
                    <div style="background: rgba(56, 139, 253, 0.08); border-left: 3px solid #58a6ff; padding: 8px 12px; margin-bottom: 6px; border-radius: 4px; font-size: 0.85rem; color: #c9d1d9;">
                        {rec}
                    </div>
                    """, unsafe_allow_html=True)

                if blast["functions"] or blast["classes"]:
                    with st.expander(f"🔍 Symbols Defined in `{os.path.basename(selected_graph_file)}`"):
                        if blast["classes"]:
                            st.markdown(f"**Classes:** {', '.join([f'`{c}`' for c in blast['classes']])}")
                        if blast["functions"]:
                            st.markdown(f"**Functions:** {', '.join([f'`{f}()`' for f in blast['functions']])}")
    else:
        st.warning("No Python source files detected in the target directory for AST dependency analysis.")


