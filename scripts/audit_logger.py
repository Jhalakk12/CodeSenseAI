"""
CodeSense AI - Persistent DevOps Audit History & Compliance Database
Manages persistent SQLite logging for WatchDog events, automated code remediations,
patch applications, rollbacks, and developer queries. Ensures zero data loss across reboots.
"""

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "codesense_audit.db")


class AuditLogger:
    """
    Thread-safe SQLite manager implementing write-ahead logging (WAL)
    for high-concurrency event ingestion across WatchDog and UI threads.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    @classmethod
    def get_instance(cls, db_path: str = DEFAULT_DB_PATH) -> "AuditLogger":
        """Singleton accessor for application-wide persistent logging."""
        with cls._lock:
            if cls._instance is None or cls._instance.db_path != os.path.abspath(db_path):
                cls._instance = cls(db_path)
            return cls._instance

    @contextmanager
    def _get_connection(self):
        """Creates a thread-safe connection with WAL mode and ensures connection is closed."""
        conn = sqlite3.connect(self.db_path, timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Initializes relational tables and performance indexes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Audit Events Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_category TEXT NOT NULL,
                target_repo TEXT,
                target_file TEXT,
                details TEXT,
                status TEXT NOT NULL,
                user_action TEXT DEFAULT 'System'
            );
            """)

            # 2. Patch & Auto-Remediation History Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS patch_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                target_file TEXT NOT NULL,
                issue_description TEXT,
                provider_used TEXT,
                model_used TEXT,
                patch_diff TEXT,
                status TEXT NOT NULL,
                backup_path TEXT
            );
            """)

            # Fast query indexes for UI dashboards
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_category ON audit_events(event_category);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_patch_timestamp ON patch_history(timestamp DESC);")
            conn.commit()

    def _normalize_path_and_repo(self, target_file: Optional[str], target_repo: Optional[str]):
        """Normalizes absolute Windows paths into clean relative repo paths with forward slashes."""
        if not target_file:
            return target_file, os.path.basename(target_repo) if target_repo else "default"

        norm_file = os.path.normpath(target_file).replace("\\", "/")
        if not target_repo or target_repo.lower() == "default":
            if "sample_repo" in norm_file:
                target_repo = "sample_repo"
                idx = norm_file.find("sample_repo")
                rel_file = norm_file[idx + len("sample_repo") + 1:]
                return rel_file, target_repo
            elif "cloned_repos" in norm_file:
                parts = norm_file.split("/")
                if "cloned_repos" in parts:
                    c_idx = parts.index("cloned_repos")
                    if c_idx + 1 < len(parts):
                        target_repo = parts[c_idx + 1]
                        rel_file = "/".join(parts[c_idx + 2:])
                        return rel_file, target_repo

        repo_name = os.path.basename(target_repo) if target_repo else "default"
        return norm_file, repo_name

    def log_event(
        self,
        event_category: str,
        target_repo: Optional[str] = None,
        target_file: Optional[str] = None,
        details: Optional[str] = None,
        status: str = "SUCCESS",
        user_action: str = "System",
        timestamp: Optional[str] = None
    ) -> int:
        """
        Logs a DevOps event into persistent storage.
        Categories: WATCHDOG_SYNC, PATCH_GENERATED, PATCH_APPLIED, PATCH_ROLLED_BACK, QUERY_EXECUTED
        """
        ts = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        clean_file, repo_name = self._normalize_path_and_repo(target_file, target_repo)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_events (timestamp, event_category, target_repo, target_file, details, status, user_action)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ts, event_category, repo_name, clean_file, details, status, user_action))
            conn.commit()
            return cursor.lastrowid

    def log_patch(
        self,
        target_file: str,
        issue_description: str,
        provider_used: str,
        model_used: str,
        patch_diff: str,
        status: str = "GENERATED",
        backup_path: Optional[str] = None,
        timestamp: Optional[str] = None
    ) -> int:
        """Logs an AI-generated patch and also writes an audit event record."""
        ts = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        clean_file, repo_name = self._normalize_path_and_repo(target_file, None)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO patch_history (timestamp, target_file, issue_description, provider_used, model_used, patch_diff, status, backup_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (ts, clean_file, issue_description, provider_used, model_used, patch_diff, status, backup_path))
            patch_id = cursor.lastrowid
            conn.commit()

        # Mirror into general audit events
        self.log_event(
            event_category="PATCH_GENERATED",
            target_repo=repo_name,
            target_file=clean_file,
            details=f"Provider: {provider_used} | Model: {model_used} | Issue: {issue_description[:60]}...",
            status="SUCCESS",
            user_action="AI Auto-Remediation",
            timestamp=ts
        )
        return patch_id

    def update_patch_status(self, patch_id: int, new_status: str):
        """Updates status of a patch record (e.g. APPLIED, ROLLED_BACK)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE patch_history SET status = ? WHERE id = ?
            """, (new_status, patch_id))
            conn.commit()

    def get_recent_events(
        self,
        limit: int = 50,
        category: Optional[str] = None,
        repo: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieves recent audit events with optional category and repository filtering."""
        query = "SELECT * FROM audit_events WHERE 1=1"
        params = []

        if category and category.upper() != "ALL":
            query += " AND event_category = ?"
            params.append(category)

        if repo and repo.upper() != "ALL":
            query += " AND target_repo = ?"
            params.append(os.path.basename(repo))

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_patch_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves history of AI-generated patches."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM patch_history ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Calculates quantitative DevOps compliance metrics for UI dashboards."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM audit_events;")
            total_events = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM audit_events WHERE event_category = 'WATCHDOG_SYNC';")
            total_syncs = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM patch_history;")
            total_patches = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM audit_events WHERE event_category = 'PATCH_ROLLED_BACK';")
            total_rollbacks = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT target_repo) FROM audit_events WHERE target_repo IS NOT NULL;")
            unique_repos = cursor.fetchone()[0]

            return {
                "total_events": total_events,
                "total_syncs": total_syncs,
                "total_patches": total_patches,
                "total_rollbacks": total_rollbacks,
                "unique_repos": unique_repos
            }

    def clear_all(self):
        """Purges audit tables (primarily for testing and clean-room evaluations)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM audit_events;")
            cursor.execute("DELETE FROM patch_history;")
            conn.commit()


# CLI Demonstration utility
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CodeSense AI Audit Logger CLI")
    parser.add_argument("--stats", action="store_true", help="Print audit metrics summary")
    parser.add_argument("--recent", type=int, default=10, help="Print N most recent audit events")
    args = parser.parse_args()

    logger = AuditLogger.get_instance()
    metrics = logger.get_metrics_summary()
    print("=" * 60)
    print("📜 CodeSense AI — DevOps Audit & Compliance Database")
    print("=" * 60)
    print(f"Database Location: {logger.db_path}")
    print(f"Total Audit Events : {metrics['total_events']}")
    print(f"WatchDog Syncs     : {metrics['total_syncs']}")
    print(f"Patches Generated  : {metrics['total_patches']}")
    print(f"Rollbacks Executed : {metrics['total_rollbacks']}")
    print("-" * 60)

    events = logger.get_recent_events(limit=args.recent)
    if events:
        print(f"Last {len(events)} Events:")
        for ev in events:
            print(f" [{ev['timestamp']}] {ev['event_category']} | {ev['target_file']} | Status: {ev['status']}")
    else:
        print("No audit events recorded yet.")
