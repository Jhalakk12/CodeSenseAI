#!/usr/bin/env python3
"""
CodeSense AI - Command Line Interface (CLI)
Provides full terminal-based interaction for codebase indexing, semantic querying,
security audits, automated pytest generation, and AI PR reviews without requiring a GUI.
"""
import os
import sys
import argparse
import warnings
from typing import Optional, List, Dict, Any

# Suppress deprecation notices from underlying LangChain/transformers for clean CLI UX
warnings.filterwarnings("ignore")

# Ensure safe UTF-8 output on all consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from dotenv import load_dotenv
from rag_engine import CodeSenseEngine, check_ollama_status

load_dotenv()

ASCII_BANNER = r"""
======================================================================
  ____          _      ____                            _     ___ 
 / ___|___   __| | ___/ ___|  ___ _ __  ___  ___      / \   |_ _|
| |   / _ \ / _` |/ _ \___ \ / _ \ '_ \/ __|/ _ \    / _ \   | | 
| |__| (_) | (_| |  __/___) |  __/ | | \__ \  __/   / ___ \  | | 
 \____\___/ \__,_|\___|____/ \___|_| |_|___/\___|  /_/   \_\___|
      Terminal CLI Assistant & AI DevOps Quality Gate
======================================================================
"""

def print_help():
    print("""
Available CLI Commands:
  index <path>        Index a codebase directory (default: ./sample_repo)
  clone <url> [pat]   Clone and index a public or private GitHub repository
  query <question>    Ask any architecture, logic, or flow question
  security <query>    Run an AI security & vulnerability audit
  test <query>        Generate automated pytest test cases
  engine [provider]   Switch active engine (groq / ollama) or view status
  model <name>        Change active LLM model name
  review              Run automated AI PR Diff quality audit
  status              View ChromaDB vector collection statistics
  help                Display this help message
  exit / quit         Exit the CLI
""")


def get_api_key(required: bool = True) -> str:
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key and required:
        print("\n[!] Error: GROQ_API_KEY not found in environment or .env file.")
        print("    Please set GROQ_API_KEY in your .env file or export GROQ_API_KEY='gsk_...'")
        print("    Or switch to local air-gapped mode using: engine ollama\n")
        sys.exit(1)
    return key


def run_interactive(engine: CodeSenseEngine):
    print(ASCII_BANNER)
    
    # Check Ollama status
    ollama_stat = check_ollama_status()
    ollama_online = ollama_stat.get("running", False)
    installed_models = ollama_stat.get("models", [])

    current_provider = "Groq"
    current_model = "qwen/qwen3.8-27b"
    api_key = os.getenv("GROQ_API_KEY", "").strip()

    if api_key:
        print(" [✓] Engine: ⚡ Groq Cloud LPU (Default: qwen/qwen3.8-27b)")
    else:
        if ollama_online:
            current_provider = "Ollama"
            current_model = installed_models[0] if installed_models else "qwen2.5:1.5b"
            print(f" [✓] GROQ_API_KEY not found; auto-selected 🔒 Local Ollama ({current_model})")
        else:
            print(" [!] GROQ_API_KEY not set and Ollama is offline. Set GROQ_API_KEY or start Ollama.")

    if ollama_online:
        print(f" [✓] Local Ollama Online: localhost:11434 (Installed: {', '.join(installed_models)})")
    else:
        print(" [-] Local Ollama offline (Start 'ollama serve' to enable Air-Gapped mode)")

    print(" [✓] Embeddings: sentence-transformers/all-MiniLM-L6-v2")
    print(" Type 'help' for available commands, or 'exit' to quit.\n")

    while True:
        try:
            prompt_label = f"codesense [{current_provider}:{current_model}]> "
            user_input = input(prompt_label).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting CodeSense AI CLI. Goodbye!")
            break

        if not user_input:
            continue

        parts = user_input.split(" ", 1)
        cmd = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ["exit", "quit", "q"]:
            print("Exiting CodeSense AI CLI. Goodbye!")
            break

        elif cmd in ["help", "h"]:
            print_help()

        elif cmd == "engine":
            if not args:
                print(f"\n[+] Active Engine: {current_provider} (Model: {current_model})")
                print(f"[+] Ollama Status: {'Online' if ollama_online else 'Offline'} (localhost:11434)")
                if installed_models:
                    print(f"[+] Installed Ollama Models: {', '.join(installed_models)}")
                print("    To switch: engine groq  OR  engine ollama\n")
            else:
                arg_lower = args.lower()
                if "groq" in arg_lower:
                    current_provider = "Groq"
                    current_model = "qwen/qwen3.8-27b"
                    if not api_key:
                        api_key = get_api_key(required=False)
                    print(f" [✓] Switched to ⚡ Groq Cloud LPU ({current_model})\n")
                elif "ollama" in arg_lower or "local" in arg_lower:
                    current_provider = "Ollama"
                    current_model = installed_models[0] if installed_models else "qwen2.5:1.5b"
                    print(f" [✓] Switched to 🔒 Local Air-Gapped Ollama ({current_model})\n")
                else:
                    print(f" [!] Unknown engine '{args}'. Available: groq, ollama\n")

        elif cmd == "model":
            if not args:
                print(f"\n[+] Current Model: {current_model}\n")
            else:
                current_model = args.strip()
                print(f" [✓] Model set to: {current_model}\n")

        elif cmd in ["clone", "index-git"]:
            if not args:
                print("[!] Please provide a repository URL. Example: clone https://github.com/org/repo [token]\n")
                continue
            parts = args.split(" ")
            git_url = parts[0].strip()
            git_token = parts[1].strip() if len(parts) > 1 else (os.getenv("GITHUB_PAT") or os.getenv("GITHUB_TOKEN") or "")
            execute_clone_and_index(engine, git_url, git_token)

        elif cmd == "index":
            target = args if args else "./sample_repo"
            print(f"\n[*] Scanning and indexing codebase at: {target} ...")
            try:
                stats = engine.index_codebase(target)
                print(f" [✓] Successfully indexed {stats['indexed_files']} files into {stats['total_chunks']} AST chunks.")
                print(f" [✓] Files indexed: {', '.join(stats['files'])}\n")
            except Exception as e:
                print(f" [!] Indexing failed: {e}\n")

        elif cmd == "status":
            try:
                count = engine.vector_store._collection.count()
                print(f"\n[+] Vector Store Persist Dir: {engine.persist_dir}")
                print(f"[+] Total Chunks in ChromaDB: {count}")
                print(f"[+] Active Engine: {current_provider} ({current_model})\n")
            except Exception as e:
                print(f"\n[!] Could not retrieve stats: {e}\n")

        elif cmd in ["query", "ask"]:
            if not args:
                print("[!] Please specify a question. Example: query How does authentication work?\n")
                continue
            execute_query(engine, api_key, args, task_mode="general", provider=current_provider, model_name=current_model)

        elif cmd in ["security", "audit"]:
            question = args if args else "Identify security vulnerabilities, SQL injection, or unhandled exceptions in the codebase."
            execute_query(engine, api_key, question, task_mode="security", provider=current_provider, model_name=current_model)

        elif cmd in ["test", "tests"]:
            question = args if args else "Generate comprehensive pytest test cases covering critical logic and error handling."
            execute_query(engine, api_key, question, task_mode="testing", provider=current_provider, model_name=current_model)

        elif cmd == "review":
            print("\n[*] Triggering automated AI PR Diff Reviewer...")
            try:
                from scripts.ai_pr_reviewer import run_ai_review
                run_ai_review()
            except Exception as e:
                print(f"[!] PR Review failed: {e}\n")

        else:
            # If no command prefix matches, treat entire input as a query
            execute_query(engine, api_key, user_input, task_mode="general", provider=current_provider, model_name=current_model)


def execute_query(
    engine: CodeSenseEngine,
    api_key: str,
    question: str,
    task_mode: str = "general",
    provider: str = "Groq",
    model_name: Optional[str] = None,
    enable_failover: bool = True
):
    if not model_name:
        model_name = "qwen/qwen3.8-27b" if provider.lower() == "groq" else "qwen2.5:1.5b"
    
    prov_display = "⚡ Groq Cloud LPU" if provider.lower() == "groq" else "🔒 Local Ollama"
    print(f"\n[*] Searching vector store and querying {prov_display} [{model_name}] ({task_mode} mode)...")
    try:
        response = engine.query_codebase(
            query=question,
            api_key=api_key if provider.lower() == "groq" else None,
            model_name=model_name,
            provider=provider,
            task_mode=task_mode,
            max_tokens=600,
            enable_failover=enable_failover
        )

        failover = response.get("failover")
        if failover and failover.get("triggered"):
            print(f"\n[!] ⚠️  Automatic Local Failover Triggered:")
            print(f"    {failover.get('reason')}\n")

        provider_label = response.get("provider_used", provider)
        model_label = response.get("model_used", model_name)
        print("\n" + "=" * 70)
        print(f"  CodeSense AI Response [{provider_label} • {model_label}]:")
        print("=" * 70)
        print(response.get("answer", "").strip())
        print("=" * 70)

        citations = response.get("citations", [])
        if citations:
            print("\n📚 Citations & Source Chunks:")
            for idx, cite in enumerate(citations, 1):
                src = cite.get("source", "Unknown")
                score = cite.get("score", 0.0)
                print(f"  [{idx}] {src} (similarity distance: {score})")
        print()

    except Exception as e:
        print(f"\n[!] Query execution failed: {e}\n")


def execute_clone_and_index(engine: CodeSenseEngine, git_url: str, git_token: str = ""):
    import subprocess
    repo_name = git_url.rstrip("/").split("/")[-1].replace(".git", "") if git_url else "repo"
    target_path = os.path.join(os.getcwd(), "cloned_repos", repo_name)
    os.makedirs(os.path.join(os.getcwd(), "cloned_repos"), exist_ok=True)
    
    clean_url = git_url.strip()
    if git_token:
        token = git_token.strip()
        if "github.com" in clean_url:
            repo_part = clean_url.split("github.com")[-1].lstrip("/:")
            if not repo_part.endswith(".git"):
                repo_part += ".git"
            auth_clone_url = f"https://x-access-token:{token}@github.com/{repo_part}"
        else:
            auth_clone_url = clean_url.replace("https://", f"https://x-access-token:{token}@")
        print(f"\n[*] Cloning private repository `{git_url}` using authenticated PAT...")
    else:
        auth_clone_url = clean_url
        print(f"\n[*] Cloning repository `{git_url}` (shallow clone)...")

    clone_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    git_base_cmd = ["git", "-c", "credential.helper="]

    if not os.path.exists(target_path):
        res = subprocess.run(
            git_base_cmd + ["clone", "--depth", "1", auth_clone_url, target_path],
            capture_output=True,
            text=True,
            timeout=120,
            env=clone_env
        )
        if res.returncode != 0:
            raw_err = res.stderr
            sanitized_err = raw_err
            if git_token.strip():
                sanitized_err = sanitized_err.replace(git_token.strip(), "******")
            err_lower = raw_err.lower()
            if not git_token and any(kw in err_lower for kw in ["could not read username", "terminal prompts disabled", "authentication failed", "repository not found"]):
                print(f" [!] 🔒 Authentication Required: Repository appears to be private.")
                print(f"     Please provide a GitHub PAT: clone <url> <pat_token>\n")
            else:
                print(f" [!] Clone failed: {sanitized_err}\n")
            return
        # Security: Scrub token from git remote config so credentials never persist on disk
        subprocess.run(["git", "-C", target_path, "remote", "set-url", "origin", clean_url], capture_output=True)
        print(f" [✓] Cloned successfully into {target_path}")
    else:
        print(f" [*] Using cached clone at: {target_path}")

    print(f"[*] Indexing AST code vectors into ChromaDB...")
    try:
        stats = engine.index_codebase(target_path)
        print(f" [✓] Successfully indexed {stats['indexed_files']} files into {stats['total_chunks']} AST chunks.")
        print(f" [✓] Files indexed: {', '.join(stats['files'])}\n")
    except Exception as e:
        print(f" [!] Indexing failed: {e}\n")


def main():
    parser = argparse.ArgumentParser(description="CodeSense AI - Terminal Command Line Interface (CLI)")
    subparsers = parser.add_subparsers(dest="command", help="CLI Subcommands")

    # clone subcommand
    p_clone = subparsers.add_parser("clone", help="Clone and index a public or private GitHub repository")
    p_clone.add_argument("url", help="GitHub repository URL")
    p_clone.add_argument("--pat", "--token", dest="token", default="", help="Optional GitHub Personal Access Token for private repos")

    # index subcommand
    p_index = subparsers.add_parser("index", help="Index a codebase directory")
    p_index.add_argument("path", nargs="?", default="./sample_repo", help="Path to directory (default: ./sample_repo)")

    # query subcommand
    p_query = subparsers.add_parser("query", help="Ask a question about the indexed codebase")
    p_query.add_argument("question", help="The question to ask")

    # security subcommand
    p_sec = subparsers.add_parser("security", help="Run a security vulnerability audit")
    p_sec.add_argument("question", nargs="?", default="Audit codebase for security vulnerabilities and injection risks", help="Optional query prompt")

    # test subcommand
    p_test = subparsers.add_parser("test", help="Generate automated unit test cases")
    p_test.add_argument("question", nargs="?", default="Generate unit tests for this codebase", help="Optional test generation prompt")

    # Add shared provider and model arguments to query, security, and test subparsers
    for p in [p_query, p_sec, p_test]:
        p.add_argument("--provider", "--engine", dest="provider", default="Groq", help="LLM inference provider (Groq or Ollama, default: Groq)")
        p.add_argument("--model", dest="model", default=None, help="Model name (default: qwen/qwen3.8-27b for Groq, qwen2.5:1.5b for Ollama)")
        p.add_argument("--no-failover", action="store_true", help="Disable automatic failover to local Ollama on Groq rate limits")

    # review subcommand
    subparsers.add_parser("review", help="Run AI PR Review on git diff")

    # status subcommand
    subparsers.add_parser("status", help="Show vector index statistics")

    args = parser.parse_args()
    engine = CodeSenseEngine()

    if not args.command:
        # Interactive REPL mode
        run_interactive(engine)
    elif args.command == "clone":
        token = args.token or os.getenv("GITHUB_PAT") or os.getenv("GITHUB_TOKEN") or ""
        execute_clone_and_index(engine, args.url, token)
    elif args.command == "index":
        print(f"[*] Indexing codebase at: {args.path} ...")
        stats = engine.index_codebase(args.path)
        print(f"[✓] Successfully indexed {stats['indexed_files']} files ({stats['total_chunks']} chunks).")
    elif args.command == "status":
        count = engine.vector_store._collection.count()
        print(f"[+] Total Chunks in ChromaDB: {count}")
    elif args.command == "query":
        api_key = get_api_key(required=(args.provider.lower() == "groq"))
        execute_query(engine, api_key, args.question, task_mode="general", provider=args.provider, model_name=args.model, enable_failover=not args.no_failover)
    elif args.command == "security":
        api_key = get_api_key(required=(args.provider.lower() == "groq"))
        execute_query(engine, api_key, args.question, task_mode="security", provider=args.provider, model_name=args.model, enable_failover=not args.no_failover)
    elif args.command == "test":
        api_key = get_api_key(required=(args.provider.lower() == "groq"))
        execute_query(engine, api_key, args.question, task_mode="testing", provider=args.provider, model_name=args.model, enable_failover=not args.no_failover)
    elif args.command == "review":
        from scripts.ai_pr_reviewer import run_ai_review
        run_ai_review()


if __name__ == "__main__":
    main()
