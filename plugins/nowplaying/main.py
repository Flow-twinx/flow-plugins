#!/usr/bin/env python3
"""nowplaying — prints the current track and live players from the flow daemon.

API v3 sample plugin. It uses only the typed surface of the injected
flow_api.py (copied from backend/plugin_api/flow_api.py at install time):

  current_track / is_playing / players / get_config / library_stats

Run it with:  flow run nowplaying      (Ctrl-C to quit)
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import flow_api


def _say(text: str):
    print(text, flush=True)


def main() -> int:
    _say(f"nowplaying — flow plugin API v{flow_api.API_VERSION}")

    # --- file-based state read (no daemon required) ---
    track = flow_api.current_track()
    title = track.get("title") or "(no track recorded)"
    dur = track.get("duration") or 0
    _say(f"current track : {title}  ({dur // 60}:{dur % 60:02d})")
    _say(f"is playing    : {flow_api.is_playing()}")

    # --- typed config through the daemon (host-validated safe keys) ---
    _say(f"theme config  : {flow_api.get_config('theme')}")

    # --- live player registry over the socket (needs the daemon) ---
    players = flow_api.players()
    if isinstance(players, list):
        for p in players:
            _say(
                f"player        : kind={p.get('kind')} pid={p.get('pid')}"
                + (f" port={p.get('port')}" if p.get("port") else "")
            )
        if not players:
            _say("player        : none registered (nothing is running)")
    else:
        _say(f"player        : {players.get('error', players)}")

    # --- library stats (file-based) ---
    stats = flow_api.library_stats()
    _say(
        f"library       : {stats.get('songs', 0)} songs, "
        f"{stats.get('liked', 0)} liked, {stats.get('duration', 0)}s total"
    )

    _say("\npolling every 2s — Ctrl-C to quit")
    try:
        while True:
            t = flow_api.current_track()
            state = "PLAYING" if t.get("playing", False) else "STOPPED/PAUSED"
            _say(f"[{state}] {t.get('title') or '(nothing playing)'}")
            time.sleep(2.0)
    except KeyboardInterrupt:
        _say("bye")
    return 0


if __name__ == "__main__":
    sys.exit(main())