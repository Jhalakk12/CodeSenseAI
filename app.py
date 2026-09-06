import os
import subprocess
import zipfile
import streamlit as st
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

# Initialize Engine with dynamic reload to prevent stale module caching
import importlib
import rag_engine
importlib.reload(rag_engine)
from rag_engine import CodeSenseEngine

engine = CodeSenseEngine()

# --- SIDEBAR: Configuration & DevOps Controls ---
with st.sidebar:
    st.markdown('<span class="header-badge">CSE 4011 • AI DevOps Workflows</span>', unsafe_allow_html=True)
    st.title("⚡ CodeSense AI")
    st.caption("Intelligent Code Assistant & DevOps Pipeline")
    st.markdown("---")

    # API Configuration
    st.subheader("🔑 LLM Configuration")
    provider = st.selectbox("Inference Provider", ["Groq", "Ollama"], index=0)
    
    default_groq_key = os.getenv("GROQ_API_KEY", "")
    api_key = st.text_input(
        "Groq API Key",
        value=default_groq_key,
        type="password",
        placeholder="gsk_...",
        help="Use your existing Groq API key for ultra-fast response times."
    )

    if provider == "Groq":
        groq_models = []
        if api_key:
            try:
                from groq import Groq
                client = Groq(api_key=api_key.strip())
                fetched = client.models.list().data
                # Strictly whitelist proven generative coding & chat model families
                allowed_families = ["qwen", "llama", "mixtral", "gemma", "deepseek"]
                groq_models = [
                    m.id for m in fetched
                    if any(fam in m.id.lower() for fam in allowed_families)
                    and not any(bad in m.id.lower() for bad in ["guard", "whisper", "vision", "embed"])
                ]
            except Exception as err:
                st.caption(f"⚠️ Could not load account models: {err}")

        # Fallback if API key not yet entered or fetch returned empty
        if not groq_models:
            groq_models = [
                "qwen/qwen3.8-27b",
                "llama3-70b-8192",
                "llama3-8b-8192",
                "mixtral-8x7b-32768",
                "gemma2-9b-it"
            ]

        # Pick high-capacity Llama models or Qwen as default
        default_idx = 0
        for i, m in enumerate(groq_models):
            if "llama" in m.lower() and "70b" in m.lower():
                default_idx = i
                break
            elif "llama" in m.lower() and "8b" in m.lower():
                default_idx = i
            elif "qwen" in m.lower() and default_idx == 0:
                default_idx = i

        model_name = st.selectbox(
            "Model",
            groq_models,
            index=default_idx,
            help="Verified generative LLMs available on your Groq account."
        )
        st.caption(f"Selected: `{model_name}`")
    else:
        model_name = st.text_input("Ollama Model Name", value="deepseek-coder:6.7b")

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
    if repo_option == "Custom Local Directory":
        target_path = st.text_input("Directory Absolute Path", value=os.getcwd(), help="Absolute path to any folder on your computer.")
    elif repo_option == "Clone from GitHub URL":
        github_url = st.text_input(
            "GitHub Repository URL",
            value="https://github.com/pallets/flask",
            placeholder="https://github.com/username/repository",
            help="Provide any public GitHub repository to clone and index its AST code vectors."
        )
        repo_name = github_url.rstrip("/").split("/")[-1].replace(".git", "") if github_url else "repo"
        target_path = os.path.join(os.getcwd(), "cloned_repos", repo_name)
    elif repo_option == "Upload Codebase (.ZIP Archive)":
        uploaded_zip = st.file_uploader(
            "Upload Codebase ZIP Archive",
            type=["zip"],
            help="Drag and drop any zipped source code folder."
        )
        if uploaded_zip is not None:
            zip_stem = os.path.splitext(uploaded_zip.name)[0]
            target_path = os.path.join(os.getcwd(), "uploaded_repos", zip_stem)
        else:
            target_path = ""
    else:
        target_path = os.path.join(os.getcwd(), "sample_repo")

    if st.button("🚀 Index / Re-Index Codebase", use_container_width=True, type="primary"):
        with st.spinner("Analyzing codebase and generating ChromaDB vectors..."):
            try:
                if repo_option == "Clone from GitHub URL":
                    if not github_url or not github_url.startswith(("http://", "https://", "git@")):
                        st.error("Please enter a valid GitHub repository URL.")
                        st.stop()
                    os.makedirs(os.path.join(os.getcwd(), "cloned_repos"), exist_ok=True)
                    if not os.path.exists(target_path):
                        st.info(f"Cloning `{github_url}` (shallow clone)...")
                        res = subprocess.run(
                            ["git", "clone", "--depth", "1", github_url.strip(), target_path],
                            capture_output=True,
                            text=True,
                            timeout=120
                        )
                        if res.returncode != 0:
                            st.error(f"Git clone failed: {res.stderr}")
                            st.stop()
                    else:
                        st.info(f"Using cached clone at `{target_path}`. Pulling latest changes...")
                        subprocess.run(["git", "-C", target_path, "pull"], capture_output=True, text=True, timeout=60)

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

# Render Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
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
        st.warning("⚠️ Please provide your Groq API Key in the left sidebar to run the inference.")
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
                        api_key=api_key,
                        model_name=model_name,
                        provider=provider,
                        task_mode=selected_task,
                        max_tokens=600
                    )
                    
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
                        "citations": res["citations"]
                    })
                except Exception as e:
                    st.error(f"Error generating answer: {str(e)}")
