"""
Configuration Manager for Simply Plural CLI

Handles storage and retrieval of user configuration including:
- API tokens (with multi-profile support)
- User preferences  
- Cache settings
- Shell integration preferences

Uses a simple key=value config file format with profile sections for easy manual editing.
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
import tempfile
import re
import hashlib


class ConfigManager:
    """Manages configuration for Simply Plural CLI"""
    
    def __init__(self, profile: str = "default"):
        self.profile = profile
        
        # Determine config directory based on platform
        self.config_dir = self._get_config_dir()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache directory
        self.cache_dir = self._get_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Config file (use .conf format for easier manual editing)
        self.config_file = self.config_dir / "simplyplural.conf"
        self.json_config_file = self.config_dir / "config.json"  # Legacy support
        
        # Load configuration
        self._all_profiles = self._load_all_profiles()
        self._config = self._all_profiles.get(self.profile, self._get_default_config())
    
    def _get_config_dir(self) -> Path:
        """Get the appropriate configuration directory for the platform"""
        
        # Check XDG_CONFIG_HOME first (Linux/Unix standard)
        if 'XDG_CONFIG_HOME' in os.environ:
            return Path(os.environ['XDG_CONFIG_HOME']) / 'simply-plural'
        
        # Platform-specific defaults
        home = Path.home()
        
        if os.name == 'nt':  # Windows
            # Use APPDATA if available, otherwise fallback to home
            appdata = os.environ.get('APPDATA')
            if appdata:
                return Path(appdata) / 'simply-plural'
            else:
                return home / '.simply-plural'
        
        elif os.name == 'posix':  # Linux, macOS, Unix
            system = os.uname().sysname.lower()
            if system == 'darwin':  # macOS
                return home / 'Library' / 'Application Support' / 'simply-plural'
            else:  # Linux and other Unix
                return home / '.config' / 'simply-plural'
        
        else:
            # Fallback for unknown platforms
            return home / '.simply-plural'
    
    def _get_cache_dir(self) -> Path:
        """Get the appropriate cache directory for the platform (base directory)"""
        
        # Check XDG_CACHE_HOME first (Linux/Unix standard)
        if 'XDG_CACHE_HOME' in os.environ:
            return Path(os.environ['XDG_CACHE_HOME']) / 'simply-plural'
        
        # Platform-specific defaults
        home = Path.home()
        
        if os.name == 'nt':  # Windows
            # Use TEMP or LOCALAPPDATA if available
            temp_dir = os.environ.get('LOCALAPPDATA') or os.environ.get('TEMP')
            if temp_dir:
                return Path(temp_dir) / 'simply-plural'
            else:
                return home / '.simply-plural' / 'cache'
        
        elif os.name == 'posix':  # Linux, macOS, Unix
            system = os.uname().sysname.lower()
            if system == 'darwin':  # macOS
                return home / 'Library' / 'Caches' / 'simply-plural'
            else:  # Linux and other Unix
                return home / '.cache' / 'simply-plural'
        
        else:
            # Fallback for unknown platforms
            return home / '.simply-plural' / 'cache'
    
    def get_profile_cache_dir(self) -> Path:
        """Get profile-specific cache directory using hash of profile name + API token
        
        This ensures that each profile+token combination has its own isolated cache,
        preventing cache collisions when switching between profiles/accounts.
        """
        # Generate a unique identifier from profile name and API token
        profile_identifier = f"{self.profile}:{self.api_token or ''}"
        profile_hash = hashlib.sha256(profile_identifier.encode()).hexdigest()[:16]
        
        # Create profile-specific subdirectory
        profile_cache_dir = self.cache_dir / profile_hash
        profile_cache_dir.mkdir(parents=True, exist_ok=True)
        
        return profile_cache_dir
    
    def _parse_config_file(self, content: str) -> Dict[str, Dict[str, Any]]:
        """Parse key=value config file format with profile sections"""
        profiles = {}
        current_profile = "default"
        
        # Normalize line endings for cross-platform compatibility
        content = content.replace('\\r\\n', '\\n').replace('\\r', '\\n')
        
        for line_num, line in enumerate(content.splitlines(), 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Check for profile section headers [profile_name]
            if line.startswith('[') and line.endswith(']'):
                current_profile = line[1:-1].strip()
                if current_profile not in profiles:
                    profiles[current_profile] = {}
                continue
            
            # Parse key = value
            if '=' not in line:
                # Skip malformed lines silently
                continue
            
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            
            # Remove quotes if present
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            
            # Initialize profile if not exists
            if current_profile not in profiles:
                profiles[current_profile] = {}
            
            # Convert to appropriate type
            profiles[current_profile][key] = self._convert_config_value(value)
        
        # If no profiles found, treat entire file as default profile
        if not profiles and current_profile == "default":
            # Re-parse without profile support for backward compatibility
            profiles["default"] = {}
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                profiles["default"][key] = self._convert_config_value(value)
        
        return profiles
    
    def _convert_config_value(self, value: str) -> Any:
        """Convert string config value to appropriate Python type"""
        # Handle empty values
        if not value:
            return ""
        
        # Handle booleans
        if value.lower() in ('true', 'yes', 'on', '1'):
            return True
        elif value.lower() in ('false', 'no', 'off', '0'):
            return False
        
        # Handle numbers
        try:
            # Try integer first
            if '.' not in value:
                return int(value)
            else:
                return float(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def _format_config_file(self, all_profiles: Dict[str, Dict[str, Any]]) -> str:
        """Format config as key=value file with profile sections"""
        lines = [
            "# Simply Plural CLI Configuration File",
            "# Edit this file to customize your settings", 
            "# Use [profile_name] sections for multiple accounts",
            ""
        ]
        
        # Group related settings
        sections = [
            ("API Settings", [
                "api_token",
                "api_timeout", 
                "max_retries"
            ]),
            ("Display Settings", [
                "default_output_format"
            ]),
            ("Cache Settings", [
                "cache_fronters_ttl",
                "cache_members_ttl",
                "cache_switches_ttl",
                "cache_custom_fronts_ttl"
            ]),
            ("Shell Integration", [
                "shell_update_interval"
            ])
        ]
        
        # Sort profiles so 'default' comes first
        profile_names = sorted(all_profiles.keys(), key=lambda x: (x != 'default', x))
        
        for profile_name in profile_names:
            config = all_profiles[profile_name]
            
            # Add profile header (except for default if it's the only profile)
            if len(all_profiles) > 1 or profile_name != 'default':
                lines.append(f"[{profile_name}]")
                lines.append("")
            
            for section_name, keys in sections:
                # Only add section header if profile has any of these keys
                section_has_values = any(key in config for key in keys)
                if section_has_values:
                    lines.append(f"# {section_name}")
                    
                    for key in keys:
                        if key in config:
                            value = config[key]
                            
                            # Quote strings that contain spaces or special chars
                            if isinstance(value, str) and (' ' in value or '"' in value or "'" in value):
                                value = f'"{value}"'
                            
                            lines.append(f"{key} = {value}")
                    
                    # Only add line break if not the last section with values
                    remaining_sections = sections[sections.index((section_name, keys)) + 1:]
                    has_remaining_values = any(
                        any(key in config for key in remaining_keys) 
                        for _, remaining_keys in remaining_sections
                    )
                    if has_remaining_values:
                        lines.append("")
            
            # Add single line break between profiles
            if profile_name != profile_names[-1]:
                lines.append("")
        
        return "\n".join(lines)
    
    def _load_all_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Load all profiles from config file"""
        # Start with defaults
        default_config = self._get_default_config()
        all_profiles = {"default": default_config}
        
        # Load from config file
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8', newline=None) as f:
                    content = f.read()
                
                file_profiles = self._parse_config_file(content)
                
                # Merge each profile with defaults
                for profile_name, profile_config in file_profiles.items():
                    merged_config = default_config.copy()
                    merged_config.update(profile_config)
                    all_profiles[profile_name] = merged_config
                
            except (IOError, UnicodeDecodeError) as e:
                # If config file is corrupted, start with defaults
                pass
        
        return all_profiles
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            # API Settings
            'api_token': "",
            'api_timeout': 10,
            'max_retries': 3,
            
            # Display Settings
            'default_output_format': "text",
            'show_custom_front_indicators': True,
            'custom_front_indicator_style': "character",  # "text" or "character"
            'custom_front_indicator_character': "^",
            
            # Cache Settings
            'cache_fronters_ttl': 900,    # 15 minutes
            'cache_members_ttl': 3600,    # 1 hour
            'cache_switches_ttl': 1800,   # 30 minutes
            'cache_custom_fronts_ttl': 3600,  # 1 hour (same as members)
            
            # Shell Integration
            'shell_update_interval': 60,

            # Daemon
            'start_daemon': False,
        }
    
    def _save_all_profiles(self, all_profiles: Optional[Dict[str, Dict[str, Any]]] = None):
        """Save all profiles to config file atomically"""
        if all_profiles is None:
            # Update current profile in all_profiles
            self._all_profiles[self.profile] = self._config
            all_profiles = self._all_profiles
            
        try:
            # Format as config file
            content = self._format_config_file(all_profiles)
            
            # Create temporary file in same directory
            with tempfile.NamedTemporaryFile(
                mode='w',
                dir=self.config_dir,
                delete=False,
                suffix='.tmp',
                encoding='utf-8',
                newline='\n'  # Force Unix line endings for consistency
            ) as tmp_file:
                tmp_file.write(content)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
                temp_path = tmp_file.name
            
            # Atomic replace
            os.replace(temp_path, self.config_file)
            
        except (IOError, OSError) as e:
            # Clean up temporary file if it exists
            try:
                if 'temp_path' in locals():
                    os.unlink(temp_path)
            except:
                pass
            raise Exception(f"Failed to save configuration: {e}")
    
    def _save_config(self):
        """Save current profile configuration"""
        self._save_all_profiles()
    
    # Profile management methods
    
    def list_profiles(self) -> List[str]:
        """Get list of all available profiles"""
        return list(self._all_profiles.keys())
    
    def profile_exists(self, profile_name: str) -> bool:
        """Check if a profile exists"""
        return profile_name in self._all_profiles
    
    def create_profile(self, profile_name: str, copy_from: Optional[str] = None) -> bool:
        """Create a new profile, optionally copying from existing profile"""
        if profile_name in self._all_profiles:
            return False
        
        if copy_from and copy_from in self._all_profiles:
            self._all_profiles[profile_name] = self._all_profiles[copy_from].copy()
        else:
            self._all_profiles[profile_name] = self._get_default_config()
        
        self._save_all_profiles()
        return True
    
    def delete_profile(self, profile_name: str) -> bool:
        """Delete a profile (cannot delete 'default')"""
        if profile_name == 'default' or profile_name not in self._all_profiles:
            return False
        
        del self._all_profiles[profile_name]
        self._save_all_profiles()
        return True
    
    # Property accessors for common config values
    
    @property
    def api_token(self) -> Optional[str]:
        """Get the API token"""
        token = self._config.get('api_token', "")
        return token if token else None
    
    def set_api_token(self, token: str):
        """Set the API token"""
        self._config['api_token'] = token
        self._save_config()
    
    @property
    def cache_fronters_ttl(self) -> int:
        """Get fronters cache TTL in seconds"""
        return self._config.get('cache_fronters_ttl', 900)
    
    @property
    def cache_members_ttl(self) -> int:
        """Get members cache TTL in seconds"""
        return self._config.get('cache_members_ttl', 3600)
    
    @property
    def cache_switches_ttl(self) -> int:
        """Get switches cache TTL in seconds"""
        return self._config.get('cache_switches_ttl', 1800)
    
    @property
    def cache_custom_fronts_ttl(self) -> int:
        """Get custom fronts cache TTL in seconds"""
        return self._config.get('cache_custom_fronts_ttl', 3600)
    
    @property
    def shell_update_interval(self) -> int:
        """Get shell update interval in seconds"""
        return self._config.get('shell_update_interval', 60)
    
    @property
    def default_output_format(self) -> str:
        """Get the default output format"""
        return self._config.get('default_output_format', 'text')
    
    @property
    def show_custom_front_indicators(self) -> bool:
        """Get whether to show custom front type indicators"""
        return self._config.get('show_custom_front_indicators', True)
    
    @property
    def start_daemon(self) -> bool:
        """Get whether to auto-start the daemon when not running"""
        return self._config.get('start_daemon', False)

    @property
    def custom_front_indicator_style(self) -> str:
        """Get custom front indicator style ('text' or 'character')"""
        return self._config.get('custom_front_indicator_style', 'text')
    
    @property
    def custom_front_indicator_character(self) -> str:
        """Get custom front indicator character"""
        return self._config.get('custom_front_indicator_character', '^')
    
    # Configuration management methods
    
    def _save_all_profiles(self, all_profiles: Optional[Dict[str, Dict[str, Any]]] = None):
        """Save all profiles to config file atomically"""
        if all_profiles is None:
            # Update current profile in all_profiles
            self._all_profiles[self.profile] = self._config
            all_profiles = self._all_profiles
            
        try:
            # Format as config file
            content = self._format_config_file(all_profiles)
            
            # Create temporary file in same directory
            with tempfile.NamedTemporaryFile(
                mode='w',
                dir=self.config_dir,
                delete=False,
                suffix='.tmp',
                encoding='utf-8',
                newline='\n'  # Force Unix line endings for consistency
            ) as tmp_file:
                tmp_file.write(content)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
                temp_path = tmp_file.name
            
            # Atomic replace
            os.replace(temp_path, self.config_file)
            
        except (IOError, OSError) as e:
            # Clean up temporary file if it exists
            try:
                if 'temp_path' in locals():
                    os.unlink(temp_path)
            except:
                pass
            raise Exception(f"Failed to save configuration: {e}")
    
    def _save_config(self):
        """Save current profile configuration"""
        self._save_all_profiles()
    
    # Profile management methods
    
    def list_profiles(self) -> List[str]:
        """Get list of all available profiles"""
        return list(self._all_profiles.keys())
    
    def profile_exists(self, profile_name: str) -> bool:
        """Check if a profile exists"""
        return profile_name in self._all_profiles
    
    def create_profile(self, profile_name: str, copy_from: Optional[str] = None) -> bool:
        """Create a new profile, optionally copying from existing profile"""
        if profile_name in self._all_profiles:
            return False
        
        if copy_from and copy_from in self._all_profiles:
            self._all_profiles[profile_name] = self._all_profiles[copy_from].copy()
        else:
            self._all_profiles[profile_name] = self._get_default_config()
        
        self._save_all_profiles()
        return True
    
    def delete_profile(self, profile_name: str) -> bool:
        """Delete a profile (cannot delete 'default')"""
        if profile_name == 'default' or profile_name not in self._all_profiles:
            return False
        
        del self._all_profiles[profile_name]
        self._save_all_profiles()
        return True
    
    # Property accessors for common config values
    
    @property
    def api_token(self) -> Optional[str]:
        """Get the API token"""
        token = self._config.get('api_token', "")
        return token if token else None
    
    def set_api_token(self, token: str):
        """Set the API token"""
        self._config['api_token'] = token
        self._save_config()
    
    @property
    def cache_fronters_ttl(self) -> int:
        """Get fronters cache TTL in seconds"""
        return self._config.get('cache_fronters_ttl', 300)
    
    @property
    def cache_members_ttl(self) -> int:
        """Get members cache TTL in seconds"""
        return self._config.get('cache_members_ttl', 3600)
    
    @property
    def cache_switches_ttl(self) -> int:
        """Get switches cache TTL in seconds"""
        return self._config.get('cache_switches_ttl', 1800)
    
    @property
    def cache_custom_fronts_ttl(self) -> int:
        """Get custom fronts cache TTL in seconds"""
        return self._config.get('cache_custom_fronts_ttl', 3600)
    
    @property
    def api_timeout(self) -> int:
        """Get API timeout in seconds"""
        return self._config.get('api_timeout', 10)
    
    @property
    def max_retries(self) -> int:
        """Get maximum retries for API requests"""
        return self._config.get('max_retries', 3)
    
    @property
    def default_output_format(self) -> str:
        """Get the default output format"""
        return self._config.get('default_output_format', 'text')
    
    # Configuration management methods
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set a configuration value"""
        self._config[key] = value
        self._save_config()
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values for current profile"""
        return self._config.copy()
    
    def validate_config(self) -> List[str]:
        """Validate current configuration and return any issues"""
        issues = []
        
        # Check API token
        if not self.api_token:
            issues.append("API token not set. Run 'sp config --setup'")
        
        # Check cache TTL values
        for key in ['cache_fronters_ttl', 'cache_members_ttl', 'cache_switches_ttl', 'cache_custom_fronts_ttl']:
            if self._config.get(key, 0) < 0:
                issues.append(f"{key} cannot be negative")
        
        # Check output format
        valid_formats = ['text', 'json', 'prompt', 'simple']
        if self.default_output_format not in valid_formats:
            issues.append(f"Invalid output format '{self.default_output_format}'. Must be one of: {', '.join(valid_formats)}")
        
        return issues
    
    def is_configured(self) -> bool:
        """Check if the CLI is properly configured"""
        return bool(self.api_token)
    
    def get_config_info(self) -> Dict[str, Any]:
        """Get information about the configuration"""
        return {
            'config_file': str(self.config_file),
            'config_dir': str(self.config_dir),
            'cache_dir': str(self.cache_dir),
            'config_exists': self.config_file.exists(),
            'is_configured': self.is_configured(),
            'validation_issues': self.validate_config(),
            'config_format': 'key=value (.conf)',
            'current_profile': self.profile,
            'available_profiles': self.list_profiles()
        }
    
    def create_example_config(self) -> Path:
        """Create an example configuration file for reference"""
        example_file = self.config_dir / "simplyplural-example.conf"
        
        # Create example config with all available options documented
        example_profiles = {
            "default": self._get_default_config(),
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
        
        content = self._format_config_file(example_profiles)
        
        # Add extra documentation at the top
        header = '''# Simply Plural CLI - Example Configuration File
# 
# Copy this file to 'simplyplural.conf' and edit as needed
# Most settings have sensible defaults and can be omitted
# 
# QUICK START:
# 1. Copy this file to 'simplyplural.conf'
# 2. Add your token: api_token = your-token-here
# 3. Remove example profiles you don't need
# 
# SECURITY NOTE:
# Protect your tokens! They are like passwords.
# Use read-only tokens when possible for safety.

'''
        
        full_content = header + content
        
        try:
            with open(example_file, 'w', encoding='utf-8', newline='\n') as f:
                f.write(full_content)
            return example_file
        except (IOError, OSError) as e:
            raise Exception(f"Failed to create example config: {e}")
