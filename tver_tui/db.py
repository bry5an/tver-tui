from __future__ import annotations

import os
from dataclasses import dataclass

try:
    import psycopg2
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


@dataclass
class SubtitleCounts:
    available: int = 0      # published but not yet downloaded
    not_available: int = 0  # not yet published
    missing: int = 0        # expected but not found / download failed
    untracked: int = 0      # downloaded episode with no subtitle row at all


def get_subtitle_counts(series_ids: list[str]) -> dict[str, SubtitleCounts]:
    """Return subtitle status counts keyed by tver_series_id.

    Counts episodes that were downloaded (downloads.status = 'downloaded') but
    whose subtitle file is absent or untracked. Uses LEFT JOIN so episodes with
    no subtitles row are also surfaced.

    Returns an empty dict if psycopg2 is missing, POSTGRESQL_CONNECTION is unset,
    or the DB is unreachable.
    """
    if not _AVAILABLE or not series_ids:
        return {}
    conn_str = os.environ.get("POSTGRESQL_CONNECTION")
    if not conn_str:
        return {}

    result: dict[str, SubtitleCounts] = {}
    try:
        with psycopg2.connect(conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT s.tver_series_id, sub.status, COUNT(*)
                    FROM series s
                    JOIN episodes e ON e.series_id = s.id
                    JOIN downloads d ON d.episode_id = e.id
                      AND d.status = 'downloaded'
                    LEFT JOIN subtitles sub ON sub.episode_id = e.id
                    WHERE s.tver_series_id = ANY(%s)
                      AND (sub.status IS NULL OR sub.status != 'downloaded')
                    GROUP BY s.tver_series_id, sub.status
                    """,
                    (series_ids,),
                )
                for tver_id, status, count in cur.fetchall():
                    if tver_id not in result:
                        result[tver_id] = SubtitleCounts()
                    if status is None:
                        result[tver_id].untracked += count
                    elif status in ("missing", "failed"):
                        result[tver_id].missing += count
                    elif status == "available":
                        result[tver_id].available += count
                    elif status == "not_available":
                        result[tver_id].not_available += count
    except Exception:
        pass  # DB unavailable — degrade gracefully

    return result
