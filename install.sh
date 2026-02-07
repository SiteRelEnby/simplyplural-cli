#!/bin/bash
# Installation script for Simply Plural CLI on Unix-like systems

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
error() {
    echo -e "${RED}Error: $1${NC}" >&2
}

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

info() {
    echo "→ $1"
}

# Check if we're in the right directory
if [ ! -f "sp.py" ]; then
    error "sp.py not found in current directory"
    error "Please run this from the simplyplural-cli directory"
    exit 1
fi

echo "Simply Plural CLI Installation"
echo "=============================="

# Check Python
info "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    error "Python 3 not found. Please install Python 3.7+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
success "Python $PYTHON_VERSION found"

# Install dependencies
info "Installing dependencies..."
if python3 -m pip install -r requirements.txt; then
    success "Dependencies installed"
else
    warning "Failed to install dependencies automatically"
    echo "Please install manually: python3 -m pip install -r requirements.txt"
fi

# Determine installation directory
if [ -d "$HOME/bin" ]; then
    INSTALL_DIR="$HOME/bin"
elif [ -d "$HOME/.local/bin" ]; then
    INSTALL_DIR="$HOME/.local/bin"
else
    # Create ~/bin if it doesn't exist
    mkdir -p "$HOME/bin"
    INSTALL_DIR="$HOME/bin"
    warning "Created $HOME/bin - you may need to add it to your PATH"
fi

info "Installing to $INSTALL_DIR..."

# Copy and make executable
cp -f sp.py "$INSTALL_DIR/sp"
chmod +x "$INSTALL_DIR/sp"

# Copy other files
if [ ! -d "$INSTALL_DIR/../share/simply-plural-cli" ]; then
    mkdir -p "$HOME/.local/share/simply-plural-cli"
    cp -f api_client.py cache_manager.py config_manager.py shell_template.sh shell_integration.py "$HOME/.local/share/simply-plural-cli/"
    cp -f daemon.py daemon_client.py daemon_protocol.py "$HOME/.local/share/simply-plural-cli/"
    cp -f README.md requirements.txt "$HOME/.local/share/simply-plural-cli/"
fi

success "Installed to $INSTALL_DIR/sp"

# Test installation
info "Testing installation..."
if "$INSTALL_DIR/sp" --help > /dev/null 2>&1; then
    success "Installation successful!"
else
    error "Installation test failed"
    exit 1
fi

# Check PATH
if ! echo "$PATH" | grep -q "$INSTALL_DIR"; then
    warning "$INSTALL_DIR is not in your PATH"
    echo "Add this to your ~/.bashrc or ~/.zshrc:"
    echo "  export PATH=\"\$PATH:$INSTALL_DIR\""
fi

echo ""
echo "=============================="
echo "Installation complete! 🎉"
echo ""
echo "Next steps:"
echo "1. Set up your API token: sp config --setup"
echo "2. Test basic functionality: sp fronting"
echo "3. See all commands: sp --help"
echo ""
echo "Optional: Start daemon for real-time updates (instant responses):"
echo "  sp daemon start"
echo "  sp daemon status"
echo ""
echo "For shell integration:"
echo "  sp config --setup"
echo "  # Follow the shell integration prompts"
