@echo off
REM CodeSense AI - Phase 1 Sourcegraph OSS Self-Hosted Container
REM Runs Sourcegraph OSS for structural and regex repository navigation

echo =======================================================
echo Starting Sourcegraph OSS Local Container (Docker)
echo =======================================================

docker run -d ^
  --publish 7080:7080 ^
  --publish 127.0.0.1:3370:3370 ^
  --rm ^
  --name sourcegraph-codesense ^
  --volume %cd%\sourcegraph\config:/etc/sourcegraph ^
  --volume %cd%\sourcegraph\data:/var/opt/sourcegraph ^
  sourcegraph/server:latest

echo Sourcegraph container initiated.
echo Access web interface at http://localhost:7080
pause
