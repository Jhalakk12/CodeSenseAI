import os
import time
import tempfile
import pytest
from scripts.codebase_watcher import CodebaseWatcher, CodebaseEventHandler


def test_watchdog_starts_and_stops():
    with tempfile.TemporaryDirectory() as tmp_dir:
        watcher = CodebaseWatcher(watch_dir=tmp_dir)
        assert watcher.start() is True
        assert watcher.is_running is True
        status = watcher.get_status()
        assert status["is_running"] is True
        assert status["watch_dir"] == os.path.abspath(tmp_dir)

        watcher.stop()
        assert watcher.is_running is False


def test_watchdog_event_trigger_on_file_creation_and_modification():
    with tempfile.TemporaryDirectory() as tmp_dir:
        events_received = []

        def test_callback(event_type, path):
            events_received.append((event_type, os.path.basename(path)))

        watcher = CodebaseWatcher(
            watch_dir=tmp_dir,
            on_change=test_callback,
            debounce_seconds=0.1
        )
        assert watcher.start() is True
        time.sleep(0.2)

        # Create a new Python file
        test_py = os.path.join(tmp_dir, "test_module.py")
        with open(test_py, "w", encoding="utf-8") as f:
            f.write("def hello(): return 'world'\n")

        # Give watchdog event loop time to capture
        time.sleep(0.5)

        # Modify the Python file
        with open(test_py, "a", encoding="utf-8") as f:
            f.write("# comment\n")

        time.sleep(0.5)
        watcher.stop()

        # Check that events were captured
        assert len(events_received) >= 1
        recorded_files = [fname for _, fname in events_received]
        assert "test_module.py" in recorded_files


def test_watchdog_ignores_bak_and_pycache_files():
    handler = CodebaseEventHandler(callback=lambda ev, p: None)
    
    # Should ignore backup and cache files
    assert handler._should_ignore("sample_repo/auth/jwt_handler.py.bak") is True
    assert handler._should_ignore("sample_repo/__pycache__/routes.cpython-312.pyc") is True
    assert handler._should_ignore(".git/index") is True
    assert handler._should_ignore(".venv/Scripts/python.exe") is True

    # Should NOT ignore valid source code files
    assert handler._should_ignore("sample_repo/auth/jwt_handler.py") is False
    assert handler._should_ignore("sample_repo/api/routes.js") is False


def test_watchdog_switch_directory():
    with tempfile.TemporaryDirectory() as dir1, tempfile.TemporaryDirectory() as dir2:
        events = []
        watcher = CodebaseWatcher(watch_dir=dir1, on_change=lambda t, p: events.append(os.path.basename(p)), debounce_seconds=0.1)
        assert watcher.start() is True
        assert watcher.watch_dir == os.path.abspath(dir1)

        # Switch to dir2
        watcher.set_watch_dir(dir2)
        assert watcher.watch_dir == os.path.abspath(dir2)
        assert watcher.is_running is True

        time.sleep(0.2)
        new_file = os.path.join(dir2, "switched.py")
        with open(new_file, "w", encoding="utf-8") as f:
            f.write("x = 1\n")

        time.sleep(0.5)
        watcher.stop()
        assert "switched.py" in events


def test_watchdog_content_hash_ignores_metadata_touches():
    with tempfile.TemporaryDirectory() as tmp_dir:
        events = []
        watcher = CodebaseWatcher(watch_dir=tmp_dir, on_change=lambda t, p: events.append(t), debounce_seconds=0.05)
        assert watcher.start() is True
        time.sleep(0.1)

        test_file = os.path.join(tmp_dir, "code.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("def foo(): return 42\n")

        time.sleep(0.3)
        initial_events_count = len(events)
        assert initial_events_count >= 1

        # Simulate metadata/timestamp touch without changing content (e.g. OneDrive cloud sync)
        os.utime(test_file, (time.time() + 10, time.time() + 10))
        time.sleep(0.3)

        watcher.stop()
        # Events count should NOT increase because file hash is unchanged!
        assert len(events) == initial_events_count



