# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install / sync dependencies
uv sync

# Run the TUI
uv run tver-tui

# Lint
uvx ruff check .
uvx ruff format .
```

## Architecture

A Python terminal UI (Textual 8.x) for browsing TVer.jp series metadata. Requires a Japanese IP.

**Entry point**: `tver_tui/app.py` → `TVerTUI(App)` → `main()`

### Modules

- **`api.py`** — `TVerClient` fetches seasons and episodes from the TVer API. Data flows: `init_session()` (POST to platform-api to get `platform_uid`/`platform_token`) → `get_series(series_id)` → returns a `SeriesInfo` dataclass with nested `Season` → `Episode`. The platform tokens are required for the `callSeasonEpisodes` endpoint but not for `callSeriesSeasons`.

- **`vpn.py`** — `check_ip()` queries geo-IP services and returns `(is_jp, country, ip)`. Called at startup in a background thread; result appears in the app's header subtitle.

- **`app.py`** — `TVerTUI(App)` with inline TCSS. Long-running API calls run via `self.run_worker(fn, thread=True)` and update the UI via `self.call_from_thread(callback, ...)`. Workers use `exclusive=True` so a new fetch cancels any in-flight one.

### TVer API endpoints

| Endpoint | Auth needed | Purpose |
|---|---|---|
| `POST platform-api.tver.jp/v2/api/platform_users/browser/create` | No | Get `platform_uid` / `platform_token` |
| `GET service-api.tver.jp/api/v1/callSeriesSeasons/{series_id}` | No | List seasons for a series |
| `GET platform-api.tver.jp/service/api/v1/callSeasonEpisodes/{season_id}` | Yes (query params) | List episodes for a season |

Series IDs start with `sr`, season IDs with `ss`, episode IDs with `ep`.

### Key data fields (from `content` object in API response)

`id`, `title`, `seriesTitle`, `broadcastDateLabel`, `isSubtitle` (CC), `isAvailable`, `duration` (seconds, sometimes absent — fall back to `resume.contentDuration`), `endAt` (Unix expiry), `broadcasterName`

### UI layout

```
Header  [title]  [sub_title = IP status]
────────────────────────────────────────
[URL input                    ] [Fetch ]
[series info bar                       ]
┌── Seasons (30c) ──┬── Episodes table ─┐
│ > 本編 (12) [CC:3]│ Title | Aired | …  │
│   予告 (3)        │                   │
└───────────────────┴───────────────────┘
Footer  [q Quit] [o Open] [r Refresh]
```

Highlighting a season immediately renders its episodes. `o` opens the highlighted episode in the default browser.

## Hard rules

- YOU MUST NOT commit or push without explicit user request.
- YOU MUST NOT add Co-Authored-By: Claude to any commit message.
