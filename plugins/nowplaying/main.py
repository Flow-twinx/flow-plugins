"""nowplaying — minimal flow plugin example.

Polls the current track every 2 s and prints it. Demonstrates flow_api usage.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import flow_api  # noqa: E402  — bundled by `flow install`


def main():
    last = ""
    try:
        while True:
            track = flow_api.current_track()
            title = track.get("title", "")
            playing = track.get("playing", False)
            line = f"♫ Now playing: {title}" if playing else "  Not playing"
            if line != last:
                print(line, flush=True)
                last = line
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
