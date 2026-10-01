#!/usr/bin/env python3

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import flow_api

PLAYERCTL = os.environ.get("PLAYERCTL_BIN") or "playerctl"
FLOW_MPRIS_NAME = os.environ.get("FLOW_MPRIS_NAME") or "flow"
CALL_TIMEOUT = 5.0
MAX_ATTEMPTS = 3  # toggle-safety cap per takeover
RUNNING = True


class PlayerctlMissing(RuntimeError):
    """`playerctl` is not installed / not on PATH."""


def _playerctl(*args: str) -> str | None:
    """Run playerctl; return stdout, or None when it failed or timed out."""
    try:
        proc = subprocess.run(
            [PLAYERCTL, *args],
            capture_output=True,
            text=True,
            timeout=CALL_TIMEOUT,
        )
    except FileNotFoundError:
        raise PlayerctlMissing(f"{PLAYERCTL} not found on PATH") from None
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout or ""


def list_players() -> list[str]:
    """MPRIS player names currently on the bus (`playerctl -l`)."""
    out = _playerctl("-l")
    if not out:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def player_status(name: str) -> str:
    """Status of one player: 'Playing' / 'Paused' / 'Stopped' (or '')."""
    out = _playerctl("-p", name, "status")
    return out.strip().lower() if out else ""


def _matches(name: str, patterns: set[str]) -> bool:
    """True when a player name equals or starts with any pattern."""
    return any(name == p or name.startswith(p) for p in patterns if p)


def _split_list(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}



class YieldToOthers:
    """Polls the MPRIS bus and pauses Flow when someone else takes over."""

    def __init__(
        self,
        interval: float,
        self_names: set[str],
        ignore: set[str],
        grace: float,
        dry_run: bool = False,
        verbose: bool = False,
    ):
        self.interval = max(0.1, interval)
        self.self_names = self_names
        self.ignore = ignore
        self.grace = max(self.interval, grace)
        self.dry_run = dry_run
        self.verbose = verbose
        self._active: str | None = None      # player that took over
        self._attempts = 0                  # toggles sent for this takeover
        self._gave_up = False               # stop toggling this takeover
        self._last_pause = 0.0              # monotonic clock of last toggle

    # -- logging ----------------------------------------------------------
    def _say(self, text: str) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {text}", flush=True)

    def _debug(self, text: str) -> None:
        if self.verbose:
            self._say(text)

    # -- flow's own state -------------------------------------------------
    def _flow_player(self, players: list[str]) -> str | None:
        """Flow's MPRIS entry, if it is on the bus."""
        for name in players:
            if _matches(name, self.self_names):
                return name
        return None

    def flow_is_playing(self, players: list[str]) -> bool:
        flow_player = self._flow_player(players)
        if flow_player:
            return player_status(flow_player) == "playing"
        return bool(flow_api.is_playing())

    # -- main loop --------------------------------------------------------
    def poll(self) -> None:
        """One poll cycle: pause Flow if another player is playing."""
        players = list_players()
        if not players:
            self._debug("no mpris players on the bus")
            self._clear_active()
            return

        active = [
            name
            for name in players
            if not _matches(name, self.self_names)
            and not _matches(name, self.ignore)
            and player_status(name) == "playing"
        ]

        if not active:
            if self._active is not None:
                self._debug(f"{self._active} stopped")
            self._clear_active()
            return

        winner = active[0]
        flow_playing = self.flow_is_playing(players)

        if winner != self._active:
            self._active = winner
            self._attempts = 0
            self._gave_up = False
            others = ", ".join(active)
            if self.dry_run:
                self._say(f"[dry-run] {others} started playing -> would pause flow")
                return
            if not flow_playing:
                self._say(f"{others} started playing (flow isn't playing)")
                return
            self._say(f"{others} started playing -> pausing flow")
        elif not flow_playing:
            return

        self._send_pause(winner)

    def _clear_active(self) -> None:
        self._active = None
        self._attempts = 0
        self._gave_up = False

    def _blocked(self) -> bool:
        """True while a recent toggle still needs time to take effect."""
        return (time.monotonic() - self._last_pause) < self.grace

    def _send_pause(self, player: str) -> None:
        """Toggle Flow's play/pause — once, then wait for it to land."""
        if self.dry_run:
            return
        if self._blocked():
            self._debug("grace window: not toggling again yet")
            return
        if self._gave_up:
            return
        if self._attempts >= MAX_ATTEMPTS:
            self._gave_up = True
            self._say(
                f"flow still reports playing after {self._attempts} pauses "
                f"for {player}; giving up until the takeover ends"
            )
            return

        self._attempts += 1
        self._last_pause = time.monotonic()
        result = flow_api.pause()
        if isinstance(result, dict) and result.get("error"):
            self._say(f"pause failed: {result['error']}")
        else:
            self._say(f"paused flow for {player} (toggle #{self._attempts})")

    def run(self) -> int:
        # Fail fast (and loudly) if playerctl is not usable at all, so a
        # background run doesn't sit there silently doing nothing.
        seen = list_players()
        self._say(
            f"watching {len(seen)} mpris player(s)"
            f" (poll {self.interval:g}s, flow = {', '.join(sorted(self.self_names))}"
            + (f", ignoring {', '.join(sorted(self.ignore))}" if self.ignore else "")
            + (", dry-run" if self.dry_run else "")
            + ")"
        )
        while RUNNING:
            try:
                self.poll()
            except PlayerctlMissing:
                raise
            except Exception as exc:  # one bad poll must not kill the plugin
                self._debug(f"poll error: {exc}")
            # sleep in slices so a signal stops us promptly
            deadline = time.monotonic() + self.interval
            while RUNNING and time.monotonic() < deadline:
                time.sleep(min(0.25, self.interval))
        self._say("bye")
        return 0


def _handle_signal(_signum, _frame):
    global RUNNING
    RUNNING = False


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="yield-to-others",
        description="Pause Flow when another MPRIS player starts playing.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="poll period in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--grace",
        type=float,
        default=3.0,
        help="minimum seconds between play/pause toggles (default: 3.0)",
    )
    parser.add_argument(
        "--self",
        dest="self_names",
        default="",
        help="comma-separated extra MPRIS names for Flow itself "
        f"(default: {FLOW_MPRIS_NAME})",
    )
    parser.add_argument(
        "--ignore",
        default="",
        help="comma-separated extra player names/prefixes that must never "
        "trigger a pause",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="log what would happen without pausing anything",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="log every poll, not just takeovers"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    self_names = _split_list(args.self_names)
    self_names.add(FLOW_MPRIS_NAME)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    watcher = YieldToOthers(
        interval=args.interval,
        self_names=self_names,
        ignore=_split_list(args.ignore),
        grace=args.grace,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
    try:
        return watcher.run()
    except PlayerctlMissing as exc:
        print(f"auto-stop: {exc}", file=sys.stderr, flush=True)
        print(
            "install playerctl with your package manager "
            "(e.g. `sudo apt install playerctl`)",
            file=sys.stderr,
            flush=True,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
