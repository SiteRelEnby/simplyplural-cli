# Simply Plural CLI

A command-line interface for [Simply Plural](https://apparyllis.com/), designed for systems who spend a lot of time in terminal/IDE environments. There are also plans to in the future provide system-related functionality for other development tools.

## Features

- **Quick switch registration** - `sp switch Luna`, `sp sw Johnny V`, `sp switch --add` Dax, etc
- **Current fronter status** - `sp fronting`, `sp who`, or `sp w`
- **Shell prompt integration** - Show fronters in your terminal prompt
- **Member management** - List and view member information
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
```bash
# Switch to a single member
sp switch Luna
sp sw Luna      # alias

# Multiple fronters
sp switch Johnny V

# Add co-fronter to existing fronters
sp switch --co Victoria
sp switch --add Amber

# Add a note to the switch
sp switch seraph --note "wouldn't come alive in a perfect life, but that can't be mine"
```

### Status Checking
```bash
# Show current fronters (human readable)
sp fronting
sp who  # alias
sp w    # alias

# Different output formats
sp who --format=simple    # Just names: "Johnny, V"
sp who --format=json      # JSON for scripts
sp who --format=prompt    # For shell prompts: "[Johnny, V] "
```

### Member Information
```bash
# List all members
sp members

# Show only current fronters
sp members --fronting
```

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

Show current fronters in your terminal prompt! The shell integration displays your current fronters directly in your bash or zsh prompt.

### Features
- **Fast updates** - Reads from local cache file (~1ms)
- **Background refresh** - Automatically updates when cache expires
- **Non-blocking** - Never slows down your prompt
- **Cross-shell** - Works with bash, zsh, and others
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
user@host:~/project [Alice] $ sp switch Bob
[OK] Switched to Bob
user@host:~/project (updating) $ 
user@host:~/project [Bob] $ 

# Multiple fronters
user@host:~/project [Alice, Bob] $ 

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

# Multi-profile support:
[friend-system]
api_token = friend-token-here
default_output_format = json
```

## API Etiquette & Rate Limits

Simply Plural is run by a small team and their API is a shared resource.

This CLI is configured with **conservative defaults** that respect the API:

- **Fronters**: Cached for 30 minutes
- **Members**: Cached for 1 hour
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
- **File cache**: 15 minutes for fronters, 30 minutes for switches, 1 hour for members
- **Automatic retry logic**: Backs off on errors instead of hammering
- **Offline mode**: Works with cached data when offline

Cache is stored in:
- **Linux**: `~/.cache/simply-plural/`
- **macOS**: `~/Library/Caches/simply-plural/`
- **Windows**: `%LOCALAPPDATA%\\simply-plural\\`

## Advanced Usage

### JSON Output for Scripts
```bash
# Get fronters as JSON
sp fronting --format=json
# Output: {"fronters": ["Johnny", "V"]}
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
```

## Known issues

* Shell integration's background refresh sometimes gets stuck, resulting in (updating). Registering any switch or refetching current fronters should fix this.

## Contributing

Feel free to submit issues and pull requests.
## Caching

The CLI uses smart caching to improve performance:

- **Memory cache**: 30 seconds for fronters, 5 minutes for members
- **File cache**: 5 minutes for fronters, 1 hour for members
- **Rate limiting**: Respects API limits with automatic backoff
- **Offline mode**: Works with cached data when offline

Cache is stored in:
- **Linux**: `~/.cache/simply-plural/`
- **macOS**: `~/Library/Caches/simply-plural/`
- **Windows**: `%LOCALAPPDATA%\\simply-plural\\`

## Advanced Usage

### JSON Output for Scripts
```bash
# Get fronters as JSON
sp fronting --format=json
# Output: {"fronters": ["Johnny", "V"]}
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
```

## Contributing

Feel free to submit issues and pull requests.

---

Trans rights are human rights 🏳️‍⚧️
