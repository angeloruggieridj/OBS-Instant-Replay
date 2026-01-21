#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         OBS Instant Replay - Installation Script             ║"
echo "║                     v1.0-beta5                               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect OS
OS="$(uname -s)"
case "${OS}" in
    Linux*)
        OBS_SCRIPTS="$HOME/.config/obs-studio/scripts"
        ;;
    Darwin*)
        OBS_SCRIPTS="$HOME/Library/Application Support/obs-studio/scripts"
        ;;
    *)
        echo -e "${RED}[ERROR] Unsupported operating system: ${OS}${NC}"
        exit 1
        ;;
esac

echo "Detected OS: ${OS}"
echo ""

# Step 1: Check FFmpeg
echo "[1/3] Checking FFmpeg installation..."
if command -v ffmpeg &> /dev/null; then
    echo -e "     ${GREEN}[OK]${NC} FFmpeg found"
    ffmpeg -version 2>&1 | head -1 | sed 's/^/     /'
else
    echo -e "     ${YELLOW}[!]${NC} FFmpeg not found"
    echo ""
    echo "     FFmpeg is required for thumbnail generation."
    echo ""
    if [ "$OS" = "Darwin" ]; then
        echo "     To install on macOS:"
        echo "     brew install ffmpeg"
        echo ""
        read -p "     Install now with Homebrew? (y/n): " INSTALL
        if [ "$INSTALL" = "y" ] || [ "$INSTALL" = "Y" ]; then
            if command -v brew &> /dev/null; then
                brew install ffmpeg
            else
                echo -e "     ${RED}[ERROR]${NC} Homebrew not found. Install from https://brew.sh"
            fi
        fi
    else
        echo "     To install on Linux (Ubuntu/Debian):"
        echo "     sudo apt update && sudo apt install ffmpeg"
        echo ""
        echo "     To install on Linux (Fedora):"
        echo "     sudo dnf install ffmpeg"
        echo ""
        read -p "     Install now with apt? (y/n): " INSTALL
        if [ "$INSTALL" = "y" ] || [ "$INSTALL" = "Y" ]; then
            if command -v apt &> /dev/null; then
                sudo apt update && sudo apt install -y ffmpeg
            elif command -v dnf &> /dev/null; then
                sudo dnf install -y ffmpeg
            else
                echo -e "     ${YELLOW}[!]${NC} Package manager not detected. Please install FFmpeg manually."
            fi
        fi
    fi
fi

echo ""

# Step 2: Check OBS scripts directory
echo "[2/3] Locating OBS Studio scripts directory..."
if [ -d "$OBS_SCRIPTS" ]; then
    echo -e "     ${GREEN}[OK]${NC} Found: $OBS_SCRIPTS"
else
    echo -e "     ${YELLOW}[!]${NC} Directory not found. Creating..."
    mkdir -p "$OBS_SCRIPTS"
    if [ -d "$OBS_SCRIPTS" ]; then
        echo -e "     ${GREEN}[OK]${NC} Created: $OBS_SCRIPTS"
    else
        echo -e "     ${RED}[ERROR]${NC} Could not create scripts directory"
        exit 1
    fi
fi

echo ""

# Step 3: Copy files
echo "[3/3] Copying plugin files..."

COPY_SUCCESS=1

if [ -f "$SCRIPT_DIR/obs_replay_manager_browser.py" ]; then
    cp "$SCRIPT_DIR/obs_replay_manager_browser.py" "$OBS_SCRIPTS/"
    if [ $? -eq 0 ]; then
        echo -e "     ${GREEN}[OK]${NC} obs_replay_manager_browser.py"
    else
        echo -e "     ${RED}[ERROR]${NC} Failed to copy obs_replay_manager_browser.py"
        COPY_SUCCESS=0
    fi
else
    echo -e "     ${RED}[ERROR]${NC} obs_replay_manager_browser.py not found in $SCRIPT_DIR"
    COPY_SUCCESS=0
fi

if [ -f "$SCRIPT_DIR/replay_http_server.py" ]; then
    cp "$SCRIPT_DIR/replay_http_server.py" "$OBS_SCRIPTS/"
    if [ $? -eq 0 ]; then
        echo -e "     ${GREEN}[OK]${NC} replay_http_server.py"
    else
        echo -e "     ${RED}[ERROR]${NC} Failed to copy replay_http_server.py"
        COPY_SUCCESS=0
    fi
else
    echo -e "     ${RED}[ERROR]${NC} replay_http_server.py not found in $SCRIPT_DIR"
    COPY_SUCCESS=0
fi

# Done
echo ""
if [ "$COPY_SUCCESS" -eq 1 ]; then
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                   Installation Complete!                     ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
else
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║             Installation completed with errors               ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
fi
echo ""
echo "Next steps:"
echo "  1. Open OBS Studio"
echo "  2. Go to Tools > Scripts"
echo "  3. Click '+' and select obs_replay_manager_browser.py"
echo "  4. Configure the replay folder in script settings"
echo "  5. Go to Docks > Custom Browser Docks"
echo "  6. Add: Name: 'Replay Manager', URL: 'http://localhost:8765'"
echo ""
echo "Hotkeys can be configured in File > Settings > Hotkeys"
echo "Search for 'Replay' to find available shortcuts."
echo ""
