# TVer TUI

Terminal UI for exploring series on [TVer.jp](https://tver.jp). Browse seasons, episodes, subtitle availability, and air dates. Requires a Japanese IP (VPN).

## Setup

**Requirements**: Python 3.10+, [uv](https://docs.astral.sh/uv/), VPN with a Japanese exit node

```bash
git clone https://github.com/bry5an/tver-tui.git
cd tver-tui
uv sync
uv run tver-tui
```

## Usage

1. Paste a TVer series URL or bare series ID into the input bar and press **Enter**

   ```
   https://tver.jp/series/sruj1jr2s1
   ```
   or just the ID:
   ```
   sruj1jr2s1
   ```

2. After loading, focus moves automatically to the seasons list
3. Navigate seasons with **↑ ↓** — the episode list updates as you move
4. Jump to the episodes pane and navigate with **↑ ↓**
5. Press **o** to open the highlighted episode in your browser

### Key bindings

| Key | Action |
|-----|--------|
| `/` | Jump to search input |
| `s` | Jump to seasons list |
| `e` | Jump to episodes table |
| `↑` `↓` | Move through seasons / episodes |
| `o` | Open highlighted episode in browser |
| `r` | Re-fetch current series |
| `q` | Quit |

### Episode columns

| Column | Meaning |
|--------|---------|
| Title | Episode title |
| Aired | Broadcast date (日本語) |
| CC | `✓` = subtitles available |
| Dur | Duration in minutes |
| Exp | Days until content expires (yellow < 7 days) |

### IP status

The header subtitle shows your detected IP and country on startup. If you're not on a Japanese IP, it shows a warning — TVer content will likely be unavailable.

## Finding series IDs

Navigate to any series page on [tver.jp](https://tver.jp) and copy the URL. The series ID is the last path segment and starts with `sr`:

```
https://tver.jp/series/sr9gfdf2ex
                        ^^^^^^^^^^  ← series ID
```

## License

MIT
