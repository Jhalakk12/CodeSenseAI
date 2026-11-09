"""
Unit tests for Feature 3: Mobile DevOps Approval Portal (Human-in-the-Loop HITL Gatekeeping)
Validates pending queue ingestion, mobile approval resolution, atomic file modification,
and audit actor accountability.
"""

import os
import tempfile
import pytest
from scripts.audit_logger import AuditLogger


def test_pending_patches_queue():
    """Verify that newly generated AI patches enter the pending approval queue."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = os.path.join(tmp_dir, "test_approval.db")
        logger = AuditLogger(db_path=db_file)

        patch_id = logger.log_patch(
            target_file="sample_repo/auth/jwt_handler.py",
            issue_description="Add token expiry check",
            provider_used="Groq",
            model_used="qwen/qwen3.8-27b",
            patch_diff="--- a/jwt_handler.py\n+++ b/jwt_handler.py",
            remediated_code="def new_code(): pass\n",
            status="PENDING_APPROVAL"
        )
        assert patch_id is not None

        pending = logger.get_pending_patches()
        assert len(pending) == 1
        assert pending[0]["id"] == patch_id
        assert pending[0]["status"] == "PENDING_APPROVAL"
        assert pending[0]["issue_description"] == "Add token expiry check"


def test_resolve_patch_approve_applies_file_and_logs():
    """Verify that approving a patch via mobile portal modifies file on disk and records HITL actor."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = os.path.join(tmp_dir, "test_approval.db")
        logger = AuditLogger(db_path=db_file)

        # Create target code file
        code_file = os.path.join(tmp_dir, "service.py")
        original_code = "def insecure(): return 'vulnerable'\n"
        remediated_code = "def insecure(): return 'hardened'\n"
        with open(code_file, "w", encoding="utf-8") as f:
            f.write(original_code)

        # Queue pending patch
        patch_id = logger.log_patch(
            target_file=code_file,
            issue_description="Harden insecure endpoint",
            provider_used="Groq",
            model_used="qwen/qwen3.8-27b",
            patch_diff="@@ -1 +1 @@\n-def insecure(): return 'vulnerable'\n+def insecure(): return 'hardened'",
            remediated_code=remediated_code,
            status="PENDING_APPROVAL"
        )

        # Execute mobile approval
        res = logger.resolve_patch(
            patch_id=patch_id,
            action="APPROVE",
            actor="Mobile DevOps Portal (HITL)",
            push_to_git=False
        )

        assert res["status"] == "applied"
        assert os.path.exists(f"{code_file}.bak")

        # Verify file content updated
        with open(code_file, "r", encoding="utf-8") as f:
            assert f.read() == remediated_code

        # Verify patch is no longer pending
        pending_after = logger.get_pending_patches()
        assert len(pending_after) == 0

        # Verify audit event has Mobile DevOps actor
        events = logger.get_recent_events(limit=5)
        applied_event = next(e for e in events if e["event_category"] == "PATCH_APPLIED")
        assert applied_event["user_action"] == "Mobile DevOps Portal (HITL)"


def test_resolve_patch_reject():
    """Verify that rejecting a patch leaves file untouched and logs rejection."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = os.path.join(tmp_dir, "test_approval.db")
        logger = AuditLogger(db_path=db_file)

        code_file = os.path.join(tmp_dir, "routes.py")
        original_code = "print('original')\n"
        with open(code_file, "w", encoding="utf-8") as f:
            f.write(original_code)

        patch_id = logger.log_patch(
            target_file=code_file,
            issue_description="Suboptimal refactor",
            provider_used="Ollama",
            model_used="qwen2.5-coder:1.5b",
            patch_diff="@@ -1 +1 @@\n-original\n+bad",
            remediated_code="print('bad')\n",
            status="PENDING_APPROVAL"
        )

        # Reject from mobile
        res = logger.resolve_patch(
            patch_id=patch_id,
            action="REJECT",
            actor="Mobile DevOps Portal (HITL)"
        )
        assert res["status"] == "rejected"

        # File must remain untouched
        with open(code_file, "r", encoding="utf-8") as f:
            assert f.read() == original_code
        assert not os.path.exists(f"{code_file}.bak")

        # Verify rejection logged
        events = logger.get_recent_events(limit=5)
        reject_event = next(e for e in events if e["event_category"] == "PATCH_REJECTED")
        assert reject_event["user_action"] == "Mobile DevOps Portal (HITL)"

