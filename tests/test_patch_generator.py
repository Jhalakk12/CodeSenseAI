"""
Unit tests for Feature 3: Automated PR Auto-Remediation & Patch Generator (Sweep.dev Pattern).
Validates unified diff creation, code extraction, atomic file patching, and rollback resilience.
"""
import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.patch_generator import (
    PatchGenerator,
    generate_unified_patch,
    extract_code_block
)


def test_generate_unified_patch():
    """Verify that generate_unified_patch creates valid git-compatible unified diff syntax."""
    original = "def add(a, b):\n    return a - b\n"
    remediated = "def add(a, b):\n    return a + b\n"
    diff = generate_unified_patch(original, remediated, "math_utils.py")

    assert "diff --git a/math_utils.py b/math_utils.py" in diff
    assert "--- a/math_utils.py" in diff
    assert "+++ b/math_utils.py" in diff
    assert "-    return a - b" in diff
    assert "+    return a + b" in diff


def test_generate_unified_patch_no_changes():
    """Verify that identical code returns an empty diff string."""
    code = "def identity(x):\n    return x\n"
    diff = generate_unified_patch(code, code, "test.py")
    assert diff == ""


def test_extract_code_block():
    """Verify markdown code block extraction strips conversational preamble and fences."""
    raw_llm_output = (
        "Here is the fixed code with proper error handling:\n\n"
        "```python\n"
        "def safe_divide(a, b):\n"
        "    if b == 0:\n"
        "        raise ValueError('Cannot divide by zero')\n"
        "    return a / b\n"
        "```\n\n"
        "Hope this helps!"
    )
    extracted = extract_code_block(raw_llm_output)
    assert extracted.startswith("def safe_divide")
    assert "raise ValueError" in extracted
    assert "```" not in extracted
    assert "Here is the fixed code" not in extracted


def test_apply_patch_and_rollback():
    """Verify atomic patching with .bak backup creation and complete rollback recovery."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = os.path.join(tmp_dir, "service.py")
        original_content = "def process():\n    return 'vulnerable'\n"
        remediated_content = "def process():\n    return 'hardened'\n"

        with open(test_file, "w", encoding="utf-8") as f:
            f.write(original_content)

        # 1. Apply patch
        apply_res = PatchGenerator.apply_patch_to_file(test_file, remediated_content, create_backup=True)
        assert apply_res["status"] == "applied"
        assert os.path.exists(f"{test_file}.bak")

        # Verify new content on disk
        with open(test_file, "r", encoding="utf-8") as f:
            assert f.read() == remediated_content

        # 2. Rollback patch
        rollback_res = PatchGenerator.rollback_patch(test_file)
        assert rollback_res["status"] == "rolled_back"
        assert not os.path.exists(f"{test_file}.bak")

        # Verify restored original content
        with open(test_file, "r", encoding="utf-8") as f:
            assert f.read() == original_content


def test_patch_generator_generate_fix_mock():
    """Verify end-to-end generate_fix orchestration with mocked LLM."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = os.path.join(tmp_dir, "auth.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("def login(u, p):\n    return True\n")

        mock_llm_chain = MagicMock()
        mock_llm_chain.invoke.return_value = "```python\ndef login(u, p):\n    if not u or not p:\n        return False\n    return True\n```"

        with patch("scripts.patch_generator.ChatPromptTemplate.from_template") as mock_prompt:
            mock_prompt_inst = MagicMock()
            mock_prompt_inst.__or__.return_value = MagicMock(__or__=MagicMock(return_value=mock_llm_chain))
            mock_prompt.return_value = mock_prompt_inst

            patcher = PatchGenerator()
            res = patcher.generate_fix(
                file_path=test_file,
                issue_description="Add input validation for username and password",
                provider="Groq",
                api_key="mock_key"
            )

            assert res["status"] == "success"
            assert "diff --git" in res["patch_diff"]
            assert "+    if not u or not p:" in res["patch_diff"]
            assert "-    return True" in res["patch_diff"]


def test_patch_generator_failover_to_ollama():
    """Verify that when Groq raises an error, PatchGenerator hot-fails-over to local Ollama."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = os.path.join(tmp_dir, "db.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("def connect():\n    return 'open'\n")

        mock_groq_chain = MagicMock()
        mock_groq_chain.invoke.side_effect = RuntimeError("429 Too Many Requests: Rate limit exceeded")

        mock_fallback_chain = MagicMock()
        mock_fallback_chain.invoke.return_value = "```python\ndef connect():\n    # hardened connection pool\n    return 'safe_pool'\n```"

        with patch("scripts.patch_generator.ChatPromptTemplate.from_template") as mock_prompt:
            mock_prompt_inst = MagicMock()
            # First chain invocation raises 429, second chain invocation returns fallback output
            mock_prompt_inst.__or__.side_effect = [
                MagicMock(__or__=MagicMock(return_value=mock_groq_chain)),
                MagicMock(__or__=MagicMock(return_value=mock_fallback_chain))
            ]
            mock_prompt.return_value = mock_prompt_inst

            mock_engine = MagicMock()
            mock_engine.select_best_fallback_model.return_value = "qwen2.5:1.5b"
            mock_engine._create_ollama_chat.return_value = MagicMock()

            patcher = PatchGenerator(engine=mock_engine)
            res = patcher.generate_fix(
                file_path=test_file,
                issue_description="Fix connection leak",
                provider="Groq",
                api_key="mock_key",
                enable_failover=True
            )

            assert res["status"] == "success"
            assert res["failover"]["triggered"] is True
            assert "Ollama" in res["provider_used"]
            assert "+    return 'safe_pool'" in res["patch_diff"]


def test_cli_execute_remediation():
    """Verify CLI execute_remediation and execute_rollback end-to-end integration."""
    from cli import execute_remediation, execute_rollback

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = os.path.join(tmp_dir, "calc.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("def divide(a, b):\n    return a / b\n")

        with patch.object(PatchGenerator, "generate_fix") as mock_gen:
            mock_gen.return_value = {
                "status": "success",
                "file_path": test_file,
                "remediated_code": "def divide(a, b):\n    if b == 0:\n        raise ZeroDivisionError('Division by zero')\n    return a / b\n",
                "patch_diff": "diff --git a/calc.py b/calc.py\n+    if b == 0:\n",
                "provider_used": "Groq",
                "model_used": "qwen/qwen3.8-27b",
                "failover": {"triggered": False}
            }

            mock_engine = MagicMock()
            # Execute with auto_apply=True
            execute_remediation(mock_engine, "dummy_key", test_file, "Add zero check", auto_apply=True)

            # Check that file was patched and backup created
            assert os.path.exists(f"{test_file}.bak")
            with open(test_file, "r", encoding="utf-8") as f:
                content = f.read()
                assert "ZeroDivisionError" in content

            # Execute rollback
            execute_rollback(test_file)
            assert not os.path.exists(f"{test_file}.bak")
            with open(test_file, "r", encoding="utf-8") as f:
                content = f.read()
                assert "ZeroDivisionError" not in content

