"""Radio recovery and evidence, independent of whether a screen is open.

Elapsed audio and ALSA hardware pointers are liveness evidence, not proof of
audible sound. No microphone is opened. Silence in a programme is never a fault.
"""
import asyncio
import json
import logging
import os
import time
from pathlib import Path

from opus import dac

log = logging.getLogger(__name__)
POLL = 3
STALL = 20
MAX_BACKOFF = 60
STABLE = 120


def output_status() -> dict | None:
    """Read only the configured card, never another active sound device."""
    card_id = os.environ.get("OPUS_DAC_CARD", "none")
    if card_id in ("none", "proof"):
        return None
    root = Path("/run/opus-asound")
    try:
        for card in root.glob("card[0-9]*"):
            if (card / "id").read_text().strip() != card_id:
                continue
            sub = card / "pcm0p/sub0"
            text = (sub / "status").read_text()
            fields = {key.strip(): value.strip() for line in text.splitlines() if ":" in line
                      for key, value in [line.split(":", 1)]}
            if fields.get("state") == "RUNNING" and "hw_ptr" not in fields:
                return None
            return {"state": fields.get("state", "closed").strip(),
                    "hw_ptr": int(fields["hw_ptr"]) if "hw_ptr" in fields else None,
                    "card": card_id}
        return {"state": "missing", "hw_ptr": None, "card": card_id}
    except (OSError, ValueError):
        return None  # not measurable is different from a measured stopped output


async def probe_stream(address: str) -> dict:
    """Probe compressed headers, no playback or PCM conversion; bounded I/O."""
    proc = await asyncio.create_subprocess_exec(
        "/usr/lib/jellyfin-ffmpeg/ffprobe", "-v", "quiet", "-rw_timeout", "4000000",
        "-analyzeduration", "500000", "-probesize", "32768",
        "-select_streams", "a:0", "-show_entries",
        "stream=codec_name,sample_rate,channels,bit_rate", "-of", "json", address,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), 8)
        rows = json.loads(out).get("streams", [])
        if proc.returncode or not rows:
            return {}
        row = rows[0]
        return {"codec": row.get("codec_name"),
                "sample_rate_hz": int(row["sample_rate"]) if row.get("sample_rate") else None,
                "channels": row.get("channels")}
    except (TimeoutError, ValueError):
        return {}
    finally:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()


class RadioMonitor:
    def __init__(self):
        self.probed: dict[str, dict] = {}
        self.probe_at: dict[str, float] = {}
        self.probe_task: asyncio.Task | None = None
        self.reset()

    def reset(self, blocked=False):
        self.address = ""
        self.current = {}
        self.playlist = None
        self.blocked = blocked
        self.last_elapsed = None
        self.last_pointer = None
        self.progress_at = time.monotonic()
        self.output_at = self.progress_at
        self.stable_at = self.progress_at
        self.next_retry = 0.0
        self.attempts = 0
        self.reason = None
        self.state = "idle"
        self.output = None
        self.checked_at = None

    def stream_info(self, address):
        return self.probed.get(address, {})

    def current_for(self, status, current):
        """MPD drops currentsong on EOF, but leaves the same queue item in place.

        Retain only an already-armed station in the unchanged queue. Explicit
        stop/pause resets this intent; a cold start never has retained state.
        """
        if (not current.get("file") and status.get("state") == "stop"
                and not self.blocked and self.address and self.current.get("Id")
                and self.playlist is not None and status.get("playlist") == self.playlist):
            return self.current
        return current

    def snapshot(self, address):
        if address != self.address:
            return {"state": "unknown", "speaker_verified": False}
        return {"state": self.state, "reason": self.reason, "attempts": self.attempts,
                "checked_at": self.checked_at, "output": self.output,
                "speaker_verified": False}

    async def _probe(self, address):
        try:
            self.probe_at[address] = time.monotonic()
            result = await probe_stream(address)
            if result:
                # Only the last station is needed; don't grow with listening history.
                self.probed = {address: result}
        except (OSError, ValueError):
            log.warning("radio format probe unavailable")

    async def tick(self):
        # Manual stop/source changes cannot slip between the check and recovery.
        async with dac._turn:
            status, current = await dac._exchange(["status"], ["currentsong"])
            await self.observe(status, current, output_status(), time.monotonic())

    async def observe(self, status, current, output, at):
        current = self.current_for(status, current)
        if status.get("state") == "pause":
            self.reset(blocked=True)
            return
        if self.blocked:
            self.state = "idle"
            return
        if not await self._armed(status, current, at):
            return
        self._record(status, current, output, at)
        progressed, output_progress = self._progress(status, output, at)
        reason = self._fault(status, output, at)
        if reason:
            await self._recover(reason, status, current, output, at)
        elif progressed and (output is None or output_progress):
            self._healthy(at)
        else:
            self.stable_at = at

    async def _armed(self, status, current, at) -> bool:
        address = current.get("file", "")
        # ICY title updates can increment MPD's playlist version. They must not
        # reset the retry budget while the same item is still selected.
        if self.address and current.get("Id") != self.current.get("Id"):
            self.reset()
        if address != self.address:
            self.reset()
            # Only a known station already playing can arm recovery. Never start
            # a stopped queue after boot or restart library/video playback.
            if status.get("state") != "play" or not address.startswith(("http://", "https://")) \
                    or dac._TRACK.search(address) or await dac._station(address) is None:
                return False
            self.address = address
            self.progress_at = self.output_at = self.stable_at = at
            self.state = "checking"
        return bool(self.address)

    def _record(self, status, current, output, at):
        self.current = dict(current)
        self.playlist = status.get("playlist")
        self.checked_at = time.time()
        self.output = output
        if self.address not in self.probed and at - self.probe_at.get(self.address, -60) >= 60:
            if self.probe_task is None or self.probe_task.done():
                self.probe_task = asyncio.create_task(self._probe(self.address))

    def _progress(self, status, output, at) -> tuple[bool, bool]:
        elapsed = dac._number(status.get("elapsed"))
        progressed = elapsed is not None and self.last_elapsed is not None and elapsed > self.last_elapsed
        if progressed:
            self.progress_at = at
        self.last_elapsed = elapsed
        pointer = (output or {}).get("hw_ptr")
        output_progress = bool(output) and output.get("state") == "RUNNING" \
            and pointer is not None and self.last_pointer is not None and pointer != self.last_pointer
        if output_progress:
            self.output_at = at
        self.last_pointer = pointer
        return progressed, output_progress

    def _fault(self, status, output, at) -> str | None:
        if status.get("error"):
            return "mpd_error"
        if status.get("state") == "stop":
            return "stream_ended"
        if at - self.progress_at >= STALL:
            return "playback_stalled"
        if output is not None and at - self.output_at >= STALL:
            return "output_stalled"
        return None

    async def _recover(self, reason, status, current, output, at):
        self.reason = reason
        self.state = "failed" if self.attempts >= 3 else "recovering"
        self.stable_at = at
        if at < self.next_retry:
            return
        # Do not clear/rebuild the queue: reopen exactly the current song id.
        songid = status.get("songid") or current.get("Id")
        if songid is None:
            self.state = "failed"
            return
        queued, = await dac._exchange(["playlistid", songid])
        if queued.get("file") != self.address or queued.get("Id") != songid:
            self.reset(blocked=True)
            return
        self.attempts += 1
        self.next_retry = at + min(MAX_BACKOFF, STALL * (2 ** min(self.attempts - 1, 2)))
        log.warning("radio recovery attempt=%s reason=%s elapsed=%s output=%s",
                    self.attempts, reason, self.last_elapsed, (output or {}).get("state"))
        await dac._exchange(["stop"], ["clearerror"], ["playid", songid])
        self.progress_at = self.output_at = at
        self.last_elapsed = self.last_pointer = None

    def _healthy(self, at):
        if self.state in ("recovering", "failed"):
            log.info("radio recovered attempt=%s; playback advancing; output=%s",
                     self.attempts, (self.output or {}).get("state", "unmeasured"))
        self.state = "healthy"
        self.reason = None
        if at - self.stable_at >= STABLE:
            self.attempts = 0

    async def run(self):
        log.info("radio watchdog started: stall=%ss max_backoff=%ss; speaker audio unmeasured", STALL, MAX_BACKOFF)
        try:
            while True:
                try:
                    await self.tick()
                except Exception as exc:
                    self.state = "unavailable"
                    # Exception class, never an address that might hold a ticket.
                    log.warning("radio watchdog check failed: %s", type(exc).__name__)
                await asyncio.sleep(POLL)
        finally:
            if self.probe_task and not self.probe_task.done():
                self.probe_task.cancel()
                await asyncio.gather(self.probe_task, return_exceptions=True)


monitor = RadioMonitor()
