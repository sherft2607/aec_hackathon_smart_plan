"""Render the pitch in chunks and join them, retrying any chunk whose render stops making progress.

Remotion's video frame extraction can stall now and then on a long render; a stalled chunk is killed and
rendered again. Usage: python3 record/render_chunks.py [output.mp4]
"""
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHUNKS = ROOT / "out" / "chunks"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "4site_pitch.mp4"
SIZE = 600
STALL = 90


def total_frames() -> int:
    listing = subprocess.run(["npx", "remotion", "compositions", "src/index.ts"], cwd=ROOT, capture_output=True, text=True).stdout
    return int(re.search(r"^Pitch\s+\d+\s+\S+\s+(\d+)", listing, re.M).group(1))


def render(index: int, start: int, end: int) -> Path:
    out = CHUNKS / f"c{index:03d}.mp4"
    if out.exists():
        return out
    for attempt in range(4):
        log = CHUNKS / f"c{index:03d}.log"
        tmp = CHUNKS / f"c{index:03d}.part.mp4"
        with open(log, "w") as fh:
            proc = subprocess.Popen(["npx", "remotion", "render", "src/index.ts", "Pitch", str(tmp), f"--frames={start}-{end}",
                                     "--codec=h264", "--crf=20", "--gl=angle", "--concurrency=4"], cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        size, last = -1, time.time()
        while proc.poll() is None:
            time.sleep(5)
            now = log.stat().st_size
            if now != size:
                size, last = now, time.time()
            elif time.time() - last > STALL:
                proc.kill()
                subprocess.run(["pkill", "-f", "chrome-headless-shell"])
                print(f"  chunk {index} stalled, retry {attempt + 1}", flush=True)
                break
        if proc.wait() == 0 and tmp.exists():
            tmp.rename(out)
            return out
    raise SystemExit(f"chunk {index} failed")


def main() -> None:
    CHUNKS.mkdir(parents=True, exist_ok=True)
    total = total_frames()
    parts = []
    for i, start in enumerate(range(0, total, SIZE)):
        end = min(start + SIZE, total) - 1
        print(f"chunk {i}: frames {start}-{end}", flush=True)
        parts.append(render(i, start, end))
    listing = CHUNKS / "list.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(OUT)], check=True)
    print("wrote", OUT, flush=True)


main()
