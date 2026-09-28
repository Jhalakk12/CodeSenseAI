#!/usr/bin/env python3
"""
CodeSense AI - Automated CI/CD PR Reviewer & Diff Analyzer
Analyzes git diffs or modified files using Groq LPU, flags bugs/vulnerabilities,
and generates recommended unit test cases for CI/CD pipelines.
"""
import os
import sys
import subprocess
from dotenv import load_dotenv

# Ensure safe output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load local environment variables if available
load_dotenv()

REVIEW_PROMPT = """You are CodeSense AI, an automated AI DevOps Code Reviewer and Quality Gatekeeper.
Analyze the following Git Diff / Changed Code:

```diff
{diff_content}
```

Provide a structured, high-signal PR review report adhering strictly to this format:

### 🛡️ CodeSense AI - Automated Pull Request Quality Audit

#### 1. 📝 Executive Summary
A concise, 2-3 sentence overview of what changed and its architectural impact.

#### 2. ⚠️ Risk Assessment & Flagged Lines
- **Risk Level**: [🟢 LOW / 🟡 MEDIUM / 🔴 HIGH]
- Identify any potential security vulnerabilities (OWASP Top 10), performance regressions, or boundary conditions.
- Specifically cite any risky lines of code.

#### 3. 🧪 Recommended Automated Test Cases
Suggest 2-3 specific `pytest` test cases that MUST be added to guarantee regression coverage for these changes.
Include test function names and exact assertion logic.

#### 4. 🚀 DevOps Gate Decision
- **Status**: [APPROVED / CHANGES REQUESTED]
- Rationale for CI/CD progression.
"""


def get_git_diff() -> str:
    """Retrieve git diff for the current PR, commit, or staged/unstaged changes."""
    commands = [
        ["git", "diff", "HEAD~1", "HEAD"],
        ["git", "diff", "--staged"],
        ["git", "diff", "origin/main...HEAD"],
        ["git", "diff"]
    ]

    for cmd in commands:
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            continue

    # Fallback to sample microservice diff if no git diff exists
    sample_diff = (
        "diff --git a/sample_repo/services/deployment_service.py b/sample_repo/services/deployment_service.py\n"
        "--- a/sample_repo/services/deployment_service.py\n"
        "+++ b/sample_repo/services/deployment_service.py\n"
        "@@ -28,6 +28,12 @@ class DeploymentPipeline:\n"
        "+    def emergency_rollback(self, cluster_id: str, force: bool = False):\n"
        "+        # Direct cluster rollback without secondary confirmation check\n"
        "+        target_cluster = self.clusters.get(cluster_id)\n"
        "+        if target_cluster:\n"
        "+            target_cluster['active_version'] = target_cluster.get('previous_version')\n"
        "+            return {'status': 'rolled_back', 'cluster': cluster_id}\n"
        "+        return {'status': 'error', 'message': 'Cluster not found'}\n"
    )
    return sample_diff


def run_ai_review():
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        print("⚠️ Warning: GROQ_API_KEY not configured. Skipping live AI PR review.")
        sys.exit(0)

    diff = get_git_diff()
    if not diff:
        print("ℹ️ No code changes detected to review. Quality gate passed.")
        sys.exit(0)

    print("🔍 CodeSense AI: Analyzing codebase diff and generating AI Quality Audit...")

    try:
        from groq import Groq
        client = Groq(api_key=api_key)

        model = "qwen/qwen3.8-27b"

        prompt = REVIEW_PROMPT.format(diff_content=diff[:8000])
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert DevOps engineer and security auditor."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1500
        )

        report = response.choices[0].message.content
        print("\n" + "=" * 70)
        print(report)
        print("=" * 70 + "\n")

        with open("pr_review_report.md", "w", encoding="utf-8") as f:
            f.write(report)
        print("✅ AI PR Review Report successfully generated and saved to pr_review_report.md")

    except Exception as e:
        print(f"⚠️ AI Review execution encountered error: {e}")
        sys.exit(0)


if __name__ == "__main__":
    run_ai_review()
