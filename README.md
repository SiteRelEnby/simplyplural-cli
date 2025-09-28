# Simply Plural CLI

A command-line interface for [Simply Plural](https://apparyllis.com/), designed for systems who spend a lot of time in terminal/IDE environments. There are also plans to in the future provide system-related functionality for other development tools.

## Features

- **Quick switch registration** - `sp switch Luna`, `sp sw Johnny V`, `sp switch --add Dax`, etc
- **Current fronter status** - `sp fronting`, `sp who`, or `sp w` with type indicators
- **Shell prompt integration** - Show fronters in your terminal prompt
- **Member and custom front management** - List and view information for both types
- **Switch history** - View recent switches and patterns
- **Backup/export** - Export your data **(WARNING: This feature is not complete, and should not be relied on as your only backup!)**
- **Offline-friendly** - Configurable caching reduces API calls, degrades gracefully, and works offline
- **Cross-platform** - Python 3.x with minimal, easily-findable dependencies.

## Installation

### Quick Start
```bash
# Clone or download the files
git clone https://github.com/SiteRelEnby/simply-plural-cli.git
cd simply-plural-cli

# Run the setup script (recommended)
python3 setup.py

# Or install manually:
python3 -m pip install requests
python3 sp.py config --setup
```

### Unix/Linux/macOS Installation
```bash
# Automatic installation
chmod +x install.sh
./install.sh

# Then you can use 'sp' from anywhere
sp --help
```

### Manual Installation
```bash
# Install dependencies
python3 -m pip install requests

# Copy to your PATH
[[ ! -d ~/bin ]] && mkdir ~/bin
cp sp.py ~/bin/sp
chmod +x ~/bin/sp

# Or create a symlink
ln -s /path/to/sp.py ~/bin/sp
```

### Windows Installation
```cmd
# Install dependencies
python -m pip install requests

# Copy to a directory in your PATH or use full path
copy sp.py C:\Users\%USERNAME%\bin\sp.py
```

### Setup
```bash
# Run the setup wizard
sp config --setup
```

You'll need to get a token from Simply Plural:
1. Open Simply Plural app
2. Go to Settings → Account → Tokens
3. Create a new token with appropriate permissions:
   - **Read-only**: Safe for viewing fronters, members, and history
   - **Read + Write**: Required for registering switches (`sp switch` command)
   - **Delete**: NOT recommended (this program doesn't need it)

**Security Note**: Tokens are like passwords. Use read-only tokens in shared environments or when you only need to view data. Only use write permissions on trusted devices.

## Basic Usage

### Switch Management

The CLI supports both **members** and **custom fronts** seamlessly. Use any name in switch commands - the CLI automatically detects whether it's a member or custom front.

```bash
# Switch to a single member
sp switch Luna
sp sw Luna      # alias

# Multiple fronters (any combination of members and custom fronts)
sp switch Johnny V

# Add co-fronter to existing fronters
sp switch --co Victoria
sp switch --add Amber

# Add a note to the switch
sp switch seraph --note "wouldn't come alive in a perfect life, but that can't be mine"
```

### Status Checking

The fronting status shows **type indicators** to distinguish between members and custom fronts:

```bash
# Show current fronters (human readable)
sp fronting
# Example output: "Currently fronting: Alice, ^Garnet"

sp who  # alias
sp w    # alias

# Different output formats
sp who --format=simple    # Just names: "Alice, ^Garnet"
sp who --format=json      # JSON for scripts
sp who --format=prompt    # For shell prompts: "[Alice, ^Garnet] "
```

**Type indicators** (configurable):
- Members: No indicator (e.g., "Alice")
- Custom fronts: "^" prefix by default (e.g., "^Garnet")
- Can be configured to use text style: "Garnet (custom front)"
- Can be disabled entirely

### Member and Custom Front Information

```bash
# List all members
sp members

# List all custom fronts
sp custom-fronts

# List both members and custom fronts together
sp members --include-custom

# Show only current fronters
sp members --fronting
```

### Custom Front Features

Custom fronts work identically to members in all commands:

```bash
# List all custom fronts with descriptions
sp custom-fronts

# Switch to custom fronts just like members
sp switch Garnet
sp switch Crystal Rose    # multiple custom fronts

# All other commands work the same way
sp history    # Shows switches including custom fronts
sp fronting   # Shows current fronters with type indicators
```

The CLI automatically detects whether a name refers to a member or custom front, so you never need to specify the type manually.

### History
```bash
# Recent switches
sp history

# Today's switches only
sp history --today

# This week's switches
sp history --week

# Limit number of results (max 1000)
sp history --count 20
```

**Note**: The `--count` parameter is limited to 1000 switches to prevent excessive API calls and memory usage. The API doesn't enforce hard limits, but our client includes reasonable safeguards.

### Data Management
```bash
# Backup all data
sp backup

# Backup to specific file
sp backup --output backup-file-name.json

# View configuration
sp config --show
```

**Note**: The backup command creates a limited export containing recent data (up to 1000 switches due to API limitationss), and does not back up *all* account data. For complete account backup, use Simply Plural app's native export feature in Settings.

## Shell Integration

Show current fronters in your terminal prompt! The shell integration displays your current fronters directly in your bash or zsh prompt, with type indicators for custom fronts.

### Features
- **Fast updates** - Reads from local cache file (~1ms)
- **Background refresh** - Automatically updates when cache expires
- **Non-blocking** - Never slows down your prompt
- **Cross-shell** - Works with bash, zsh, and others
- **Type indicators** - Shows custom fronts with visual distinction
- **Graceful degradation** - Shows "(updating)" while fetching data

### Quick Setup

```bash
# Generate integration script
sp shell install

# Follow the displayed instructions to add to your shell config
```

### Manual Setup

1. **Generate the integration script**:
   ```bash
   sp shell generate
   ```

2. **Add to your shell config**:
   
   **For Bash** (`~/.bashrc`):
   ```bash
   # Simply Plural integration
   source ~/.config/simply-plural/shell/integration.sh
   PS1="\$(sp_prompt)$PS1"
   ```
   
   **For Zsh** (`~/.zshrc`):
   ```bash
   # Simply Plural integration
   source ~/.config/simply-plural/shell/integration.sh
   PROMPT="\$(sp_prompt)$PROMPT"
   ```

3. **Restart your shell** or run:
   ```bash
   source ~/.bashrc   # or ~/.zshrc
   ```

### How It Works

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Your Prompt   │───▶│   Cache File     │───▶│ Background      │
│   (instant)     │    │ ~/.cache/sp_status│    │ API Updates     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
        ~1ms                    ~10ms                 ~200ms
```

- **Prompt display**: Instantly reads current status from cache file
- **Background refresh**: When cache expires (15+ minutes), triggers API update
- **Smart caching**: Balances responsiveness with API politeness

### Example Output

```bash
# Normal usage
user@host:~/project [Alice] $ sp switch Garnet
[OK] Switched to Garnet
user@host:~/project (updating) $ 
user@host:~/project [Garnet] $ 

# Multiple fronters including custom fronts
user@host:~/project [Alice, ^Garnet] $ 

# When updating
user@host:~/project (updating) $ 

# When offline/error
user@host:~/project (error) $ 
```

### Advanced Configuration

Customize update frequency in your config:

```ini
# How often to check for updates (seconds)
shell_update_interval = 60    # Default: 1 minute

# Cache settings affect shell integration
cache_fronters_ttl = 900      # 15 minutes (default)
```

### Testing Shell Integration

Use the test utility to verify everything works:

```bash
# Run isolated test environment
./test-shell.sh

# Manual testing
sp _internal_update_status     # Update status file
cat ~/.cache/sp_status         # Check status content
sp --debug _internal_update_status  # Debug output
```

### Troubleshooting

**Prompt not updating**:
- Check that `sp _internal_update_status` runs without errors
- Verify the status file exists: `ls ~/.cache/sp_status`
- Make sure you sourced the integration script in your shell config

**Shows "(updating)" constantly**:
- Check your API token: `sp config --show`
- Test manual command: `sp fronting`
- Check debug output: `sp --debug _internal_update_status`

**Integration script not found**:
- Run `sp shell generate` to create it
- Check the path: `ls ~/.config/simply-plural/shell/integration.sh`

**Slow prompt**:
- The integration should never slow your prompt (it's designed to be ~1ms)
- If you're seeing delays, check for conflicts with other prompt modifications
- Use `time sp_prompt` to measure performance

## Configuration

Configuration is stored in platform-appropriate locations:
- **Linux**: `~/.config/simply-plural/simplyplural.conf`
- **macOS**: `~/Library/Application Support/simply-plural/simplyplural.conf`  
- **Windows**: `%APPDATA%\\simply-plural\\simplyplural.conf`

### Options
```bash
# View current config
sp config --show

# View example config
sp config --example

# The config file uses key=value format:
[default]
api_token = your-token-here
default_output_format = human
cache_custom_fronts_ttl = 3600

# Custom front display options
show_custom_front_indicators = true          # Enable/disable type indicators
custom_front_indicator_style = character     # "character" or "text"
custom_front_indicator_character = ^         # Character to use for prefix style

# Multi-profile support:
[friend-system]
api_token = friend-token-here
default_output_format = json
```

#### Custom Front Display Configuration

You can customize how custom fronts are displayed:

**Indicator Styles:**
```ini
# Character style (default): "^Garnet"
custom_front_indicator_style = character
custom_front_indicator_character = ^

# Text style: "Garnet (custom front)"
custom_front_indicator_style = text

# Disable indicators entirely: "Garnet"
show_custom_front_indicators = false
```

**Custom Characters:**
```ini
# Different character options
custom_front_indicator_character = *    # "*Garnet"
custom_front_indicator_character = @    # "@Garnet"
custom_front_indicator_character = #    # "#Garnet"
```

## API Etiquette & Rate Limits

Simply Plural is run by a small team and their API is a shared resource.

This CLI is configured with **conservative defaults** that respect the API:

- **Fronters**: Cached for 15 minutes
- **Members**: Cached for 1 hour
- **Custom fronts**: Cached for 1 hour
- **Switches**: Cached for 30 minutes
- **Background refresh**: Only when cache expires
- **Backoff retry logic**: Backs off on errors instead of hammering

### Official API Guidelines

Per the [Simply Plural API documentation](https://docs.apparyllis.com/docs/getting-started/intro#rate-limits):

> "We don't rate limit requests, however if you are going to request updates to data in a frequent interval (more than once per 30 minutes) we would ask that you implement a socket connection."

The defaults should work fine for normal usage with minimal lag. **Please don't**:
- Set very low cache TTLs
- Use this tool in scripts that hammer the API in tight loops
- Disable caching just because you can
- Run large numbers of parallel requests

### High-Frequency Updates

If you genuinely need near-real-time updates (more frequent than every 30 minutes), consider:

1. **WebSocket connections** - See the [Socket documentation](https://docs.apparyllis.com/docs/getting-started/socket)
2. **Contributing** - PRs are welcome if you want to add socket support! 🚀

## Caching

The CLI uses smart caching to improve performance:

- **Memory cache**: 5 minutes for all data types (instant access)
- **File cache**: 15 minutes for fronters, 30 minutes for switches, 1 hour for members and custom fronts
- **Automatic retry logic**: Backs off on errors instead of hammering
- **Offline mode**: Works with cached data when offline

Cache is stored in:
- **Linux**: `~/.cache/simply-plural/`
- **macOS**: `~/Library/Caches/simply-plural/`
- **Windows**: `%LOCALAPPDATA%\\simply-plural\\`

## Advanced Usage

### JSON Output for Scripts

```bash
# Get fronters as JSON (includes type information)
sp fronting --format=json
# Example output: {"fronters": [{"name": "Ruby", "type": "member"}, {"name": "Sapphire", "type": "member"}, {"name": "Garnet", "type": "custom_front"}]}

# Get custom fronts as JSON
sp custom-fronts --format=json
```

### Multi-Profile Support

The CLI supports multiple Simply Plural accounts:

```bash
# Create a profile for a friend's system
sp config --create-profile friend-system

# Use different profile
sp --profile friend-system fronting
sp --profile friend-system switch Alice

# List all profiles
sp config --list-profiles
```

## Troubleshooting

### Common Issues

**"Error: Missing required dependencies"**
- The CLI will automatically check for required dependencies and tell you exactly what to install
- Run the suggested `pip3 install` command
- If you have multiple Python versions, try `python3 -m pip install requests`

**"Error: Not configured"**
- Run `sp config --setup` to set up your token

**"Connection failed"**
- Check your internet connection
- API might be temporarily down
- CLI will use cached data when possible

**"Name 'X' not found" when switching**
- The name might not exist as either a member or custom front
- Check available names: `sp members --include-custom`
- Names are case-sensitive by default

**"Ambiguous name 'X'" when switching**
- You have both a member and custom front with the same name
- The error message will show which entities matched
- This is rare but can happen if you have identical names

**Shell integration issues**
- See the [Shell Integration](#shell-integration) section for detailed troubleshooting

### Debug Mode
```bash
# See what's in cache
ls ~/.cache/simply-plural/

# Test API connection
sp fronting --format=json

# Check configuration
sp config --show

# Debug custom front functionality
sp --debug custom-fronts
sp --debug switch Garnet
```

## Custom Front Technical Details

For developers and advanced users:

- **API Integration**: Uses `/v1/customFronts/{systemId}` and `/v1/customFront/{systemId}/{customFrontId}` endpoints
- **Switching Mechanism**: Same frontHistory API as members, distinguished by `custom: true/false` field
- **Caching**: Custom fronts cached separately with configurable TTL (default 1 hour)
- **Name Resolution**: Unified lookup system handles both entity types automatically
- **Type Detection**: API responses include `custom` field for proper type indicators

## Known Issues

* Shell integration's background refresh sometimes gets stuck, resulting in (updating). Registering any switch or refetching current fronters should fix this.
* Custom front and member names are case-sensitive for exact matching

## Contributing

Feel free to submit issues and pull requests. Areas where contributions are especially welcome:

- WebSocket support for real-time updates
- Additional output formats
- Enhanced name matching (fuzzy/case-insensitive)
- Platform-specific integrations

---

Trans rights are human rights 🏳️‍⚧️
