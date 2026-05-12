from __future__ import annotations

import webbrowser

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
    Tree,
)

from .api import Season, SeriesInfo, TVerAPIError, TVerClient, parse_series_id
from .config import ConfigSeries, load_config
from .db import SubtitleCounts, get_subtitle_counts
from .vpn import check_ip

_CSS = """
Screen {
    layout: vertical;
}

#url-bar {
    height: 3;
    layout: horizontal;
}

#url-bar > Input {
    width: 1fr;
}

#url-bar > Button {
    width: 10;
}

#series-info {
    height: 1;
    padding: 0 1;
    background: $boost;
    color: $text-muted;
}

#browser {
    height: 1fr;
}

#config-pane {
    width: 40;
    border-right: solid $border;
    layout: vertical;
}

#config-header {
    height: 1;
    padding: 0 1;
    background: $boost;
    color: $text-muted;
    text-style: bold;
}

#config-tree {
    height: 1fr;
}

#seasons-pane {
    width: 26;
    border-right: solid $border;
    layout: vertical;
}

#seasons-header {
    height: 1;
    padding: 0 1;
    background: $boost;
    color: $text-muted;
    text-style: bold;
}

#seasons-list {
    height: 1fr;
}

#episodes-pane {
    width: 1fr;
    layout: vertical;
}

#episodes-header {
    height: 1;
    padding: 0 1;
    background: $boost;
    color: $text-muted;
    text-style: bold;
}

#episodes-table {
    height: 1fr;
}
"""


class TVerTUI(App[None]):
    """TVer series browser."""

    TITLE = "TVer TUI"
    CSS = _CSS

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("o", "open_episode", "Open in browser"),
        Binding("r", "refresh_series", "Refresh"),
        Binding("/", "focus_input", "Search"),
        Binding("c", "focus_config", "Config"),
        Binding("s", "focus_seasons", "Seasons"),
        Binding("e", "focus_episodes", "Episodes"),
        Binding("ctrl+l", "focus_input", show=False),
    ]

    _series: SeriesInfo | None = None
    _config_nodes: dict[str, tuple]  # url -> (TreeNode, ConfigSeries)

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            with Horizontal(id="url-bar"):
                yield Input(
                    placeholder="TVer series URL or ID  (e.g. https://tver.jp/series/sr…)",
                    id="url-input",
                )
                yield Button("Fetch", variant="primary", id="fetch-btn")
            yield Static("Enter a series URL or ID above to get started.", id="series-info")
            with Horizontal(id="browser"):
                with Vertical(id="config-pane"):
                    yield Static("Config", id="config-header")
                    yield Tree("root", id="config-tree")
                with Vertical(id="seasons-pane"):
                    yield Static("Seasons", id="seasons-header")
                    yield ListView(id="seasons-list")
                with Vertical(id="episodes-pane"):
                    yield Static("Episodes", id="episodes-header")
                    yield DataTable(id="episodes-table")
        yield Footer()

    def on_mount(self) -> None:
        self._config_nodes = {}
        table = self.query_one("#episodes-table", DataTable)
        table.cursor_type = "row"
        table.add_column("Title")
        table.add_column("Aired", width=16)
        table.add_column("CC", width=3)
        table.add_column("Dur", width=5)
        table.add_column("Exp", width=7)
        self._load_config_tree()
        self._check_ip()

    def _load_config_tree(self) -> None:
        tree = self.query_one("#config-tree", Tree)
        tree.show_root = False
        tree.show_guides = True
        groups = load_config()
        for group in groups:
            group_node = tree.root.add(group.name.replace("_", " "), expand=True)
            for series in group.series:
                label = self._series_label(series)
                node = group_node.add_leaf(label, data=series)
                self._config_nodes[series.url] = (node, series)
        if not groups:
            tree.root.add_leaf("(no config found)", data=None)
        self._fetch_subtitle_status()

    @staticmethod
    def _series_label(series: ConfigSeries, counts: SubtitleCounts | None = None) -> Text:
        label = Text(series.name)
        if not series.subtitles:
            label.append(" ·cc", style="dim")
            return label
        if counts is not None:
            problem = counts.missing + counts.untracked
            if problem:
                label.append(f" ✗{problem}", style="red bold")
            if counts.available:
                label.append(f" ↓{counts.available}", style="yellow bold")
            if counts.not_available:
                label.append(f" ?{counts.not_available}", style="dim")
        return label

    def _fetch_subtitle_status(self) -> None:
        urls = list(self._config_nodes.keys())
        if not urls:
            return

        def _run() -> None:
            ids: list[str] = []
            id_to_url: dict[str, str] = {}
            for url in urls:
                try:
                    sid = parse_series_id(url)
                    ids.append(sid)
                    id_to_url[sid] = url
                except Exception:
                    pass
            counts = get_subtitle_counts(ids)
            self.call_from_thread(self._apply_subtitle_status, counts, id_to_url)

        self.run_worker(_run, thread=True)

    def _apply_subtitle_status(
        self, counts: dict[str, SubtitleCounts], id_to_url: dict[str, str]
    ) -> None:
        tree = self.query_one("#config-tree", Tree)
        for sid, url in id_to_url.items():
            entry = self._config_nodes.get(url)
            if entry is None:
                continue
            node, series = entry
            node.label = self._series_label(series, counts.get(sid))
        tree.refresh()

    # ── IP check ────────────────────────────────────────────────────────────

    def _check_ip(self) -> None:
        def _run() -> None:
            is_jp, country, ip = check_ip()
            self.call_from_thread(self._apply_ip_status, is_jp, country, ip)

        self.run_worker(_run, thread=True)

    def _apply_ip_status(self, is_jp: bool, country: str, ip: str) -> None:
        if is_jp:
            self.sub_title = f"JP ✓  {ip}"
        else:
            self.sub_title = f"⚠ Non-JP IP ({country}: {ip}) — TVer may be unavailable"

    # ── Fetch ────────────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "fetch-btn":
            self._do_fetch()

    def on_input_submitted(self, _: Input.Submitted) -> None:
        self._do_fetch()

    def _do_fetch(self) -> None:
        raw = self.query_one("#url-input", Input).value.strip()
        if not raw:
            return
        self.query_one("#fetch-btn", Button).disabled = True
        self.query_one("#series-info", Static).update("Fetching…")
        self._fetch_series(raw)

    def _fetch_series(self, raw: str) -> None:
        def _run() -> None:
            try:
                series_id = parse_series_id(raw)
                info = TVerClient().get_series(series_id)
                self.call_from_thread(self._apply_series, info)
            except TVerAPIError as e:
                self.call_from_thread(self._apply_error, str(e))
            except Exception as e:
                self.call_from_thread(self._apply_error, f"Unexpected error: {e}")
            finally:
                self.call_from_thread(
                    lambda: setattr(self.query_one("#fetch-btn", Button), "disabled", False)
                )

        self.run_worker(_run, thread=True, exclusive=True, exit_on_error=False)

    def _apply_series(self, info: SeriesInfo) -> None:
        self._series = info
        n_seasons = len(info.seasons)
        n_eps = info.episode_count
        n_cc = info.subtitle_count
        broadcaster = f"  |  {info.broadcaster}" if info.broadcaster else ""
        self.query_one("#series-info", Static).update(
            f"[bold]{info.title}[/bold]{broadcaster}"
            f"  |  {n_seasons} season(s)  |  {n_eps} ep(s)"
            f"  |  CC: {n_cc}/{n_eps}"
        )
        seasons_list = self.query_one("#seasons-list", ListView)
        seasons_list.clear()
        for season in info.seasons:
            cc = sum(1 for ep in season.episodes if ep.has_subtitles)
            label = f"{season.title}  ({len(season.episodes)})"
            if cc:
                label += f"  [CC:{cc}]"
            seasons_list.append(ListItem(Label(label)))
        if info.seasons:
            self._render_season(info.seasons[0])
            self.query_one("#seasons-list", ListView).focus()

    def _apply_error(self, msg: str) -> None:
        self.query_one("#series-info", Static).update(f"[red]Error:[/red] {msg}")
        self.notify(msg, title="Fetch failed", severity="error")

    # ── Season / episode display ─────────────────────────────────────────────

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if self._series is None or event.item is None:
            return
        idx = self.query_one("#seasons-list", ListView).index
        if idx is not None and idx < len(self._series.seasons):
            self._render_season(self._series.seasons[idx])

    def _render_season(self, season: Season) -> None:
        cc_total = sum(1 for ep in season.episodes if ep.has_subtitles)
        self.query_one("#episodes-header", Static).update(
            f"Episodes — {season.title}  ({len(season.episodes)} ep(s)"
            + (f", CC: {cc_total}" if cc_total else "")
            + ")"
        )
        table = self.query_one("#episodes-table", DataTable)
        table.clear()
        for ep in season.episodes:
            title = Text(ep.title)
            if not ep.is_available:
                title.stylize("dim")

            cc = Text("✓", style="green bold") if ep.has_subtitles else Text("·", style="dim")

            exp = Text(ep.expires_display)
            days = ep.expires_days
            if days < 0:
                exp.stylize("red")
            elif days < 7:
                exp.stylize("yellow")

            table.add_row(title, ep.broadcast_date, cc, ep.duration_display, exp)

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_open_episode(self) -> None:
        if self._series is None:
            return
        seasons_list = self.query_one("#seasons-list", ListView)
        season_idx = seasons_list.index
        if season_idx is None:
            return
        season = self._series.seasons[season_idx]
        table = self.query_one("#episodes-table", DataTable)
        row = table.cursor_row
        if 0 <= row < len(season.episodes):
            ep = season.episodes[row]
            webbrowser.open(ep.url)
            self.notify(f"Opened: {ep.title}", title="Browser")

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        series: ConfigSeries | None = event.node.data
        if series is None:
            return
        inp = self.query_one("#url-input", Input)
        inp.value = series.url
        self._do_fetch()

    def action_focus_config(self) -> None:
        self.query_one("#config-tree", Tree).focus()

    def action_focus_input(self) -> None:
        self.query_one("#url-input", Input).focus()

    def action_focus_seasons(self) -> None:
        self.query_one("#seasons-list", ListView).focus()

    def action_focus_episodes(self) -> None:
        self.query_one("#episodes-table", DataTable).focus()

    def action_refresh_series(self) -> None:
        self._do_fetch()


def main() -> None:
    TVerTUI().run()
