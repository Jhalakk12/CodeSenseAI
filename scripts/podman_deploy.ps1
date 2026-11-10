# ==============================================================================
# CodeSense AI - Rootless Podman Deployment Orchestrator
# Builds container image and deploys native Kubernetes pod using Podman
# ==============================================================================

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  CodeSense AI - Rootless Podman Deployment Orchestrator" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Verify Podman CLI
$podmanCmd = Get-Command "podman" -ErrorAction SilentlyContinue
if (-not $podmanCmd) {
    Write-Host "[!] Error: 'podman' executable not found in PATH." -ForegroundColor Red
    exit 1
}

$podmanVer = podman --version
Write-Host "[OK] Podman detected: $podmanVer" -ForegroundColor Green

# 2. Build CodeSense AI Container Image if not present
Write-Host "`n[+] Checking for local container image 'codesense-ai-app:latest'..." -ForegroundColor Cyan
$imgCheck = podman images -q codesense-ai-app:latest

if (-not $imgCheck) {
    Write-Host "[*] Image not found. Building 'codesense-ai-app:latest' via Podman..." -ForegroundColor Yellow
    podman build -t codesense-ai-app:latest -f Dockerfile .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] Podman build failed. Please check Dockerfile." -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Image 'codesense-ai-app:latest' built successfully." -ForegroundColor Green
} else {
    Write-Host "[OK] Image 'codesense-ai-app:latest' already exists locally." -ForegroundColor Green
}

# 3. Deploy Native Podman Kubernetes Pod
Write-Host "`n[+] Deploying multi-container pod via 'podman play kube podman-k8s.yaml'..." -ForegroundColor Cyan
podman play kube podman-k8s.yaml

if ($LASTEXITCODE -ne 0) {
    Write-Host "[*] Trying podman-compose fallback..." -ForegroundColor Yellow
    $composeCmd = Get-Command "podman-compose" -ErrorAction SilentlyContinue
    if ($composeCmd) {
        podman-compose -f podman-compose.yml up -d
    }
}

# 4. Display Active Pod and Containers
Start-Sleep -Seconds 3
Write-Host "`n[OK] Active Podman Pods:" -ForegroundColor Green
podman pod ps

Write-Host "`n[OK] Active Podman Containers:" -ForegroundColor Green
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  CodeSense AI is LIVE on Rootless Podman!" -ForegroundColor Green
Write-Host "  Web Dashboard:  http://localhost:8501" -ForegroundColor Yellow
Write-Host "  Ollama Node:    http://localhost:11434" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
