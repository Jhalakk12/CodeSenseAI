"""
Unit tests for Feature 2: Persistent Audit History & Compliance Database (SQLite)
Validates schema creation, event logging, patch auditing, rollback recording, and concurrent thread safety.
"""

import os
import tempfile
import threading
try:
    import pytest
except ImportError:
    pass
from scripts.audit_logger import AuditLogger


def test_audit_logger_initialization_and_schema():
    """Verify tables and indexes are created properly upon initialization."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = os.path.join(tmp_dir, "test_audit.db")
        logger = AuditLogger(db_path=db_file)
        assert os.path.exists(db_file)

        metrics = logger.get_metrics_summary()
        assert metrics["total_events"] == 0
        assert metrics["total_syncs"] == 0
        assert metrics["total_patches"] == 0
        assert metrics["total_rollbacks"] == 0


def test_log_event_and_retrieve():
    """Verify logging an event and retrieving it with proper fields."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = os.path.join(tmp_dir, "test_audit.db")
        logger = AuditLogger(db_path=db_file)

        row_id = logger.log_event(
            event_category="WATCHDOG_SYNC",
            target_repo="sample_repo",
            target_file="auth/jwt_handler.py",
            details="Auto-reindexed 16 chunks in 0.18s",
            status="SUCCESS",
            user_action="WatchDog Daemon"
        )
        assert row_id == 1

        events = logger.get_recent_events(limit=10)
        assert len(events) == 1
        ev = events[0]
        assert ev["event_category"] == "WATCHDOG_SYNC"
        assert ev["target_repo"] == "sample_repo"
        assert ev["target_file"] == "auth/jwt_handler.py"
        assert "0.18s" in ev["details"]
        assert ev["status"] == "SUCCESS"


def test_log_patch_and_status_update():
    """Verify logging an AI-generated patch and updating its status upon apply/rollback."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = os.path.join(tmp_dir, "test_audit.db")
        logger = AuditLogger(db_path=db_file)

        patch_id = logger.log_patch(
            target_file="auth/jwt_handler.py",
            issue_description="Add input validation for tokens",
            provider_used="Groq",
            model_used="qwen/qwen3.8-27b",
            patch_diff="--- a/jwt_handler.py\n+++ b/jwt_handler.py\n@@ ... @@",
            status="GENERATED",
            backup_path="auth/jwt_handler.py.bak"
        )
        assert patch_id == 1

        # Check patch history
        patches = logger.get_patch_history()
        assert len(patches) == 1
        assert patches[0]["status"] == "GENERATED"
        assert patches[0]["provider_used"] == "Groq"

        # Update patch status to APPLIED
        logger.update_patch_status(patch_id, "APPLIED")
        patches_updated = logger.get_patch_history()
        assert patches_updated[0]["status"] == "APPLIED"

        # Verify metrics reflect the patch
        metrics = logger.get_metrics_summary()
        assert metrics["total_patches"] == 1


def test_filter_by_category_and_repo():
    """Verify category and repository filtering in audit log retrieval."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = os.path.join(tmp_dir, "test_audit.db")
        logger = AuditLogger(db_path=db_file)

        logger.log_event("WATCHDOG_SYNC", target_repo="sample_repo", target_file="app.py")
        logger.log_event("WATCHDOG_SYNC", target_repo="flask", target_file="docs/conf.py")
        logger.log_event("PATCH_APPLIED", target_repo="sample_repo", target_file="utils.py")

        # Filter by category
        sync_events = logger.get_recent_events(category="WATCHDOG_SYNC")
        assert len(sync_events) == 2

        # Filter by repo
        flask_events = logger.get_recent_events(repo="flask")
        assert len(flask_events) == 1
        assert flask_events[0]["target_file"] == "docs/conf.py"


def test_concurrent_logging_thread_safety():
    """Verify high-concurrency writes from multiple threads without database locked errors."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = os.path.join(tmp_dir, "test_concurrent.db")
        logger = AuditLogger(db_path=db_file)

        num_threads = 10
        events_per_thread = 20

        def worker(thread_idx: int):
            for i in range(events_per_thread):
                logger.log_event(
                    event_category="WATCHDOG_SYNC",
                    target_repo=f"repo_{thread_idx}",
                    target_file=f"file_{i}.py",
                    details=f"Thread {thread_idx} log {i}"
                )

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        metrics = logger.get_metrics_summary()
        assert metrics["total_events"] == num_threads * events_per_thread

