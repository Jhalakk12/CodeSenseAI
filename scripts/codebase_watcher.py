"""
CodeSense AI - Real-Time Codebase WatchDog Daemon
Monitors file system events (created, modified, deleted) across the target codebase.
Automatically triggers incremental/full re-indexing and AST topology updates in real-time.
"""

import os
import sys
import time
import hashlib
import threading
from datetime import datetime
from typing import Callable, Optional, Dict, Any, List

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

# Supported code extensions to track
TRACKED_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".html", ".css", ".json", ".sql"}

# Directory names and patterns to ignore
IGNORED_PATTERNS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    ".pytest_cache",
    ".chroma",
    "chroma_db",
    "node_modules",
    ".bak",
    ".swp",
    ".tmp"
}

# Process-wide re-index lock to serialize ChromaDB operations
_REINDEX_LOCK = threading.Lock()


class CodebaseEventHandler(FileSystemEventHandler):
    """
    Handles file-system events on code files with debouncing logic.
    """

    def __init__(
        self,
        callback: Callable[[str, str], None],
        debounce_seconds: float = 1.5,
        tracked_extensions: Optional[set] = None
    ):
        super().__init__()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.tracked_extensions = tracked_extensions or TRACKED_EXTENSIONS
        self._last_event_time: Dict[str, float] = {}
        self._file_hashes: Dict[str, str] = {}
        self._lock = threading.Lock()

    def _get_file_hash(self, path: str) -> Optional[str]:
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return None

    def initialize_existing_hashes(self, root_dir: str):
        """Scans root_dir on startup so existing files are baseline-hashed and don't trigger startup events."""
        if not os.path.exists(root_dir):
            return
        with self._lock:
            for root, _, files in os.walk(root_dir):
                if any(part.startswith(".") or part in IGNORED_PATTERNS for part in root.split(os.sep)):
                    continue
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in self.tracked_extensions:
                        full_p = os.path.normpath(os.path.join(root, f))
                        h = self._get_file_hash(full_p)
                        if h:
                            self._file_hashes[full_p] = h

    def _should_ignore(self, path: str) -> bool:
        norm_path = os.path.normpath(path)
        parts = norm_path.split(os.sep)
        
        # Check if any path segment contains ignored patterns
        for part in parts:
            if part.startswith(".") and part not in {".", ".."}:
                return True
            if part in IGNORED_PATTERNS:
                return True
            if part.endswith(".bak") or part.endswith(".tmp") or part.endswith(".swp"):
                return True

        ext = os.path.splitext(norm_path)[1].lower()
        if ext not in self.tracked_extensions:
            return True

        return False

    def _debounce_and_dispatch(self, event_type: str, file_path: str):
        if self._should_ignore(file_path):
            return

        norm_path = os.path.normpath(file_path)
        now = time.time()
        with self._lock:
            # 1. Debounce rapid OS flushes
            last_time = self._last_event_time.get(norm_path, 0.0)
            if (now - last_time) < self.debounce_seconds:
                return  # Skip duplicate rapid save events
            self._last_event_time[norm_path] = now

            # 2. Content Hash Verification: ignore metadata/timestamp touches (e.g. OneDrive cloud sync)
            if event_type == "modified":
                current_hash = self._get_file_hash(norm_path)
                if current_hash:
                    last_hash = self._file_hashes.get(norm_path)
                    if last_hash == current_hash:
                        return  # Code content is unchanged; ignore OS metadata touch
                    self._file_hashes[norm_path] = current_hash
            elif event_type == "created":
                current_hash = self._get_file_hash(norm_path)
                if current_hash:
                    self._file_hashes[norm_path] = current_hash
            elif event_type == "deleted":
                self._file_hashes.pop(norm_path, None)

        try:
            self.callback(event_type, file_path)
        except Exception as e:
            print(f"[WatchDog Error] Callback failed for {file_path}: {e}")

    def on_modified(self, event: FileSystemEvent):
        if not event.is_directory:
            self._debounce_and_dispatch("modified", event.src_path)

    def on_created(self, event: FileSystemEvent):
        if not event.is_directory:
            self._debounce_and_dispatch("created", event.src_path)

    def on_deleted(self, event: FileSystemEvent):
        if not event.is_directory:
            self._debounce_and_dispatch("deleted", event.src_path)


class CodebaseWatcher:
    """
    WatchDog daemon orchestrator managing background directory observer threads.
    Ensures safe, non-racing singleton execution across Streamlit reloads.
    """
    _global_instance = None

    def __init__(
        self,
        watch_dir: str = "",
        engine: Optional[Any] = None,
        on_change: Optional[Callable[[str, str], None]] = None,
        debounce_seconds: float = 1.5
    ):
        self.watch_dir = os.path.abspath(watch_dir) if watch_dir else ""
        self.engine = engine
        self.custom_callback = on_change
        self.debounce_seconds = debounce_seconds

        self.observer: Optional[Observer] = None
        self.is_running = False
        self.event_history: List[Dict[str, Any]] = []
        self.last_sync_time: Optional[str] = None
        self.total_events_processed = 0
        self._lock = threading.Lock()

    def set_watch_dir(self, new_dir: str):
        """Switches directory dynamically, restarting observer safely."""
        target_abs = os.path.abspath(new_dir) if new_dir else ""
        if self.watch_dir == target_abs and self.is_running:
            return

        was_running = self.is_running
        self.stop()
        self.watch_dir = target_abs
        if was_running and target_abs:
            self.start()

    def _handle_change_event(self, event_type: str, file_path: str):
        rel_path = os.path.relpath(file_path, self.watch_dir) if self.watch_dir else os.path.basename(file_path)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        event_record = {
            "type": event_type,
            "file": rel_path,
            "full_path": file_path,
            "timestamp": now_str,
            "status": "pending"
        }

        with self._lock:
            self.total_events_processed += 1
            self.last_sync_time = now_str
            self.event_history.insert(0, event_record)
            if len(self.event_history) > 20:
                self.event_history.pop()

        print(f"🐕 [WatchDog] {event_type.upper()}: {rel_path} @ {now_str}")

        # Acquire lock so concurrent file touches do not race ChromaDB
        have_lock = _REINDEX_LOCK.acquire(blocking=False)
        if not have_lock:
            print(f"⏳ [WatchDog] Re-indexing already in progress, safely skipping duplicate event for {rel_path}")
            return

        try:
            # Trigger RAG engine auto-reindex if engine was passed
            if self.engine is not None and hasattr(self.engine, "index_codebase") and self.watch_dir:
                try:
                    start_t = time.time()
                    stats = self.engine.index_codebase(self.watch_dir)
                    latency = round(time.time() - start_t, 3)
                    chunks = stats.get("total_chunks", 0)
                    event_record["status"] = "synced"
                    event_record["chunks"] = chunks
                    event_record["latency"] = f"{latency}s"
                    print(f"✅ [WatchDog] Auto-reindexed {chunks} chunks for {rel_path} in {latency}s")

                    # Log to persistent SQLite database
                    try:
                        from scripts.audit_logger import AuditLogger
                        AuditLogger.get_instance().log_event(
                            event_category="WATCHDOG_SYNC",
                            target_repo=self.watch_dir,
                            target_file=rel_path,
                            details=f"Auto-reindexed {chunks} chunks in {latency}s",
                            status="SUCCESS",
                            user_action="WatchDog Daemon"
                        )
                    except Exception as audit_err:
                        print(f"[WatchDog Audit Warning] Could not persist event: {audit_err}")
                except Exception as e:
                    event_record["status"] = f"error: {str(e)}"
                    print(f"❌ [WatchDog] Reindex failed: {e}")
                    try:
                        from scripts.audit_logger import AuditLogger
                        AuditLogger.get_instance().log_event(
                            event_category="WATCHDOG_SYNC",
                            target_repo=self.watch_dir,
                            target_file=rel_path,
                            details=f"Reindex failed: {str(e)[:100]}",
                            status="ERROR",
                            user_action="WatchDog Daemon"
                        )
                    except Exception:
                        pass

            # Trigger user-defined callback if provided
            if self.custom_callback:
                try:
                    self.custom_callback(event_type, file_path)
                except Exception as e:
                    print(f"[WatchDog] Custom callback error: {e}")
        finally:
            try:
                _REINDEX_LOCK.release()
            except RuntimeError:
                pass

    def start(self) -> bool:
        """Starts the background directory watcher thread."""
        if not self.watch_dir or not os.path.exists(self.watch_dir):
            print(f"❌ [WatchDog] Target path does not exist: {self.watch_dir}")
            return False

        if self.is_running:
            return True

        # Stop any previous global instance running in background
        if CodebaseWatcher._global_instance is not None and CodebaseWatcher._global_instance is not self:
            try:
                CodebaseWatcher._global_instance.stop()
            except Exception:
                pass
        CodebaseWatcher._global_instance = self

        handler = CodebaseEventHandler(
            callback=self._handle_change_event,
            debounce_seconds=self.debounce_seconds
        )
        handler.initialize_existing_hashes(self.watch_dir)

        self.observer = Observer()
        self.observer.schedule(handler, path=self.watch_dir, recursive=True)
        self.observer.daemon = True
        self.observer.start()
        self.is_running = True
        print(f"🐕 [WatchDog Daemon ACTIVE] Watching directory: {self.watch_dir}")
        return True

    def stop(self):
        """Stops the observer thread."""
        if self.observer and self.is_running:
            try:
                self.observer.stop()
                self.observer.join(timeout=2.0)
            except Exception as e:
                print(f"[WatchDog] Stop warning: {e}")
            finally:
                self.is_running = False
                print(f"🛑 [WatchDog Daemon STOPPED] Stopped watching: {self.watch_dir}")

    def get_status(self) -> Dict[str, Any]:
        """Returns health status, active path, and event history for UI/CLI."""
        with self._lock:
            return {
                "is_running": self.is_running,
                "watch_dir": self.watch_dir,
                "total_events": self.total_events_processed,
                "last_sync": self.last_sync_time or "No events yet",
                "recent_events": list(self.event_history[:5])
            }


# Standalone CLI runner for demonstration
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CodeSense AI Real-Time WatchDog Daemon")
    parser.add_argument("--dir", default="sample_repo", help="Target repository directory to monitor")
    parser.add_argument("--debounce", type=float, default=1.0, help="Debounce delay in seconds")
    args = parser.parse_args()

    target = os.path.abspath(args.dir)
    print("=" * 60)
    print("🐕 CodeSense AI — Real-Time WatchDog File Monitor")
    print("=" * 60)
    print(f"Watching: {target}")
    print("Press Ctrl+C to terminate...")

    watcher = CodebaseWatcher(watch_dir=target, debounce_seconds=args.debounce)
    if watcher.start():
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            watcher.stop()
            print("\nWatchDog daemon shut down cleanly.")

