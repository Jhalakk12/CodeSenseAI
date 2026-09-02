import sys
import os

# Add sample_repo to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sample_repo")))

from auth.jwt_handler import create_access_token, verify_token  # noqa: E402
from database.connection import DatabasePool  # noqa: E402
from services.deployment_service import DeploymentManager  # noqa: E402


def test_jwt_create_and_verify():
    token = create_access_token({"sub": "testuser", "role": "admin"})
    assert token is not None
    payload = verify_token(token)
    assert payload["sub"] == "testuser"
    assert payload["role"] == "admin"


def test_database_connection_pool():
    pool = DatabasePool(max_connections=2, timeout=1.0)
    conn1 = pool.acquire_connection()
    conn2 = pool.acquire_connection()
    assert conn1["status"] == "busy"
    assert conn2["status"] == "busy"

    # Release connection back
    pool.release_connection(conn1)
    assert conn1["status"] == "idle"


def test_deployment_manager_health_and_deploy():
    deployer = DeploymentManager(environment="test")
    record = deployer.trigger_deployment(commit_sha="abc1234", service_name="auth-service")
    assert record["status"] == "deployed"
    assert record["commit"] == "abc1234"
