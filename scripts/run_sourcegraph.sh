#!/usr/bin/env bash
# CodeSense AI - Phase 1 Sourcegraph OSS Self-Hosted Container
# Runs Sourcegraph OSS for structural and regex repository navigation

echo "======================================================="
echo "Starting Sourcegraph OSS Local Container (Docker / Podman)"
echo "======================================================="

CONTAINER_CMD="docker"
if ! command -v docker &> /dev/null && command -v podman &> /dev/null; then
    CONTAINER_CMD="podman"
fi

$CONTAINER_CMD run -d \
  --publish 7080:7080 \
  --publish 127.0.0.1:3370:3370 \
  --rm \
  --name sourcegraph-codesense \
  --volume ~/.sourcegraph/config:/etc/sourcegraph \
  --volume ~/.sourcegraph/data:/var/opt/sourcegraph \
  sourcegraph/server:latest

echo "Sourcegraph container initiated via $CONTAINER_CMD."
echo "Access web interface at http://localhost:7080"
