#!/bin/bash
# Simply Plural shell integration test launcher

set -e

echo "🧪 Simply Plural Shell Integration Tester"
echo "=========================================="

# Create test configs
TEST_DIR="/tmp/sp-shell-test"
mkdir -p "$TEST_DIR"

# Write the test bashrc
cat > "$TEST_DIR/.bashrc" << 'EOF'
#!/bin/bash
# Minimal test .bashrc for Simply Plural shell integration testing

# Simply Plural shell integration
_sp_prompt() {
    local status_file="$HOME/.cache/sp_status"
    
    # Always show current content (fast - ~1ms)
    cat "$status_file" 2>/dev/null || echo ""
    
    # Background check if refresh needed (slow stuff in background, no job control spam)
    (_sp_background_check >/dev/null 2>&1 & disown)
}

_sp_background_check() {
    local lock_file="$HOME/.cache/sp_refresh.lock"
    local status_file="$HOME/.cache/sp_status"
    local cache_ttl=900      # 15 minutes (updated TTL)
    
    # Quick mutex check - only one background worker at a time
    if [[ -f "$lock_file" ]]; then
        local lock_age=$(($(date +%s) - $(stat -c %Y "$lock_file" 2>/dev/null || echo 0)))
        if [[ $lock_age -lt 120 ]]; then
            return  # Another check is running
        fi
    fi
    
    # Check if we need to refresh
    if [[ -f "$status_file" ]]; then
        local file_age=$(($(date +%s) - $(stat -c %Y "$status_file" 2>/dev/null || echo 0)))
        if [[ $file_age -lt $cache_ttl ]]; then
            return  # Cache is still fresh
        fi
    fi
    
    # Do the slow work - update cache and status file
    # Note: Adjust path to your SP installation
    cd /cygdrive/d/claude/simplyplural-cli
    python sp.py --profile=default _internal_update_status >/dev/null 2>&1 || true
    rm -f "$lock_file" 2>/dev/null || true
}

# Initial cache population (run once on shell startup)
_sp_background_check

# Simple colorful prompt with SP integration
export PS1="\[\033[32m\]\u@\h\[\033[0m\]:\[\033[34m\]\w\[\033[0m\] \[\033[35m\]\$(_sp_prompt)\[\033[0m\]$ "

# Basic shell settings
export PATH="$PATH:."
export EDITOR=nano

# Make it obvious this is the test environment
echo "🧪 Simply Plural test environment loaded (Bash)"
echo "💡 Use 'exit' to return to your normal shell"
echo "🔧 Test commands:"
echo "   cd /cygdrive/d/claude/simplyplural-cli && python sp.py fronting"
echo "   cd /cygdrive/d/claude/simplyplural-cli && python sp.py switch TestMember"
echo "   cat ~/.cache/sp_status"
EOF

# Write the test zshrc
cat > "$TEST_DIR/.zshrc" << 'EOF'
#!/bin/zsh
# Minimal test .zshrc for Simply Plural shell integration testing

# Simply Plural shell integration
_sp_prompt() {
    local status_file="$HOME/.cache/sp_status"
    
    # Always show current content (fast - ~1ms)
    cat "$status_file" 2>/dev/null || echo ""
    
    # Background check if refresh needed (slow stuff in background, no job control spam)
    (_sp_background_check >/dev/null 2>&1 & disown)
}

_sp_background_check() {
    local lock_file="$HOME/.cache/sp_refresh.lock"
    local status_file="$HOME/.cache/sp_status"
    local cache_ttl=900      # 15 minutes (updated TTL)
    
    # Quick mutex check - only one background worker at a time
    if [[ -f "$lock_file" ]]; then
        local lock_age=$(($(date +%s) - $(stat -c %Y "$lock_file" 2>/dev/null || echo 0)))
        if [[ $lock_age -lt 120 ]]; then
            return  # Another check is running
        fi
    fi
    
    # Check if we need to refresh
    if [[ -f "$status_file" ]]; then
        local file_age=$(($(date +%s) - $(stat -c %Y "$status_file" 2>/dev/null || echo 0)))
        if [[ $file_age -lt $cache_ttl ]]; then
            return  # Cache is still fresh
        fi
    fi
    
    # Do the slow work - update cache and status file
    # Note: Adjust path to your SP installation
    cd /cygdrive/d/claude/simplyplural-cli
    python sp.py --profile=default _internal_update_status >/dev/null 2>&1 || true
    rm -f "$lock_file" 2>/dev/null || true
}

# Initial cache population (run once on shell startup)
_sp_background_check

# Enable prompt substitution for zsh
setopt PROMPT_SUBST

# Simple colorful prompt with SP integration
export PROMPT='%F{green}%n@%m%f:%F{blue}%~%f %F{magenta}$(_sp_prompt)%f$ '

# Basic zsh settings
export PATH="$PATH:."
export EDITOR=nano

# Zsh completion system (minimal)
autoload -U compinit
compinit

# Make it obvious this is the test environment
echo "🧪 Simply Plural test environment loaded (Zsh)"
echo "💡 Use 'exit' to return to your normal shell"
echo "🔧 Test commands:"
echo "   cd /cygdrive/d/claude/simplyplural-cli && python sp.py fronting"
echo "   cd /cygdrive/d/claude/simplyplural-cli && python sp.py switch TestMember"
echo "   cat ~/.cache/sp_status"
EOF

echo "✅ Test configs created in $TEST_DIR"
echo ""
echo "Choose your test shell:"
echo "1) Bash   (test .bashrc)"
echo "2) Zsh    (test .zshrc)"
echo "3) Show config files only"
echo ""
read -p "Enter choice [1-3]: " choice

case $choice in
    1)
        echo "🚀 Launching Bash test environment..."
        bash --rcfile "$TEST_DIR/.bashrc" -i
        ;;
    2)
        echo "🚀 Launching Zsh test environment..."
        ZDOTDIR="$TEST_DIR" zsh -i
        ;;
    3)
        echo "📄 Test config files:"
        echo "Bash: $TEST_DIR/.bashrc"
        echo "Zsh:  $TEST_DIR/.zshrc"
        echo ""
        echo "Manual usage:"
        echo "  bash --rcfile $TEST_DIR/.bashrc -i"
        echo "  ZDOTDIR=$TEST_DIR zsh -i"
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "🧹 Clean up test directory? (y/N)"
read -p "> " cleanup
if [[ "$cleanup" =~ ^[Yy] ]]; then
    rm -rf "$TEST_DIR"
    echo "✅ Test directory cleaned up"
fi
