#!/usr/bin/env bash
# ==============================================================================
# CodeSense AI — Rootless Podman Deployment Script (Linux / WSL2)
# ==============================================================================
set -e

echo -e "\033[1;36m============================================================\033[0m"
echo -e "\033[1;36m  CodeSense AI - Rootless Podman Deployment Orchestrator\033[0m"
echo -e "\033[1;36m============================================================\033[0m"

# 1. Verify Podman Installation
if ! command -v podman &> /dev/null; then
    echo -e "\033[1;31m[!] Podman is not installed. Please install podman first.\033[0m"
    echo -e "    On Ubuntu/Debian: sudo apt update && sudo apt install -y podman"
    echo -e "    On Fedora/RHEL:   sudo dnf install -y podman podman-compose"
    exit 1
fi

echo -e "\033[1;32m[✓] Podman Version: $(podman --version)\033[0m"

# 2. Check for Rootless Status
USER_ID=$(id -u)
if [ "$USER_ID" -eq 0 ]; then
    echo -e "\033[1;33m[!] Warning: Running as root. Recommended: Run as unprivileged user for rootless security.\033[0m"
else
    echo -e "\033[1;32m[✓] Verified Rootless Mode: Running as unprivileged UID $USER_ID\033[0m"
fi

# 3. Deploy via podman-compose or podman play kube
if command -v podman-compose &> /dev/null; then
    echo -e "\033[1;34m[+] Launching via podman-compose...\033[0m"
    podman-compose -f podman-compose.yml up -d
else
    echo -e "\033[1;33m[*] podman-compose not found. Using native 'podman play kube'...\033[0m"
    podman play kube podman-k8s.yaml
fi

sleep 3
echo -e "\n\033[1;32m[✓] Active Podman Containers:\033[0m"
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo -e "\n\033[1;36m============================================================\033[0m"
echo -e "\033[1;32m  CodeSense AI is live on Rootless Podman!\033[0m"
echo -e "\033[1;33m  Streamlit UI: http://localhost:8501\033[0m"
echo -e "\033[1;33m  Ollama Node:  http://localhost:11434\033[0m"
echo -e "\033[1;36m============================================================\033[0m"

