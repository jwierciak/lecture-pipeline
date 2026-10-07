#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Lecture Pipeline - LaunchAgent Automated Installer (macOS)
# ==============================================================================

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}====================================================${NC}"
echo -e "${CYAN}    Lecture Pipeline - macOS LaunchAgent Setup     ${NC}"
echo -e "${CYAN}====================================================${NC}"

# 1. Verify macOS
if [[ "$(uname -s)" != "Darwin" ]]; then
    echo -e "${RED}[ERROR] This setup script is intended for macOS (Apple Silicon).${NC}"
    exit 1
fi

# 2. Determine project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE_FILE="${PROJECT_DIR}/launchd/com.lecture-pipeline.plist.template"
LAUNCHAGENTS_DIR="${HOME}/Library/LaunchAgents"
PLIST_TARGET="${LAUNCHAGENTS_DIR}/com.lecture-pipeline.processor.plist"

# 3. Detect Python interpreter
if [[ -n "${CONDA_PREFIX:-}" && -x "${CONDA_PREFIX}/bin/python" ]]; then
    PYTHON_EXEC="${CONDA_PREFIX}/bin/python"
elif [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    PYTHON_EXEC="${VIRTUAL_ENV}/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_EXEC="$(command -v python3)"
else
    echo -e "${RED}[ERROR] Python 3 interpreter could not be found.${NC}"
    exit 1
fi

echo -e "Using Python:   ${GREEN}${PYTHON_EXEC}${NC}"
echo -e "Project Root:   ${GREEN}${PROJECT_DIR}${NC}"

# 4. Verify .env configuration
if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
    if [[ -f "${PROJECT_DIR}/.env.example" ]]; then
        echo -e "${YELLOW}[WARNING] .env not found. Copying .env.example -> .env${NC}"
        cp "${PROJECT_DIR}/.env.example" "${PROJECT_DIR}/.env"
        echo -e "${YELLOW}Please edit ${PROJECT_DIR}/.env and set your GEMINI_API_KEY!${NC}"
    fi
fi

# 5. Determine Watch Folder
WATCH_DIR="${HOME}/Documents/Wykłady"
if [[ -f "${PROJECT_DIR}/.env" ]]; then
    ENV_WATCH=$(grep -E "^LECTURE_WATCH_DIR=" "${PROJECT_DIR}/.env" | cut -d'=' -f2- | tr -d '"' | tr -d "'" || true)
    if [[ -n "${ENV_WATCH}" ]]; then
        # Expand tilde
        WATCH_DIR="${ENV_WATCH/#\~/$HOME}"
    fi
fi

echo -e "Watched Folder: ${GREEN}${WATCH_DIR}${NC}"

# Ensure directories exist
mkdir -p "${WATCH_DIR}"
mkdir -p "${PROJECT_DIR}/logs"
mkdir -p "${PROJECT_DIR}/.staging"
mkdir -p "${LAUNCHAGENTS_DIR}"

# 6. Check template
if [[ ! -f "${TEMPLATE_FILE}" ]]; then
    echo -e "${RED}[ERROR] Template file missing: ${TEMPLATE_FILE}${NC}"
    exit 1
fi

# 7. Unload existing service if running
if launchctl list | grep -q "com.lecture-pipeline.processor"; then
    echo -e "${YELLOW}[INFO] Unloading existing service...${NC}"
    launchctl unload "${PLIST_TARGET}" 2>/dev/null || true
fi

# 8. Generate target plist
sed \
    -e "s|{{PYTHON_EXEC}}|${PYTHON_EXEC}|g" \
    -e "s|{{PROJECT_DIR}}|${PROJECT_DIR}|g" \
    -e "s|{{WATCH_DIR}}|${WATCH_DIR}|g" \
    "${TEMPLATE_FILE}" > "${PLIST_TARGET}"

chmod 644 "${PLIST_TARGET}"

# 9. Register and load LaunchAgent
launchctl load "${PLIST_TARGET}"

echo -e "\n${GREEN}✔ LaunchAgent successfully installed and activated!${NC}"
echo -e "Plist path:     ${CYAN}${PLIST_TARGET}${NC}"
echo -e "Logs directory: ${CYAN}${PROJECT_DIR}/logs/${NC}"
echo -e "\nTo monitor service activity, run:"
echo -e "  ${YELLOW}tail -f ${PROJECT_DIR}/logs/launchd_out.log${NC}"
echo -e "To uninstall, run:"
echo -e "  ${YELLOW}${SCRIPT_DIR}/uninstall_service.sh${NC}\n"

