import time
from typing import Dict, Any, List, Optional

class DatabasePool:
    """
    Manages database connection pooling and query execution.
    """
    def __init__(self, max_connections: int = 10, timeout: float = 5.0):
        self.max_connections = max_connections
        self.timeout = timeout
        self._pool: List[Dict[str, Any]] = []
        self._active_connections = 0
        self._initialize_pool()

    def _initialize_pool(self):
        for i in range(self.max_connections):
            self._pool.append({"id": f"conn_{i}", "status": "idle", "created_at": time.time()})

    def acquire_connection(self) -> Dict[str, Any]:
        """
        Acquires an idle connection from the pool.
        Raises TimeoutError if all connections are busy.
        """
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            for conn in self._pool:
                if conn["status"] == "idle":
                    conn["status"] = "busy"
                    self._active_connections += 1
                    return conn
            time.sleep(0.1)
        raise TimeoutError("Database connection pool exhausted")

    def release_connection(self, conn: Dict[str, Any]):
        """
        Releases a connection back to the pool.
        """
        for item in self._pool:
            if item["id"] == conn["id"]:
                item["status"] = "idle"
                self._active_connections -= 1
                return
        raise ValueError("Attempted to release an unknown connection")

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Executes a SQL query safely using connection pooling.
        """
        conn = self.acquire_connection()
        try:
            # Simulate DB query execution
            time.sleep(0.05)
            return [{"status": "success", "query": query, "rows_affected": 1}]
        finally:
            self.release_connection(conn)

db_pool = DatabasePool(max_connections=5)
