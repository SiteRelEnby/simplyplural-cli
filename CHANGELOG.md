# Changelog

All notable changes to simplyplural-cli are documented here.

## [0.1.0] - 2026-02-07

Initial release.

### Core CLI
- Switch management: `sp switch`, `sp sw` with single or multiple fronters
- Co-fronting: `sp switch --co`/`--add` to add fronters without replacing
- Switch notes: `sp switch --note "..."`
- Fronter status: `sp fronting`, `sp who`, `sp w`
- Output formats: text, simple, json, prompt
- Member listing: `sp members` with `--fronting` filter
- Custom front support: automatic detection, type indicators (`^Name`),
  configurable indicator style (character, text, or hidden)
- Switch history: `sp history` with `--today`, `--week`, `--count` filters
- Data backup: `sp backup` (limited export, up to 1000 switches)
- Version command: `sp --version` / `sp version`
- Debug mode: `sp --debug` for troubleshooting

### Daemon Mode
- Background WebSocket daemon for real-time updates (`sp daemon start`)
- Instant CLI responses via Unix domain socket IPC (<1ms vs ~200-500ms)
- Auto-start: daemon launches automatically when CLI is used (`start_daemon = true` by default)
- Per-profile daemon instances
- Fronter name resolution from in-memory member/custom front data
- Transparent fallback to REST API when daemon is unavailable

### Shell Integration
- Show current fronters in bash/zsh prompt
- Daemon-first updates with cache fallback
- Non-blocking, ~1ms prompt reads from status file
- Background refresh when cache expires
- Staleness indicator (`~[names]`) for stale cached data
- `sp shell install` / `sp shell generate` setup commands

### Configuration
- INI-based config with setup wizard (`sp config --setup`)
- Multi-profile support (`sp --profile <name>`)
- Configurable cache TTLs (fronters, members, switches, custom fronts)
- Custom front display settings (indicator style, character)
- Example config: `sp config --example`
- Platform-appropriate config/cache directories (Linux, macOS, Windows)

### Infrastructure
- Installable Python package (`pip install simplyplural-cli`)
- `src/` layout with `pyproject.toml`
- GitHub Actions CI (Python 3.9-3.13 test matrix + build verification)
- Automated PyPI release workflow (tag-triggered, trusted publishing)
- 68 tests
