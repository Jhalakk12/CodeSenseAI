import os
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

# Initialize Engine
@st.cache_resource
def get_engine():
    return CodeSenseEngine()

engine = get_engine()

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
                # Only include generative LLMs, exclude whisper audio and guard classifiers
                groq_models = [
                    m.id for m in fetched
                    if not any(k in m.id.lower() for k in ["whisper", "guard", "audio", "embed"])
                ]
            except Exception as err:
                st.caption(f"⚠️ Could not load account models: {err}")

        # Fallback if API key not yet entered or fetch returned empty
        if not groq_models:
            groq_models = [
                "llama3-8b-8192",
                "llama3-70b-8192",
                "mixtral-8x7b-32768",
                "gemma2-9b-it"
            ]

        # Prioritize 8b or 70b general models if present
        default_idx = 0
        for i, m in enumerate(groq_models):
            if "8b" in m.lower() or "70b" in m.lower():
                default_idx = i
                break

        model_name = st.selectbox(
            "Model",
            groq_models,
            index=default_idx,
            help="Live model list detected from your Groq account."
        )
        st.caption(f"Selected: `{model_name}`")
    else:
        model_name = st.text_input("Ollama Model Name", value="deepseek-coder:6.7b")

    st.markdown("---")

    # Codebase Target
    st.subheader("📁 Repository Indexing")
    repo_option = st.radio(
        "Source Codebase",
        ["Built-in Sample Microservice (sample_repo)", "Custom Local Directory"],
        index=0
    )

    if repo_option == "Custom Local Directory":
        target_path = st.text_input("Directory Absolute Path", value=os.getcwd())
    else:
        target_path = os.path.join(os.getcwd(), "sample_repo")

    if st.button("🚀 Index / Re-Index Codebase", use_container_width=True, type="primary"):
        with st.spinner("Analyzing AST, splitting chunks, and generating ChromaDB vectors..."):
            try:
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
    <div style="font-size: 0.85rem; color: #8b949e;">
        <div>🐳 <b>Dockerfile:</b> <span style="color: #3fb950;">Configured</span></div>
        <div>📦 <b>Docker Compose:</b> <span style="color: #3fb950;">Ready</span></div>
        <div>⚙️ <b>CI/CD (GitHub Actions):</b> <span style="color: #3fb950;">Active</span></div>
        <div>📊 <b>Vector Store:</b> <span style="color: #58a6ff;">ChromaDB Persistent</span></div>
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

# Render Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
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
                        task_mode=selected_task
                    )
                    
                    st.markdown(res["answer"])
                    
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
