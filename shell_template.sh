# Simply Plural shell integration
# Add this to your ~/.bashrc or ~/.zshrc

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
    local cache_ttl=300      # 5 minutes
    
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
    # Note: Using --profile=default - change this if you want shell integration to use a different profile
    touch "$lock_file"
    sp --profile=default _internal_update_status >/dev/null 2>&1 || true
    rm -f "$lock_file" 2>/dev/null || true
}

# Initial cache population (run once on shell startup)
_sp_background_check

# Hook into prompt (uncomment the one for your shell)
# For Bash:
# PS1="$(_sp_prompt)$PS1"

# For Zsh:  
# PROMPT="$(_sp_prompt)$PROMPT"

# Alternative: If you have existing PROMPT_COMMAND setup
# PROMPT_COMMAND="_sp_prompt; $PROMPT_COMMAND"
