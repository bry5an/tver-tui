from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime

import certifi

_HEADERS = {
    "x-tver-platform-type": "web",
    "Origin": "https://tver.jp",
    "Referer": "https://tver.jp/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


class TVerAPIError(Exception):
    pass


@dataclass
class Episode:
    id: str
    title: str
    series_title: str
    broadcast_date: str
    has_subtitles: bool
    is_available: bool
    duration_seconds: int
    end_at: int
    broadcaster: str

    @property
    def url(self) -> str:
        return f"https://tver.jp/episodes/{self.id}"

    @property
    def duration_display(self) -> str:
        if not self.duration_seconds:
            return "—"
        return f"{self.duration_seconds // 60}m"

    @property
    def expires_display(self) -> str:
        if not self.end_at:
            return "—"
        days = (self.end_at - datetime.now().timestamp()) / 86400
        if days < 0:
            return "expired"
        if days < 1:
            return "today"
        return f"{int(days)}d"

    @property
    def expires_days(self) -> float:
        if not self.end_at:
            return 9999
        return (self.end_at - datetime.now().timestamp()) / 86400


@dataclass
class Season:
    id: str
    title: str
    episodes: list[Episode] = field(default_factory=list)


@dataclass
class SeriesInfo:
    id: str
    title: str
    broadcaster: str
    seasons: list[Season] = field(default_factory=list)

    @property
    def episode_count(self) -> int:
        return sum(len(s.episodes) for s in self.seasons)

    @property
    def subtitle_count(self) -> int:
        return sum(1 for s in self.seasons for ep in s.episodes if ep.has_subtitles)


class TVerClient:
    """Minimal TVer API client for series browsing."""

    def __init__(self) -> None:
        self._uid: str | None = None
        self._token: str | None = None
        self._ssl = ssl.create_default_context(cafile=certifi.where())

    def _request(self, url: str, data: bytes | None = None) -> dict:
        req = urllib.request.Request(
            url, data=data, headers=_HEADERS, method="POST" if data else "GET"
        )
        try:
            with urllib.request.urlopen(req, context=self._ssl) as r:
                return json.loads(r.read().decode())
        except ssl.SSLError:
            self._ssl = ssl._create_unverified_context()
            with urllib.request.urlopen(req, context=self._ssl) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise TVerAPIError(f"HTTP {e.code}: {e.reason}") from e
        except Exception as e:
            raise TVerAPIError(str(e)) from e

    def _init_session(self) -> None:
        resp = self._request(
            "https://platform-api.tver.jp/v2/api/platform_users/browser/create",
            data=b"device_type=pc",
        )
        result = resp.get("result", {})
        self._uid = result.get("platform_uid")
        self._token = result.get("platform_token")
        if not self._uid:
            raise TVerAPIError("Failed to obtain platform credentials from TVer")

    def _authed_url(self, url: str) -> str:
        params = {"platform_uid": self._uid, "platform_token": self._token}
        sep = "&" if "?" in url else "?"
        return url + sep + urllib.parse.urlencode(params)

    def get_series(self, series_id: str) -> SeriesInfo:
        if not self._uid:
            self._init_session()

        seasons_resp = self._request(
            f"https://service-api.tver.jp/api/v1/callSeriesSeasons/{series_id}"
        )
        contents = seasons_resp.get("result", {}).get("contents", [])

        seasons: list[Season] = [
            Season(id=item["content"]["id"], title=item["content"].get("title", "Unknown"))
            for item in contents
            if item.get("type") == "season" and item.get("content", {}).get("id")
        ]

        if not seasons:
            raise TVerAPIError("No seasons found — check that the ID is a series (starts with 'sr')")

        series_title = ""
        broadcaster = ""

        for season in seasons:
            url = self._authed_url(
                f"https://platform-api.tver.jp/service/api/v1/callSeasonEpisodes/{season.id}"
            )
            ep_resp = self._request(url)
            for item in ep_resp.get("result", {}).get("contents", []):
                if item.get("type") != "episode":
                    continue
                c = item.get("content", {})
                ep_id = c.get("id")
                if not ep_id:
                    continue

                duration = (
                    c.get("duration")
                    or item.get("resume", {}).get("contentDuration", 0)
                    or 0
                )
                end_at = c.get("endAt") or item.get("endAt", 0) or 0

                ep = Episode(
                    id=ep_id,
                    title=c.get("title", ""),
                    series_title=c.get("seriesTitle", ""),
                    broadcast_date=c.get("broadcastDateLabel", ""),
                    has_subtitles=bool(c.get("isSubtitle")),
                    is_available=bool(c.get("isAvailable", True)),
                    duration_seconds=int(duration),
                    end_at=int(end_at),
                    broadcaster=c.get("broadcasterName", ""),
                )
                season.episodes.append(ep)

                if not series_title and ep.series_title:
                    series_title = ep.series_title
                if not broadcaster and ep.broadcaster:
                    broadcaster = ep.broadcaster

        return SeriesInfo(
            id=series_id,
            title=series_title or series_id,
            broadcaster=broadcaster,
            seasons=seasons,
        )


def parse_series_id(url_or_id: str) -> str:
    """Extract series ID from a TVer URL, or return the raw ID if given directly."""
    s = url_or_id.strip()
    if s.startswith("http"):
        path = urllib.parse.urlparse(s).path
        s = path.rstrip("/").split("/")[-1]
    if not s.startswith("sr"):
        raise TVerAPIError(
            f"'{s}' doesn't look like a series ID (expected 'sr...'). "
            "Use a URL like https://tver.jp/series/sr... or just the series ID."
        )
    return s
