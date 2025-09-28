#!/usr/bin/env python3
"""
Simply Plural CLI - Command line interface for Simply Plural

Usage:
    sp switch <member>              Register a switch (works with members and custom fronts)
    sp switch <member1> <member2>   Multiple fronters (any combination)
    sp fronting                     Show current fronter(s) with type indicators
    sp who                          Alias for fronting
    sp members                      List all members
    sp members --include-custom     List members and custom fronts
    sp custom-fronts                List all custom fronts
    sp history                      Recent switches
    sp backup                       Export data
    sp status --format=prompt       Format for shell prompt

Custom Front Support:
    Simply Plural CLI supports both members and custom fronts seamlessly.
    Use any name in switch commands - the CLI will automatically detect the type.
    Custom fronts are shown with "(custom front)" indicators in all displays.

Installation:
    Download this script to ~/bin/ or anywhere in your PATH
    Run: sp config --setup
"""

import sys
import argparse
import json
import os
import time
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any


def check_dependencies():
    """Check for required dependencies and provide helpful error messages"""
    missing_deps = []
    
    try:
        import requests
    except ImportError:
        missing_deps.append('requests')
    
    if missing_deps:
        print("Error: Missing required dependencies:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\nPlease install them with:")
        print(f"  pip3 install {' '.join(missing_deps)}")
        print("\nOr install all dependencies:")
        print("  pip3 install -r requirements.txt")
        sys.exit(1)


# Check dependencies before importing our modules
check_dependencies()

# Import our modules (handle both standalone script and package imports)
try:
    from api_client import SimplyPluralAPI, APIError
    from cache_manager import CacheManager
    from config_manager import ConfigManager
    from shell_integration import ShellIntegrationManager
except ImportError:
    # If running as standalone script, add current directory to path
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    
    # Also try the standard installation location
    sys.path.insert(0, str(Path.home() / ".local" / "share" / "simply-plural-cli"))
    
    try:
        from api_client import SimplyPluralAPI, APIError
        from cache_manager import CacheManager
        from config_manager import ConfigManager
        from shell_integration import ShellIntegrationManager
    except ImportError as e:
        print(f"Error: Failed to import required modules: {e}")
        print("Make sure all files are in the same directory as this script,")
        print("or run from the source directory.")
        sys.exit(1)


class SimplePluralCLI:
    def __init__(self, profile: str = "default", debug: bool = False):
        self.debug = debug
        self.config = ConfigManager(profile)
        self.cache = CacheManager(self.config.cache_dir, self.config)
        self.api = SimplyPluralAPI(self.config.api_token, self.config, debug, self.cache) if self.config.api_token else None
        self.shell = ShellIntegrationManager(self.config)
    
    def _format_entity_name(self, name: str, entity_type: str) -> str:
        """Format entity name with appropriate type indicator based on config"""
        if entity_type == 'custom_front' and self.config.show_custom_front_indicators:
            if self.config.custom_front_indicator_style == 'character':
                return f"{self.config.custom_front_indicator_character}{name}"
            else:  # text style
                return f"{name} (custom front)"
        else:
            return name
    
    def cmd_switch(self, members: List[str], note: Optional[str] = None, co: bool = False):
        """Register a switch"""
        if not self.api:
            print("Error: Not configured. Run 'sp config --setup'", file=sys.stderr)
            return 1
            
        try:
            if co and len(members) == 1:
                # Add co-fronter to existing fronters
                current = self.api.get_fronters()
                # Handle both list and dict responses
                if isinstance(current, list):
                    current_names = [f.get('name', 'Unknown') for f in current]
                else:
                    current_names = [f.get('name', 'Unknown') for f in current.get('fronters', [])]
                if members[0] not in current_names:
                    members = current_names + members
            
            result = self.api.register_switch(members, note)
            
            # Invalidate cache immediately after local switch
            self.cache.invalidate_fronters()
            
            # Update status file immediately (local action, lag acceptable)
            try:
                self.cmd_internal_update_status()
            except:
                pass  # Don't fail switch if status update fails
            
            if len(members) == 1:
                print(f"[OK] Switched to {members[0]}")
            else:
                print(f"[OK] Switched to {', '.join(members)}")
                
            if note:
                print(f"  Note: {note}")
                
        except APIError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        
        return 0
    
    def cmd_debug(self, action: str):
        """Debug and diagnostic commands"""
        if action == 'cache':
            print("Cache Information:")
            print("=" * 20)
            cache_info = self.cache.get_cache_info()
            if not cache_info:
                print("No cached data found.")
            else:
                for key, info in cache_info.items():
                    print(f"\n{key}:")
                    print(f"  Age: {info['age_seconds']}s")
                    print(f"  TTL: {info['ttl_seconds']}s")
                    print(f"  Expired: {info['expired']}")
                    print(f"  In memory: {info['in_memory']}")
                    print(f"  File size: {info['file_size']} bytes")
                    
        elif action == 'config':
            print("Configuration Debug:")
            print("=" * 20)
            print(f"Profile: {self.config.profile}")
            print(f"Config file: {self.config.config_file}")
            print(f"Cache dir: {self.config.cache_dir}")
            print(f"Token: {'Set' if self.config.api_token else 'Not set'}")
            print(f"API timeout: {self.config.api_timeout}s")
            print(f"Max retries: {self.config.max_retries}")
            
        elif action == 'purge':
            print("Purging all cached data...")
            try:
                # Show what we're about to delete
                cache_info = self.cache.get_cache_info()
                if cache_info:
                    print(f"Found {len(cache_info)} cached items:")
                    for key in cache_info.keys():
                        print(f"  - {key}")
                else:
                    print("No cached data found.")
                
                # Clear the cache
                self.cache.clear_all()
                print("✓ Cache purged successfully.")
                print("Next API calls will fetch fresh data.")
                
            except Exception as e:
                print(f"Error purging cache: {e}")
                return 1
                
        return 0
    
    def cmd_help(self, topic: Optional[str] = None):
        """Show help information"""
        if topic:
            # Show help for specific topic
            help_topics = {
                'config': 'Configuration management:\n  --setup    Run setup wizard\n  --show     Show current config\n  --edit     Edit config file\n  --example  Output example config to stdout\n  --list-profiles    List all profiles\n  --create-profile   Create new profile\n  --delete-profile   Delete a profile',
                'profiles': 'Profile management:\n  sp --profile <n> <command>     Use specific profile\n  sp config --list-profiles        List profiles\n  sp config --create-profile <n>   Create profile\n  sp config --delete-profile <n>   Delete profile',
                'switch': 'Switch registration:\n  sp switch <member>               Switch to member\n  sp switch <member1> <member2>    Multiple fronters\n  sp switch --co <member>          Add co-fronter\n  sp switch --add <member>          (alias for --co)\n  sp switch <member> --note "text"  Add note\n  sp sw <member>                   Alias for `sp switch`',
                'format': 'Output formats:\n  human    Human readable (default)\n  json     JSON for scripts\n  prompt   For shell prompts\n  simple   Just names',
                'cache': 'Caching behavior:\n  - Fronters cached for 5 minutes\n  - Members cached for 1 hour\n  - Individual member lookups cached\n  - Works offline with cached data',
                'debug': 'Debug mode:\n  sp --debug <command>    Show API calls and responses\n  sp debug cache          Show cache information\n  sp debug config         Show configuration details\n  sp debug purge          Clear all cached data',
                'shell': 'Shell integration:\n  sp shell generate       Generate shell integration script\n  sp shell install        Generate and show installation instructions',
                'custom-fronts': 'Custom front support:\n  sp custom-fronts                    List all custom fronts\n  sp switch <custom-front>            Switch to a custom front\n  sp switch <member> <custom-front>   Mixed member/custom front co-fronting\n  sp members --include-custom         Show both members and custom fronts\n  sp fronting                         Shows "(custom front)" indicators\n\nCustom fronts work identically to members in all switch commands.\nThe CLI automatically detects whether a name is a member or custom front.'
            }
            
            if topic.lower() in help_topics:
                print(f"Help: {topic}")
                print("=" * (7 + len(topic)))
                print(help_topics[topic.lower()])
            else:
                print(f"No help available for '{topic}'")
                print(f"Available topics: {', '.join(help_topics.keys())}")
        else:
            # Show general help (same as --help)
            print(__doc__.strip())
            print("\nFor topic-specific help: sp help <topic>")
            print("Available topics: config, profiles, switch, format, cache, debug, shell, custom-fronts")
        
        return 0
    
    def cmd_fronting(self, format_type: str = "human"):
        """Show current fronter(s)"""
        try:
            # Try cache first for speed
            fronters = self.cache.get_fronters()
            if not fronters:
                if self.debug:
                    print("DEBUG: No cached fronters found, fetching from API")
                if not self.api:
                    print("Error: Not configured and no cached data", file=sys.stderr)
                    return 1
                fronters = self.api.get_fronters()
                self.cache.set_fronters(fronters)
            elif self.debug:
                print(f"DEBUG: Using cached fronters: {json.dumps(fronters, indent=2) if isinstance(fronters, dict) else fronters}")
            
            # Handle both list and dict responses
            if isinstance(fronters, list):
                fronter_info = [{'name': f.get('name', 'Unknown'), 'type': f.get('type', 'member')} for f in fronters]
            else:
                fronter_info = [{'name': f.get('name', 'Unknown'), 'type': f.get('type', 'member')} for f in fronters.get('fronters', [])]
            
            fronter_names = [f['name'] for f in fronter_info]
            
            if self.debug:
                print(f"DEBUG: Extracted fronter names: {fronter_names}")
            
            # Always update status file when we fetch fronters
            try:
                self.cmd_internal_update_status()
            except:
                pass  # Don't fail fronters command if status update fails
            
            if format_type == "json":
                print(json.dumps({"fronters": fronter_names}))
            elif format_type == "prompt":
                if fronter_names:
                    print(f"[{', '.join(fronter_names)}] ")
                else:
                    print("")
            elif format_type == "simple":
                print(', '.join(fronter_names) if fronter_names else "No one fronting")
            else:  # human
                if fronter_names:
                    # Build display names with type indicators
                    display_names = []
                    for info in fronter_info:
                        display_names.append(self._format_entity_name(info['name'], info['type']))
                    
                    if len(display_names) == 1:
                        print(f"Currently fronting: {display_names[0]}")
                    else:
                        print(f"Currently fronting: {', '.join(display_names)}")
                else:
                    print("No one currently fronting")
                    
                # Show last update time if from cache
                cache_time = self.cache.get_fronters_timestamp()
                if cache_time:
                    age = int(time.time() - cache_time)
                    if age > 30:
                        print(f"  (cached {age}s ago)")
        
        except APIError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
            
        return 0
    
    def cmd_members(self, fronting_only: bool = False, include_custom: bool = False):
        """List members and optionally custom fronts"""
        try:
            if fronting_only:
                return self.cmd_fronting("human")
            
            if self.debug:
                print("DEBUG: Fetching members list")
            
            members = self.cache.get_members()
            if not members:
                if self.debug:
                    print("DEBUG: No cached members found, fetching from API")
                if not self.api:
                    print("Error: Not configured and no cached data", file=sys.stderr)
                    return 1
                members = self.api.get_members()
                self.cache.set_members(members)
            elif self.debug:
                print(f"DEBUG: Using cached members: {len(members) if members else 0} members")
            
            if self.debug:
                print(f"DEBUG: Members response type: {type(members)}")
                print(f"DEBUG: Members response: {members}")
            
            print("Members:")
            for member in members:
                # Extract name from the nested structure
                name = member.get('content', {}).get('name', 'Unknown')
                desc = member.get('content', {}).get('desc', '')
                pronouns = member.get('content', {}).get('pronouns', '')
                
                # Build the display line
                display_parts = [name]
                if pronouns:
                    display_parts.append(f"({pronouns})")
                if desc:
                    desc_short = desc[:50] + "..." if len(desc) > 50 else desc
                    display_parts.append(f"- {desc_short}")
                    
                print(f"  {' '.join(display_parts)}")
            
            # Include custom fronts if requested
            if include_custom:
                if self.debug:
                    print("DEBUG: Also fetching custom fronts")
                
                custom_fronts = self.cache.get_custom_fronts()
                if not custom_fronts:
                    if self.debug:
                        print("DEBUG: No cached custom fronts found, fetching from API")
                    custom_fronts = self.api.get_custom_fronts()
                    self.cache.set_custom_fronts(custom_fronts)
                elif self.debug:
                    print(f"DEBUG: Using cached custom fronts: {len(custom_fronts) if custom_fronts else 0} custom fronts")
                
                if custom_fronts:
                    print("\nCustom fronts:")
                    for custom_front in custom_fronts:
                        # Extract name from the nested structure
                        name = custom_front.get('content', {}).get('name', 'Unknown')
                        desc = custom_front.get('content', {}).get('desc', '')
                        
                        # Format name with type indicator
                        formatted_name = self._format_entity_name(name, 'custom_front')
                        
                        # Build the display line
                        display_parts = [formatted_name]
                        if desc:
                            desc_short = desc[:50] + "..." if len(desc) > 50 else desc
                            display_parts.append(f"- {desc_short}")
                            
                        print(f"  {' '.join(display_parts)}")
                elif self.debug:
                    print("DEBUG: No custom fronts found")
                    
        except APIError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
            
        return 0
    
    def cmd_custom_fronts(self, include_in_members: bool = False):
        """List custom fronts"""
        try:
            if self.debug:
                print("DEBUG: Fetching custom fronts list")
            
            custom_fronts = self.cache.get_custom_fronts()
            if not custom_fronts:
                if self.debug:
                    print("DEBUG: No cached custom fronts found, fetching from API")
                if not self.api:
                    print("Error: Not configured and no cached data", file=sys.stderr)
                    return 1
                custom_fronts = self.api.get_custom_fronts()
                self.cache.set_custom_fronts(custom_fronts)
            elif self.debug:
                print(f"DEBUG: Using cached custom fronts: {len(custom_fronts) if custom_fronts else 0} custom fronts")
            
            if self.debug:
                print(f"DEBUG: Custom fronts response type: {type(custom_fronts)}")
                print(f"DEBUG: Custom fronts response: {custom_fronts}")
            
            if not custom_fronts:
                print("No custom fronts found")
                return 0
            
            print("Custom fronts:")
            for custom_front in custom_fronts:
                # Extract name from the nested structure
                name = custom_front.get('content', {}).get('name', 'Unknown')
                desc = custom_front.get('content', {}).get('desc', '')
                
                # Format name with type indicator
                formatted_name = self._format_entity_name(name, 'custom_front')
                
                # Build the display line
                display_parts = [formatted_name]
                if desc:
                    desc_short = desc[:50] + "..." if len(desc) > 50 else desc
                    display_parts.append(f"- {desc_short}")
                    
                print(f"  {' '.join(display_parts)}")
                
        except APIError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
            
        return 0
    
    def cmd_history(self, period: str = "recent", count: int = 10):
        """Show switch history"""
        if not self.api:
            print("Error: Not configured. Run 'sp config --setup'", file=sys.stderr)
            return 1
        
        # Validate count parameter
        if count < 1:
            print("Error: Count must be at least 1", file=sys.stderr)
            return 1
        elif count > 1000:
            print(f"Warning: Count limited to 1000 (requested {count})")
            count = 1000
            
        try:
            switches = self.api.get_switches(period, count)
            
            if not switches:
                print("No switch history found")
                return 0
                
            print("Recent switches:")
            for switch in switches[:count]:
                # Extract data from frontHistory structure
                content = switch.get('content', {})
                start_time = content.get('startTime', 0)
                end_time = content.get('endTime', 0)
                member_id = content.get('member', '')
                
                # Get member name with better error handling
                member_name = "Unknown"
                if member_id:
                    try:
                        member = self.api.get_member(member_id)
                        member_name = member.get('content', {}).get('name', f"ID-{member_id[:8]}")
                    except APIError as e:
                        # For 404s (deleted members), show a cleaner fallback
                        if "not found" in str(e).lower():
                            member_name = f"[Deleted member {member_id[:8]}]"
                        else:
                            member_name = f"ID-{member_id[:8]}"
                
                # Format timestamp from startTime (milliseconds)
                try:
                    if start_time:
                        # Convert from milliseconds to seconds
                        timestamp_seconds = start_time / 1000
                        time_str = time.strftime("%m/%d %H:%M", time.localtime(timestamp_seconds))
                    else:
                        time_str = "Unknown"
                except:
                    time_str = "Unknown"
                
                # Format duration if we have end time
                duration_str = ""
                if end_time and start_time:
                    duration_ms = end_time - start_time
                    duration_hours = duration_ms / (1000 * 60 * 60)
                    if duration_hours >= 1:
                        duration_str = f" ({duration_hours:.1f}h)"
                    else:
                        duration_minutes = duration_ms / (1000 * 60)
                        duration_str = f" ({duration_minutes:.0f}m)"
                elif not end_time and content.get('live', False):
                    duration_str = " (ongoing)"
                
                print(f"  {time_str} - {member_name}{duration_str}")
                    
        except APIError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
            
        return 0
    
    def cmd_backup(self, output_file: Optional[str] = None):
        """Backup data"""
        if not self.api:
            print("Error: Not configured. Run 'sp config --setup'", file=sys.stderr)
            return 1
            
        try:
            data = self.api.export_data()
            
            if not output_file:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                output_file = f"sp_backup_{timestamp}.json"
            
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            print(f"[OK] Backup saved to {output_file}")
            print(f"\n[!] Important: This is a limited backup containing:")
            print(f"    - Member list and details")
            print(f"    - Current fronters status")
            print(f"    - Recent switch history (last {len(data.get('switches', []))} switches)")
            print(f"\n    For complete data backup, use Simply Plural app's native export feature.")
            
        except APIError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except IOError as e:
            print(f"Error writing backup: {e}", file=sys.stderr)
            return 1
            
        return 0
    
    def cmd_config(self, setup: bool = False, show: bool = False, edit: bool = False, 
                   example: bool = False, list_profiles: bool = False, 
                   create_profile: Optional[str] = None, delete_profile: Optional[str] = None):
        """Configuration management"""
        if list_profiles:
            profiles = self.config.list_profiles()
            current = self.config.profile
            print("Available profiles:")
            for profile in profiles:
                marker = " (current)" if profile == current else ""
                configured = " [configured]" if self.config.profile_exists(profile) and self.config.get_all().get('api_token') else " [not configured]"
                print(f"  {profile}{marker}{configured}")
            print(f"\nUse --profile <name> to switch profiles")
            return 0
            
        elif create_profile:
            if self.config.create_profile(create_profile):
                print(f"[OK] Created profile '{create_profile}'")
                print(f"Run 'sp --profile {create_profile} config --setup' to configure it")
            else:
                print(f"Error: Profile '{create_profile}' already exists", file=sys.stderr)
                return 1
            return 0
            
        elif delete_profile:
            if delete_profile == 'default':
                print("Error: Cannot delete the default profile", file=sys.stderr)
                return 1
            elif self.config.delete_profile(delete_profile):
                print(f"[OK] Deleted profile '{delete_profile}'")
            else:
                print(f"Error: Profile '{delete_profile}' does not exist", file=sys.stderr)
                return 1
            return 0
        if setup:
            print("Simply Plural CLI Setup")
            print("======================")
            print("\n1. Get your token from Simply Plural app:")
            print("   Settings -> Account -> Tokens -> Create Token")
            print("\n2. Choose token permissions carefully:")
            print("   * READ ONLY: Safe for retrieving fronters, members, history")
            print("   * READ + WRITE: Required for registering switches (sp switch command)")
            print("   * DELETE: NOT recommended for this program")
            print("\n[!] SECURITY IMPORTANT:")
            print("   * Tokens are like passwords - protect them carefully!")
            print("   * Read-only tokens can't register switches but are safer if compromised")
            print("   * Write tokens let others change your account if stolen")
            print("   * Never grant DELETE permission unless absolutely necessary")
            print("   * For daily use, prefer read-only tokens in shared/risky environments")
            print("\n   Recommendation: Use read+write for personal use, read-only for servers/scripts")
            
            token = input("\nEnter your token: ").strip()
            if not token:
                print("Error: Token required", file=sys.stderr)
                return 1
            
            # Ensure token is never logged or printed in debug mode
            if self.debug:
                print("DEBUG: Token received (not shown for security)")
                
            # Test the token (debug mode temporarily disabled for security)
            original_debug = self.debug
            self.debug = False  # Prevent token from appearing in API debug output
            test_api = SimplyPluralAPI(token, self.config, debug=False)
            try:
                test_api.get_fronters()
                self.config.set_api_token(token)
                print("[OK] Token validated and saved")
                
                # Create example config for reference
                example_file = self.config.create_example_config()
                print(f"\n[OK] Example config created at: {example_file}")
                print("  You can edit this file to customize settings")
                
                print(f"\n[OK] Setup complete!")
                print(f"\nOptional: Generate shell integration with 'sp shell install'")
                    
            except APIError as e:
                print(f"Error: Token validation failed - {e}", file=sys.stderr)
                return 1
            finally:
                # Restore original debug mode
                self.debug = original_debug
                
        elif example:
            # Output example configuration to stdout
            example_profiles = {
                "default": self.config._get_default_config(),
                "example-friend-system": {
                    "api_token": "friend-token-here",
                    "default_output_format": "json",
                    "cache_fronters_ttl": 120
                },
                "example-server-readonly": {
                    "api_token": "readonly-token-here",
                    "default_output_format": "simple"
                }
            }
            
            # Create a comprehensive example config
            lines = [
                "# Simply Plural CLI - Example Configuration File",
                "#",
                "# Copy this content to your config file and edit as needed",
                "# Uncomment and modify settings as needed",
                "#",
                "# QUICK START:",
                "# 1. Copy this content to your config file",
                "# 2. Add your token: api_token = your-token-here",
                "# 3. Uncomment and modify any settings you want to change",
                "#",
                "# SECURITY NOTE:",
                "# Protect your tokens! They are like passwords.",
                "# Use read-only tokens when possible for safety.",
                "",
                "[default]",
                "# Get your token from: Simply Plural app -> Settings -> Account -> Tokens",
                "api_token = your-token-here",
                "",
                "# API settings",
                "# api_timeout = 10",
                "# max_retries = 3",
                "",
                "# Display preferences",
                "# default_output_format = human    # human, json, prompt, simple",
                "# show_timestamps = true",
                "# show_cache_age = true",
                "# use_colors = true",
                "# timezone = local",
                "",
                "# Cache settings (in seconds)",
                "# cache_fronters_ttl = 300     # 5 minutes",
                "# cache_members_ttl = 3600     # 1 hour",
                "# cache_switches_ttl = 1800    # 30 minutes",
                "",
                "# Shell integration",
                "# shell_update_interval = 60",
                "",
                "# Member preferences",
                "# default_member = member-name",
                "# member_name_matching = fuzzy",
                "",
                "# Backup settings",
                "# auto_backup_on_exit = false",
                "# backup_include_switches = true",
                "# backup_include_members = true",
                "# max_backup_files = 5",
                "",
                "# Example: Friend's system (read-only monitoring)",
                "[friend-system]",
                "api_token = friend-readonly-token-here",
                "default_output_format = json",
                "cache_fronters_ttl = 120    # Check more frequently",
                "",
                "# Example: Server deployment (minimal, fast)",
                "[server]",
                "api_token = server-token-here",
                "default_output_format = simple",
                "show_timestamps = false",
                "show_cache_age = false",
                "cache_fronters_ttl = 600    # Cache longer for stability"
            ]
            
            print("\n".join(lines))
                
        elif show:
            info = self.config.get_config_info()
            print("Configuration:")
            print(f"  Config file: {info['config_file']}")
            print(f"  Config format: {info['config_format']}")
            print(f"  Config exists: {info['config_exists']}")
            print(f"  Cache dir: {info['cache_dir']}")
            print(f"  Token: {'Set' if self.config.api_token else 'Not set'}")
            print(f"  Is configured: {info['is_configured']}")
            
            if info['validation_issues']:
                print("\nIssues:")
                for issue in info['validation_issues']:
                    print(f"  ! {issue}")
                    
            print("\nKey settings:")
            print(f"  Output format: {self.config.default_output_format}")
            print(f"  Cache TTL (fronters): {self.config.cache_fronters_ttl}s")
            
        elif edit:
            config_file = self.config.config_file
            if not config_file.exists():
                # Create example config
                example_file = self.config.create_example_config()
                config_file.write_text(example_file.read_text())
                print(f"Created config file: {config_file}")
            
            print(f"Edit config file: {config_file}")
            print("\nAfter editing, run 'sp config --show' to verify changes")
            
            # Try to open with system editor
            import subprocess
            import shutil
            
            editors = ['code', 'nano', 'vim', 'notepad']
            for editor in editors:
                if shutil.which(editor):
                    try:
                        subprocess.run([editor, str(config_file)])
                        break
                    except:
                        continue
            else:
                print(f"\nNo editor found. Please manually edit: {config_file}")
        
        else:
            print("Configuration management:")
            print("  --setup    Run setup wizard")
            print("  --show     Show current configuration")
            print("  --edit     Edit configuration file")
            print("  --example  Output example configuration to stdout")
            print("\nConfig file location:")
            print(f"  {self.config.config_file}")
            
        return 0
    
    def cmd_shell(self, action: str):
        """Shell integration management"""
        if action == 'generate':
            return 0 if self.shell.generate_only() else 1
                
        elif action == 'install':
            return 0 if self.shell.generate_and_show_instructions() else 1
        
        return 0
    
    def cmd_internal_update_status(self):
        """Internal command for shell prompt - fast cache-only lookup with smart fallbacks"""
        try:
            if self.debug:
                print("DEBUG: Starting internal status update")
                
            # Check cache with expiry information
            fronters = self.cache.get_fronters()
            cache_timestamp = self.cache.get_fronters_timestamp()
            
            if self.debug:
                print(f"DEBUG: Cache fronters: {fronters}")
                print(f"DEBUG: Cache timestamp: {cache_timestamp}")
            
            status_text = ""
            should_refresh = False
            
            if fronters and cache_timestamp:
                # We have cached data - check if it's fresh
                cache_age = int(time.time() - cache_timestamp)
                fronter_names = [f.get('name', 'Unknown') for f in fronters if f.get('name') != 'Unknown']
                
                if self.debug:
                    print(f"DEBUG: Cache age: {cache_age}s, TTL: {self.config.cache_fronters_ttl}s")
                    print(f"DEBUG: Extracted fronter names: {fronter_names}")
                
                if fronter_names:
                    if cache_age <= self.config.cache_fronters_ttl:
                        # Fresh data
                        status_text = f"[{', '.join(fronter_names)}] "
                        if self.debug:
                            print(f"DEBUG: Using fresh cached data: '{status_text.strip()}'")
                    else:
                        # Expired data - show with prefix indicator
                        status_text = f"~[{', '.join(fronter_names)}] "
                        should_refresh = True
                        if self.debug:
                            print(f"DEBUG: Using expired cached data: '{status_text.strip()}', will refresh")
                else:
                    # No valid names in cache
                    status_text = "(updating) "
                    should_refresh = True
                    if self.debug:
                        print("DEBUG: No valid names in cache, showing 'updating'")
            else:
                # No cached data at all
                status_text = "(updating) "
                should_refresh = True
                if self.debug:
                    print("DEBUG: No cached data at all, showing 'updating'")
            
            # Write current status (even if stale/updating)
            status_file = Path.home() / '.cache' / 'sp_status'
            status_file.parent.mkdir(exist_ok=True)
            
            if self.debug:
                print(f"DEBUG: Writing status to {status_file}: '{status_text.strip()}'")
            
            # Atomic write
            temp_file = status_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                f.write(status_text)
            temp_file.replace(status_file)
            
            if self.debug:
                print(f"DEBUG: Status file written successfully")
            
            # Start background refresh if needed (non-blocking)
            if should_refresh:
                if self.debug:
                    print("DEBUG: Starting background refresh")
                self._start_background_refresh()
            
        except Exception as e:
            if self.debug:
                print(f"DEBUG: Exception in internal_update_status: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
            
            # Check cache with expiry information
            fronters = self.cache.get_fronters()
            cache_timestamp = self.cache.get_fronters_timestamp()
            
            status_text = ""
            should_refresh = False
            
            if fronters and cache_timestamp:
                # We have cached data - check if it's fresh
                cache_age = int(time.time() - cache_timestamp)
                fronter_names = [f.get('name', 'Unknown') for f in fronters if f.get('name') != 'Unknown']
                
                if fronter_names:
                    if cache_age <= self.config.cache_fronters_ttl:
                        # Fresh data
                        status_text = f"[{', '.join(fronter_names)}] "
                    else:
                        # Expired data - show with prefix indicator
                        status_text = f"~[{', '.join(fronter_names)}] "
                        should_refresh = True
                else:
                    # No valid names in cache
                    status_text = "(updating) "
                    should_refresh = True
            else:
                # No cached data at all
                status_text = "(updating) "
                should_refresh = True
            
            # Write current status (even if stale/updating)
            status_file = Path.home() / '.cache' / 'sp_status'
            status_file.parent.mkdir(exist_ok=True)
            
            # Atomic write
            temp_file = status_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                f.write(status_text)
            temp_file.replace(status_file)
            
            # Start background refresh if needed (non-blocking)
            if should_refresh:
                self._start_background_refresh()
            
        except Exception:
            # Fail silently for shell integration - write fallback status
            try:
                status_file = Path.home() / '.cache' / 'sp_status'
                status_file.parent.mkdir(exist_ok=True)
                with open(status_file, 'w') as f:
                    f.write("(error) ")  # Show something went wrong
            except:
                pass  # Give up silently
            
        return 0
    
    def _start_background_refresh(self):
        """Start a background cache refresh if one isn't already running"""
        try:
            import subprocess
            import os
            
            lock_file = Path.home() / '.cache' / 'sp_refresh.lock'
            
            # Check if refresh is already running
            if lock_file.exists():
                # Check lock file age - if > 2 minutes old, assume stale
                try:
                    lock_age = time.time() - lock_file.stat().st_mtime
                    if lock_age < 120:  # 2 minutes
                        return  # Another refresh is running
                    else:
                        # Stale lock, remove it
                        lock_file.unlink()
                except:
                    pass  # If we can't check, proceed anyway
            
            # Start background refresh
            # Use subprocess to avoid blocking the shell prompt
            script_path = Path(__file__).resolve()
            python_exe = sys.executable
            
            # Background command that:
            # 1. Creates lock file
            # 2. Fetches fronters (populates cache)
            # 3. Updates status file
            # 4. Removes lock file
            refresh_cmd = f'''
            (
                echo $ > "{lock_file}" &&
                "{python_exe}" "{script_path}" fronting --format=simple >/dev/null 2>&1 &&
                "{python_exe}" "{script_path}" _internal_update_status >/dev/null 2>&1;
                rm -f "{lock_file}" 2>/dev/null || true
            ) &
            '''
            
            # Execute in background shell
            subprocess.Popen(
                refresh_cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True  # Detach from parent
            )
            
        except Exception:
            # If background refresh fails, that's okay - just continue
            pass


def main():
    parser = argparse.ArgumentParser(
        prog='sp',
        description='Simply Plural CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split('Installation:')[0].strip()
    )
    
    # Global options
    parser.add_argument('--profile', default='default', 
                       help='Profile to use (default: default)')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug output')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Switch command
    switch_parser = subparsers.add_parser('switch', help='Register a switch')
    switch_parser.add_argument('members', nargs='+', help='Member name(s)')
    switch_parser.add_argument('--note', help='Add a note to the switch')
    switch_parser.add_argument('--co', '--add', action='store_true', help='Add co-fronter to existing fronters')

    # sw command (alias for switch)
    sw_parser = subparsers.add_parser('sw', help='Register a switch')
    sw_parser.add_argument('members', nargs='+', help='Member name(s)')
    sw_parser.add_argument('--note', help='Add a note to the switch')
    sw_parser.add_argument('--co', '--add', action='store_true', help='Add co-fronter to existing fronters')

    
    # Fronting command
    fronting_parser = subparsers.add_parser('fronting', help='Show current fronter(s)')
    fronting_parser.add_argument('--format', choices=['human', 'json', 'prompt', 'simple'], 
                                default='human', help='Output format')
    
    # Who command (alias for fronting)
    who_parser = subparsers.add_parser('who', help='Show current fronter(s)')
    who_parser.add_argument('--format', choices=['human', 'json', 'prompt', 'simple'], 
                           default='human', help='Output format')
    
    # w command (alias for who)
    w_parser = subparsers.add_parser('w', help='Show current fronter(s)')
    w_parser.add_argument('--format', choices=['human', 'json', 'prompt', 'simple'],
                         default='human', help='Output format')
    # Members command
    members_parser = subparsers.add_parser('members', help='List members')
    members_parser.add_argument('--fronting', action='store_true', help='Show only current fronters')
    members_parser.add_argument('--include-custom', action='store_true', help='Include custom fronts in the listing')
    
    # Custom fronts command
    custom_fronts_parser = subparsers.add_parser('custom-fronts', help='List custom fronts')
    custom_fronts_parser.add_argument('--help-alias', action='store_true', help=argparse.SUPPRESS)
    
    # History command
    history_parser = subparsers.add_parser('history', help='Show switch history')
    history_parser.add_argument('--today', action='store_const', const='today', dest='period', 
                               help='Show today\'s switches')
    history_parser.add_argument('--week', action='store_const', const='week', dest='period',
                               help='Show this week\'s switches')
    history_parser.add_argument('--count', type=int, default=10, help='Number of switches to show (max 1000)')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Export data')
    backup_parser.add_argument('--output', help='Output file name')
    
    # Config command
    config_parser = subparsers.add_parser('config', help='Configuration')
    config_parser.add_argument('--setup', action='store_true', help='Run setup wizard')
    config_parser.add_argument('--show', action='store_true', help='Show current configuration')
    config_parser.add_argument('--edit', action='store_true', help='Edit configuration file')
    config_parser.add_argument('--example', action='store_true', help='Output example configuration to stdout')
    config_parser.add_argument('--list-profiles', action='store_true', help='List all profiles')
    config_parser.add_argument('--create-profile', metavar='NAME', help='Create a new profile')
    config_parser.add_argument('--delete-profile', metavar='NAME', help='Delete a profile')
    
    # Help command
    help_parser = subparsers.add_parser('help', help='Show help message')
    help_parser.add_argument('topic', nargs='?', help='Help topic (optional)')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Get status (alias for fronting)')
    status_parser.add_argument('--format', choices=['human', 'json', 'prompt', 'simple'], 
                              default='prompt', help='Output format')
    
    # Shell integration command
    shell_parser = subparsers.add_parser('shell', help='Generate shell integration')
    shell_parser.add_argument('action', choices=['generate', 'install'], 
                             help='Generate integration script or install it')
    
    # Internal commands
    internal_parser = subparsers.add_parser('_internal_update_status', help=argparse.SUPPRESS)
    
    # Debug commands
    debug_parser = subparsers.add_parser('debug', help='Debug and diagnostic commands')
    debug_parser.add_argument('action', choices=['cache', 'config', 'purge'], 
                             help='Debug action to perform')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    cli = SimplePluralCLI(args.profile, args.debug)
    
    # Route commands
    if args.command in ['switch','sw']:
        return cli.cmd_switch(args.members, args.note, args.co)
    elif args.command in ['fronting', 'who', 'w']:
        return cli.cmd_fronting(args.format)
    elif args.command == 'members':
        return cli.cmd_members(args.fronting, getattr(args, 'include_custom', False))
    elif args.command == 'custom-fronts':
        return cli.cmd_custom_fronts()
    elif args.command == 'history':
        period = getattr(args, 'period', 'recent')
        return cli.cmd_history(period, args.count)
    elif args.command == 'backup':
        return cli.cmd_backup(args.output)
    elif args.command == 'config':
        return cli.cmd_config(args.setup, args.show, args.edit, args.example,
                             getattr(args, 'list_profiles', False),
                             getattr(args, 'create_profile', None),
                             getattr(args, 'delete_profile', None))
    elif args.command == 'help':
        return cli.cmd_help(getattr(args, 'topic', None))
    elif args.command == 'status':
        return cli.cmd_fronting(args.format)
    elif args.command == 'shell':
        return cli.cmd_shell(args.action)
    elif args.command == 'debug':
        return cli.cmd_debug(args.action)
    elif args.command == '_internal_update_status':
        return cli.cmd_internal_update_status()
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
