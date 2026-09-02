"""
FastAPI application routes demonstrating user management and deployment endpoints.
"""
from typing import Dict, Any
from auth.jwt_handler import create_access_token, verify_token
from database.connection import db_pool
from services.deployment_service import DeploymentManager

deployer = DeploymentManager(environment="production")


def handle_login(credentials: Dict[str, str]) -> Dict[str, Any]:
    username = credentials.get("username")
    password = credentials.get("password")

    # In production, compare hashed password against DB
    if username == "devops_admin" and password == "secure_pass_123":
        token = create_access_token({"sub": username, "role": "admin"})
        return {"access_token": token, "token_type": "bearer"}
    return {"error": "Invalid username or password"}


def trigger_deploy_route(token: str, payload: Dict[str, str]) -> Dict[str, Any]:
    user_info = verify_token(token)
    if user_info.get("role") != "admin":
        raise PermissionError("Admin privileges required for trigger_deploy")

    commit_sha = payload.get("commit_sha", "HEAD")
    service_name = payload.get("service_name", "web-api")

    # Execute query to record deployment event
    db_pool.execute_query(f"INSERT INTO audit_log (action, user) VALUES ('deploy', '{user_info['sub']}')")

    result = deployer.trigger_deployment(commit_sha=commit_sha, service_name=service_name)
    return result
