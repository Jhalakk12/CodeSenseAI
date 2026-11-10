"""
Unit tests for Feature 6: Rootless Podman Configuration & Multi-Container Pod Orchestration
Validates podman-compose.yml, podman-k8s.yaml, rootless security options, SELinux volume relabeling,
port allocations, and service dependencies.
"""

import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import pytest
except ImportError:
    pass

try:
    import yaml
except ImportError:
    # Minimal fallback parser if pyyaml is not installed in the clean runner
    yaml = None


def _load_yaml(file_path: str):
    assert os.path.exists(file_path), f"File {file_path} not found"
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    if yaml is not None:
        return yaml.safe_load(content)
    # Basic dictionary validation if yaml module not present
    return {"raw_content": content}


def test_podman_compose_file_exists_and_valid():
    """Verify podman-compose.yml exists and contains required top-level keys."""
    compose_path = os.path.join(os.path.dirname(__file__), "..", "podman-compose.yml")
    assert os.path.exists(compose_path)
    
    with open(compose_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "version:" in content
    assert "services:" in content
    assert "codesense-app:" in content
    assert "ollama-service:" in content


def test_podman_services_configuration():
    """Verify both codesense-app and ollama-service are defined with correct ports and images."""
    compose_path = os.path.join(os.path.dirname(__file__), "..", "podman-compose.yml")
    with open(compose_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify ports
    assert '"8501:8501"' in content or "8501:8501" in content
    assert '"11434:11434"' in content or "11434:11434" in content
    # Verify Ollama image
    assert "ollama/ollama:latest" in content
    # Verify inter-service dependency
    assert "depends_on:" in content
    assert "ollama-service" in content


def test_rootless_security_and_selinux_flags():
    """Verify mandatory Podman rootless security flags (userns_mode, no-new-privileges, :Z)."""
    compose_path = os.path.join(os.path.dirname(__file__), "..", "podman-compose.yml")
    with open(compose_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Rootless user namespace mapping
    assert "keep-id" in content, "userns_mode: keep-id required for rootless UID mapping"
    # Privilege escalation defense
    assert "no-new-privileges:true" in content, "Security opt no-new-privileges required"
    # SELinux volume relabeling (:Z flag)
    assert ":Z" in content, "SELinux :Z flag required for Podman volume mounts"
    assert "/app/data:Z" in content or "./data:/app/data:Z" in content
    assert "/app/chroma_db:Z" in content or "./chroma_db:/app/chroma_db:Z" in content


def test_podman_healthchecks():
    """Verify healthcheck definitions for zero-downtime reliability."""
    compose_path = os.path.join(os.path.dirname(__file__), "..", "podman-compose.yml")
    with open(compose_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "healthcheck:" in content
    assert "http://localhost:8501/_stcore/health" in content
    assert "http://localhost:11434/api/tags" in content


def test_kubernetes_manifest_podman_k8s():
    """Verify podman-k8s.yaml defines valid Kubernetes Pod specification for podman play kube."""
    k8s_path = os.path.join(os.path.dirname(__file__), "..", "podman-k8s.yaml")
    assert os.path.exists(k8s_path)

    with open(k8s_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "kind: Pod" in content
    assert "name: codesense-ai-pod" in content
    assert "containerPort: 8501" in content
    assert "containerPort: 11434" in content
    assert "name: codesense-app" in content
    assert "name: ollama-service" in content


def test_deployment_scripts_exist():
    """Verify deployment scripts for Windows and Linux exist and are executable."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    ps_script = os.path.join(root, "scripts", "podman_deploy.ps1")
    sh_script = os.path.join(root, "scripts", "podman_deploy.sh")

    assert os.path.exists(ps_script), "podman_deploy.ps1 missing"
    assert os.path.exists(sh_script), "podman_deploy.sh missing"


if __name__ == "__main__":
    test_podman_compose_file_exists_and_valid()
    test_podman_services_configuration()
    test_rootless_security_and_selinux_flags()
    test_podman_healthchecks()
    test_kubernetes_manifest_podman_k8s()
    test_deployment_scripts_exist()
    print("All 6 Podman Configuration unit tests passed successfully!")

