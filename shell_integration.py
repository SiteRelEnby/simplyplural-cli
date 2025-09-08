"""
Shell Integration Manager for Simply Plural CLI

Handles generation and management of shell prompt integration scripts.
Provides smart, non-blocking prompt updates with background cache refresh.
"""

import os
import sys
from pathlib import Path
from typing import Optional


class ShellIntegrationManager:
    """Manages shell prompt integration for Simply Plural CLI"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.shell_dir = self.config.config_dir / "shell"
    
    def generate_integration_script(self) -> Path:
        """Generate the shell integration script from template"""
        self.shell_dir.mkdir(exist_ok=True)
        
        # Read the template file
        template_path = Path(__file__).parent / "shell_template.sh"
        
        try:
            with open(template_path, 'r') as f:
                script_content = f.read()
        except FileNotFoundError:
            # Fallback to embedded script if template not found
            script_content = self._get_fallback_script()
        
        script_path = self.shell_dir / "integration.sh"
        with open(script_path, 'w') as f:
            f.write(script_content)
            
        return script_path
    
    def _get_fallback_script(self) -> str:
        """Fallback shell script if template file is missing"""
        return '''# Simply Plural shell integration
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
'''
    
    def get_installation_instructions(self, script_path: Path) -> str:
        """Get shell-specific installation instructions"""
        shell_name = os.environ.get('SHELL', '').split('/')[-1]
        
        if shell_name == 'bash':
            config_file = "~/.bashrc"
        elif shell_name == 'zsh':
            config_file = "~/.zshrc"
        elif shell_name == 'fish':
            return f"""Fish shell detected, but this integration is for bash/zsh.
Consider using fish-specific prompt functions.

For fish, you might want to create a function in ~/.config/fish/functions/:
function sp_prompt
    cat ~/.cache/sp_status 2>/dev/null; or echo ""
end"""
        else:
            config_file = "your shell config file (~/.bashrc or ~/.zshrc)"
        
        return f"""To install shell integration:

1. Add the integration to your shell:
   echo 'source {script_path}' >> {config_file}

2. Edit {config_file} and uncomment the prompt line for your shell:
   # For Bash: PS1="$(_sp_prompt)$PS1" 
   # For Zsh:  PROMPT="$(_sp_prompt)$PROMPT"

3. Restart your shell or run:
   source {config_file}

The prompt will show:
  [Member]     - Current fronter (fresh data)
  ~[Member]    - Current fronter (refreshing in background)  
  (updating)   - Fetching data
  (error)      - Something went wrong

To use a different profile for shell integration, edit the generated script and
change --profile=default to --profile=yourprofile"""
    
    def generate_and_show_instructions(self) -> bool:
        """Generate integration script and show installation instructions"""
        try:
            script_path = self.generate_integration_script()
            instructions = self.get_installation_instructions(script_path)
            
            print(f"✓ Generated integration script at: {script_path}")
            print(f"\n{instructions}")
            return True
            
        except Exception as e:
            print(f"Error generating shell integration: {e}", file=sys.stderr)
            return False
    
    def generate_only(self) -> bool:
        """Generate integration script without showing instructions"""
        try:
            script_path = self.generate_integration_script()
            print(f"✓ Shell integration script generated at: {script_path}")
            return True
            
        except Exception as e:
            print(f"Error generating shell integration: {e}", file=sys.stderr)
            return False
    
    def get_script_path(self) -> Path:
        """Get the path where the integration script would be/is located"""
        return self.shell_dir / "integration.sh"
    
    def script_exists(self) -> bool:
        """Check if the integration script already exists"""
        return self.get_script_path().exists()
