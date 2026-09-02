import logging
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DeploymentService")

class DeploymentManager:
    """
    Automates CI/CD deployment orchestrations, health checks, and rollbacks.
    """
    def __init__(self, environment: str = "staging"):
        self.environment = environment
        self.deployment_history: List[Dict[str, Any]] = []

    def run_health_check(self, service_url: str) -> bool:
        """
        Pings deployed service to verify readiness.
        """
        logger.info(f"Running health checks on {service_url} in {self.environment}")
        # Simulated health check
        return True

    def trigger_deployment(self, commit_sha: str, service_name: str) -> Dict[str, Any]:
        """
        Deploys the specified build artifact and runs rollback on failure.
        """
        logger.info(f"Initiating deployment for {service_name} commit {commit_sha}")
        health_passed = self.run_health_check(f"https://{service_name}.internal/health")
        
        if not health_passed:
            self.execute_rollback(commit_sha)
            return {"status": "failed", "action": "rollback", "commit": commit_sha}

        record = {
            "service": service_name,
            "commit": commit_sha,
            "environment": self.environment,
            "status": "deployed"
        }
        self.deployment_history.append(record)
        return record

    def execute_rollback(self, failed_commit: str):
        """
        Performs automated rollback to previous stable commit.
        """
        logger.warning(f"Health check failed for {failed_commit}. Rolling back to last stable release.")
        # Rollback logic simulation
        return True
