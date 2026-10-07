#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Lecture Pipeline - LaunchAgent Uninstaller (macOS)
# ==============================================================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

LAUNCHAGENTS_DIR="${HOME}/Library/LaunchAgents"
PLIST_TARGET="${LAUNCHAGENTS_DIR}/com.lecture-pipeline.processor.plist"

echo -e "${YELLOW}Unloading lecture-pipeline LaunchAgent...${NC}"

if launchctl list | grep -q "com.lecture-pipeline.processor"; then
    launchctl unload "${PLIST_TARGET}" 2>/dev/null || true
    echo -e "${GREEN}✔ Service stopped.${NC}"
else
    echo -e "Service was not running."
fi

if [[ -f "${PLIST_TARGET}" ]]; then
    rm -f "${PLIST_TARGET}"
    echo -e "${GREEN}✔ Removed ${PLIST_TARGET}${NC}"
fi

echo -e "${GREEN}Lecture Pipeline daemon uninstalled successfully.${NC}"

