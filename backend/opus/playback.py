"""How a thing is played, decided per device and per file.

Three ways, in order of how little work they cost. **Direct** hands the file over
untouched and the browser does everything — no server work at all. **Remux**
repackages the compressed streams into a container the browser will open, which
touches the audio but never the picture, so the client keeps hardware-decoding
exactly as it would a local file. **Transcode** is the only path that decodes and
re-encodes, and it happens on the GPU or it does not happen: a software fallback
would quietly cook the host that also runs the photo library's machine learning,
and hide that the fast path is broken.

What decides is the device, asked rather than guessed. The browser knows whether
it can decode a codec *efficiently* — `mediaCapabilities.decodingInfo()` reports
`powerEfficient` — and that answer is worth more than any table of user agents."""

import asyncio
import logging
import os
import re
import shutil
from dataclasses import dataclass

log = logging.getLogger(__name__)

def render_node() -> str | None:
    """The GPU as this container sees it. Discovered rather than named, because
    the node's number differs per host and it is the same number libva uses to
    find the card behind it."""
    import glob

    nodes = sorted(glob.glob("/dev/dri/renderD*"))
    return nodes[0] if nodes else None

# what every browser opens without help
UNIVERSAL = {"h264"}
# containers a browser will play progressively
PLAYABLE_CONTAINERS = {"mp4", "m4v", "webm"}
# The two pictures this card has no decoder for, found on the photo shelf: a
# DivX from 2005 and a phone's H.263. They are decoded on the processor, where a
# standard-definition frame costs a twentieth of real time, and encoded on the
# card like everything else. Any other codec the card cannot open fails loudly.
DECODED_ON_THE_PROCESSOR = {"mpeg4", "h263"}


# what an mp4 will carry, so what a rebuild can hand over without touching
MP4_AUDIO = {"aac", "ac3", "eac3", "mp3"}
# encoders that keep a film's channels, best first. Both stop at 5.1 — there is
# no encoder here that writes 7.1, so an eight-channel source loses its two back
# channels and keeps the other six, which is the whole difference between a room
# and a pair of speakers
SURROUND_ENCODERS = ("eac3", "ac3")
SURROUND_MAX = 6


class PlaybackError(Exception):
    """Playback could not be arranged. Never swallowed — a silent fallback to a
    worse path is the thing this module exists to prevent."""


@dataclass(frozen=True)
class Sound:
    """What a rebuild does with the film's sound."""
    codec: str  # copy | aac | ac3 | eac3
    channels: int  # 0 when copying
    bitrate: str


def sound_for(codec: str, channels: int, accepts: list[str], takes: int = 0) -> Sound:
    """The sound a rebuild should carry, given what the renderer can render.

    A film's sound was folded to two channels every time the file had to be
    repackaged — which is every 4K remux, because mp4 cannot carry TrueHD and
    the box cannot pass it through. The picture survived untouched and the room
    lost its rear speakers to a line of ffmpeg arguments. What the renderer can
    take is asked of the renderer, and the best of it is used: the track whole
    where the container allows, otherwise the widest encoder the box owns.

    An empty `accepts` is a browser, which folds anything down to two channels
    at the speaker anyway — no reason to send it more."""
    src = (codec or "").lower()
    take = {a.strip().lower() for a in accepts if a.strip()}
    if not take:
        return Sound("aac", 2, "192k")
    # A renderer that says how many channels can leave it is believed: sending a
    # box six of them when two is all its output carries is how a centre channel
    # goes missing rather than being folded into the pair that is heard. The
    # track can only be handed over WHOLE if the box can carry all of it — the
    # cap is what the box takes, compared against what the file actually holds.
    if src in MP4_AUDIO and src in take and (not takes or takes >= channels):
        return Sound("copy", 0, "")
    if takes:
        channels = min(channels, takes)
    if channels > 2:
        for encoder in SURROUND_ENCODERS:
            if encoder in take:
                return Sound(encoder, min(channels, SURROUND_MAX), "640k")
        if "aac" in take:
            return Sound("aac", min(channels, SURROUND_MAX), "384k")
    return Sound("aac", 2, "192k")


STEREO = Sound("aac", 2, "192k")


def _audio_args(sound: Sound, trim: bool) -> list[str]:
    if sound.codec == "copy":
        # nothing to trim in a stream that is not decoded
        return ["-c:a", "copy"]
    return [
        # sound decoded from before the landing keyframe is cut here, not
        # trusted to the seek: with the picture stream-copied, the seek does
        # not trim the decoded sound at all
        *(["-af", "atrim=start=0"] if trim else []),
        "-c:a", sound.codec, "-ac", str(sound.channels), "-b:a", sound.bitrate,
    ]


@dataclass(frozen=True)
class Plan:
    mode: str  # direct | remux | transcode
    reason: str
    width: int | None = None
    height: int | None = None
    codec: str = ""


def fit(src_w: int, src_h: int, box_w: int, box_h: int) -> tuple[int, int]:
    """The largest picture of the source's shape that fits inside the screen.

    Capping the height alone is wrong the moment the two shapes differ: a 16:9
    film held to 1200 tall comes out 2133 wide, which is wider than the 1920 the
    panel actually has — more pixels than the screen can show, encoded and sent
    for nothing. Both edges are honoured, and both come out even because an
    encoder will not take an odd one."""
    if not src_w or not src_h:
        return box_w - box_w % 2, box_h - box_h % 2
    scale = min(box_w / src_w, box_h / src_h, 1.0)
    w = int(src_w * scale) // 2 * 2
    h = int(src_h * scale) // 2 * 2
    return max(w, 2), max(h, 2)


def render_node_openable(node: str) -> bool:
    return os.access(node, os.R_OK | os.W_OK)


def gpu_available() -> bool:
    node = render_node()
    return node is not None and render_node_openable(node)


def decide(media: dict, *, can_decode: bool, max_height: int | None,
           max_width: int | None = None, audio: int = 0,
           native: bool = False, rebuild_audio: bool = False) -> Plan:
    """`can_decode` is the client's own answer about this file's video codec:
    can it, and would it be power-efficient. `max_height` is the screen it will
    be shown on — sending 4K to a 1080p panel costs bandwidth and battery for a
    detail nobody can see. `native` is a client that is not a browser at all."""
    codec, width, height, container = _source(media)

    # An engine running on the television opens the containers this library is
    # actually in, and decodes them on hardware that was built for it. Every
    # question below is a browser's question; asking them of a native TV engine
    # would have the server rebuild a file the box in front of it opens for
    # nothing.
    if native and can_decode and not rebuild_audio:
        return Plan("direct", "the engine on this box opens the file as it is",
                    width, height, codec)

    shrunk = _shrunk(width, height, max_width, max_height)
    if shrunk is not None:
        return Plan("transcode", "the source is larger than the screen it is going to",
                    shrunk[0], shrunk[1], "h264")
    # `UNIVERSAL` is the browser baseline. A native client explicitly saying
    # no is stronger evidence and must reach the hardware transcode path.
    if not (can_decode or (not native and codec in UNIVERSAL)):
        return Plan("transcode", f"the device cannot decode {codec or 'this'} efficiently",
                    width, height, "h264")
    # A selected sound track needs a rebuilt container, but that cannot make an
    # unsupported picture codec decodable. Check the picture first.
    if (audio or rebuild_audio) and container in PLAYABLE_CONTAINERS:
        return Plan("remux", "another sound track was asked for", width, height, codec)
    if container in PLAYABLE_CONTAINERS:
        return Plan("direct", "the browser can open this file as it is", width, height, codec)
    return Plan("remux", f"{container or 'this container'} is not one a browser opens; "
                "the picture is copied untouched", width, height, codec)


def _source(media: dict) -> tuple[str, int, int, str]:
    return ((media.get("video_codec") or "").lower(),
            media.get("width") or 0,
            media.get("height") or 0,
            (media.get("container") or "").lower())


def _shrunk(width: int, height: int, max_width: int | None,
            max_height: int | None) -> tuple[int, int] | None:
    """The size the picture comes down to when it is larger than the screen
    it is going to; None when it is not."""
    box_w = max_width or (max_height * 2 if max_height else 0)
    box_h = max_height or 0
    if box_h and (height > box_h or (box_w and width > box_w)):
        return fit(width, height, box_w, box_h)
    return None


JELLYFIN_FFMPEG = "/usr/lib/jellyfin-ffmpeg/ffmpeg"


def _ffmpeg() -> str:
    """Jellyfin's build where it is present, because its tone mapping works and
    Debian's does not — the engine, not the product."""
    if os.path.exists(JELLYFIN_FFMPEG):
        return JELLYFIN_FFMPEG
    found = shutil.which("ffmpeg")
    if not found:
        raise PlaybackError("no ffmpeg in this image")
    return found


# A seek in a stream whose picture is copied can only truly begin on a
# keyframe: ffmpeg starts the copied video at the keyframe before the point
# while trimming the re-encoded sound to the exact second asked for, and the
# two arrive out of step by the difference — sound and subtitles agreeing with
# each other and both ahead of the picture. Stream and subtitles are therefore
# aligned to the keyframe itself, found once per (file, second) and remembered.
_KEYFRAMES: dict[tuple[str, int], float] = {}


def _ffprobe() -> str:
    beside = os.path.join(os.path.dirname(JELLYFIN_FFMPEG), "ffprobe")
    if os.path.exists(beside):
        return beside
    found = shutil.which("ffprobe")
    if not found:
        raise PlaybackError("no ffprobe in this image")
    return found


async def snap_start(path: str, t: float) -> float:
    """The last video keyframe at or before `t`, which is where a copied-video
    stream asked to start at `t` actually begins."""
    key = (path, int(t))
    if key in _KEYFRAMES:
        return _KEYFRAMES[key]
    command = [
        _ffprobe(), "-v", "error", "-select_streams", "v:0", "-skip_frame", "nokey",
        "-show_entries", "frame=pts_time", "-read_intervals", f"{t}%+#1",
        "-of", "default=nw=1:nk=1", path,
    ]
    async with _admitting:
        _refuse_past_ceiling("probe")
        proc = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        _running[proc] = "probe"
    try:
        out, _ = await proc.communicate()
    finally:
        _running.pop(proc, None)
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
    try:
        found = float(out.split()[0])
    except (IndexError, ValueError):
        log.warning("no keyframe found near %ss in %s; seeking unaligned", t, path)
        return t
    if len(_KEYFRAMES) > 256:
        _KEYFRAMES.clear()
    _KEYFRAMES[key] = found
    return found


def subtitle_command(path: str, index: int | None) -> list[str]:
    """One subtitle track as WebVTT, which is the only thing a browser will take.

    `index` names an embedded stream; None means the path IS the subtitle — a
    sidecar the library fetched, which matters because the films with no
    embedded text tracks are exactly the ones whose subtitles were gone looking
    for. Bitmap tracks (PGS on a Blu-ray remux) cannot become text and are never
    offered."""
    return [
        _ffmpeg(), "-hide_banner", "-loglevel", "error",
        "-i", path,
        *(["-map", f"0:s:{index}"] if index is not None else []),
        "-f", "webvtt", "pipe:1",
    ]


_STAMP = re.compile(r"(\d+):(\d{2})(?::(\d{2}))?\.(\d{3})")


def _stamp_seconds(match: re.Match) -> float:
    a, b, c, ms = match.groups()
    hours, minutes, seconds = (0, int(a), int(b)) if c is None else (int(a), int(b), int(c))
    return hours * 3600 + minutes * 60 + seconds + int(ms) / 1000


def _stamp_text(seconds: float) -> str:
    ms = round(max(seconds, 0.0) * 1000)
    hours, rest = divmod(ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def shift_vtt(text: str, offset: float) -> str:
    """Cues rebased onto a stream that began at `offset` into the film.

    The cues carry the film's own time; a remux started at minute thirty has a
    clock that runs from zero, so served as they are they land half an hour
    from the words. ffmpeg cannot do this: its input seek rebases to the first
    cue it lands on rather than the requested point, and disabling that leaves
    malformed negative stamps in the output. Cues already over before the
    stream began are dropped; one straddling it keeps its tail."""
    blocks = []
    for block in text.split("\n\n"):
        lines = block.splitlines()
        timed = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timed is None:
            blocks.append(block)
            continue
        stamps = list(_STAMP.finditer(lines[timed]))
        if len(stamps) < 2:
            blocks.append(block)
            continue
        begin = _stamp_seconds(stamps[0]) - offset
        end = _stamp_seconds(stamps[1]) - offset
        if end <= 0:
            continue
        line = lines[timed]
        lines[timed] = (line[:stamps[0].start()] + _stamp_text(begin)
                        + line[stamps[0].end():stamps[1].start()]
                        + _stamp_text(end) + line[stamps[1].end():])
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def remux_command(path: str, start: float = 0, audio: int = 0,
                  sound: Sound = STEREO) -> list[str]:
    """Copy the picture, re-encode only the sound — MP4 cannot carry TrueHD or
    DTS-HD, so a 'pure' remux of a remux does not exist. Fragmented output so it
    can be served while it is still being made."""
    return [
        _ffmpeg(), "-hide_banner", "-loglevel", "error",
        # a minute arrives at once, the rest at eight times watching speed: a
        # remux nobody is draining must have a ceiling, or an abandoned one
        # races through the whole film at the speed of the disk
        "-readrate", "8", "-readrate_initial_burst", "60",
        # -ss quietly aims ~0.13 s short of the point it is given (a DTS-format
        # heuristic), and from a keyframe's own timestamp that lands a whole
        # cue earlier — the picture then starts a GOP before the sound and the
        # subtitles. Aiming past the point and offsetting back the same amount
        # makes the landing keyframe the timeline's zero again
        *(["-itsoffset", "0.2", "-ss", str(start + 0.2)] if start else []),
        "-i", path,
        "-map", "0:v:0", "-map", f"0:a:{audio}?",
        "-c:v", "copy",
        *_audio_args(sound, trim=True),
        # delay_moov holds the first fragment until every track has reached its
        # end. Without it, a file whose sound is stored after a whole GOP of
        # picture loses that first GOP of sound: the fragment is sealed before
        # the late audio arrives and the muxer drops it without a word — the
        # picture then runs ten seconds from the voice for the rest of the film
        "-movflags", "+frag_keyframe+empty_moov+default_base_moof+delay_moov",
        "-f", "mp4", "pipe:1",
    ]


def compact_audio_command(path: str) -> list[str]:
    """A modest mobile stream, deliberately separate from house playback.

    Audio transcoding is cheap enough for a small home server but is still a
    process with a bounded lifetime in ``stream``.  The fixed 96 kb/s Opus
    target is transparent enough for a car and turns a lossless album into a
    useful cellular/offline-cache size.  It is never selected implicitly.
    """
    return [
        _ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin",
        "-i", path, "-map", "0:a:0", "-vn",
        "-c:a", "libopus", "-b:a", "96k", "-vbr", "constrained",
        "-application", "audio", "-f", "ogg", "pipe:1",
    ]


# what a picture says about itself when it is HDR
HDR_TRANSFERS = {"smpte2084", "arib-std-b67"}


def transcode_command(path: str, width: int, height: int, start: float = 0,
                      audio: int = 0, hdr: bool = False,
                      sound: Sound = STEREO, codec: str = "") -> list[str]:
    """Decode and encode on the GPU, both. The 10-bit sources need saying out
    loud: H.264 is 8-bit, and without the format conversion the encoder reports
    'no usable encoding profile', which reads as if the card cannot do it."""
    node = render_node()
    if node is None:
        raise PlaybackError(
            "this file needs transcoding and there is no GPU here — refusing to "
            "do it in software"
        )
    if not render_node_openable(node):
        raise PlaybackError(
            f"{node} is here but uid {os.getuid()} cannot open it — the backend "
            "needs the node's group (OPUS_RENDER_GID)"
        )
    # An HDR picture re-encoded as if it were SDR comes out washed green and
    # magenta: the numbers are carried over unchanged into a colour space that
    # means something else by them. Tone mapping is done in OpenCL on the same
    # card — measured at 6.3x realtime — because the VAAPI filter crushes the
    # picture to near-black on this hardware, and doing it on the processor is
    # the one thing this module will not do.
    #
    # Scaling comes first either way: the filter is the expensive part, and a
    # 1080p frame is a quarter of the work of a 4K one.
    if hdr:
        devices = ["-init_hw_device", f"vaapi=va:{node}",
                   "-init_hw_device", "opencl=ocl@va", "-filter_hw_device", "ocl"]
        picture = (
            f"scale_vaapi=w={width}:h={height}:format=p010"
            ",hwmap=derive_device=opencl"
            ",tonemap_opencl=format=nv12:primaries=bt709:transfer=bt709"
            ":matrix=bt709:tonemap=bt2390:peak=100:desat=0"
            ",hwmap=derive_device=vaapi:reverse=1,format=vaapi"
        )
    else:
        devices = ["-init_hw_device", f"vaapi=va:{node}", "-filter_hw_device", "va"]
        picture = f"scale_vaapi=w={width}:h={height}:format=nv12"

    if codec in DECODED_ON_THE_PROCESSOR:
        decoding = []
        picture = f"format={'p010' if hdr else 'nv12'},hwupload," + picture
    else:
        decoding = ["-hwaccel", "vaapi", "-hwaccel_output_format", "vaapi"]

    return [
        _ffmpeg(), "-hide_banner", "-loglevel", "error",
        *devices,
        *decoding,
        *(["-ss", str(start)] if start else []),
        "-i", path,
        "-map", "0:v:0", "-map", f"0:a:{audio}?",
        "-vf", picture,
        "-c:v", "h264_vaapi", "-qp", "24",
        *_audio_args(sound, trim=False),
        # delay_moov holds the first fragment until every track has reached its
        # end. Without it, a file whose sound is stored after a whole GOP of
        # picture loses that first GOP of sound: the fragment is sealed before
        # the late audio arrives and the muxer drops it without a word — the
        # picture then runs ten seconds from the voice for the rest of the film
        "-movflags", "+frag_keyframe+empty_moov+default_base_moof+delay_moov",
        "-f", "mp4", "pipe:1",
    ]


# How many pictures this box will re-encode at once. Not a tuning knob: the
# media host also runs the photo library's machine learning on the same card,
# and an unbounded number of transcodes is how a household of one browser tab
# takes a server down.
MAX_CONCURRENT = 3
# And how many processes of any kind. A remux and a subtitle are cheap one at a
# time and not at all cheap when nothing stops a page from asking for fifty.
MAX_PROCESSES = 12
# what each live process is doing. Only re-encoding a picture is scarce; a remux
# copies the video untouched and a subtitle conversion reads one small track, and
# counting those against the same budget is how pressing the subtitle menu looked
# like a second film had started.
_running: dict[asyncio.subprocess.Process, str] = {}


def running() -> int:
    return sum(1 for kind in _running.values() if kind == "transcode")


def in_flight(kind: str | None = "transcode") -> list[dict]:
    """What this box is encoding right now, and what each one costs. Read from
    the kernel rather than remembered, so a process that died without telling us
    cannot show up here as work still being done."""
    out = []
    for proc, doing in list(_running.items()):
        if kind is not None and doing != kind:
            continue
        entry = {"pid": proc.pid, "doing": doing, "cpu_s": None, "rss_mb": None}
        try:
            with open(f"/proc/{proc.pid}/stat") as fh:
                fields = fh.read().rsplit(") ", 1)[1].split()
            ticks = os.sysconf("SC_CLK_TCK")
            entry["cpu_s"] = round((int(fields[11]) + int(fields[12])) / ticks, 1)
            with open(f"/proc/{proc.pid}/statm") as fh:
                entry["rss_mb"] = round(int(fh.read().split()[1]) * 4096 / 1e6)
        except (OSError, IndexError, ValueError):
            pass
        out.append(entry)
    return out


def host_load() -> dict:
    try:
        one, five, fifteen = os.getloadavg()
    except OSError:
        return {}
    return {"load": [round(one, 2), round(five, 2), round(fifteen, 2)],
            "cores": os.cpu_count()}


# who is watching what, so that a viewer's new stream can end their old one.
# A seek abandons the previous stream, and the abandonment is only visible
# here if every hop between the browser and this process passes it on — one
# proxy that keeps draining is enough to keep a dead encoder alive. The one
# thing this process knows for certain is that the SAME viewer asking for the
# SAME title again has left the stream they had.
_live: dict[str, asyncio.subprocess.Process] = {}
_admitting = asyncio.Lock()


def _refuse_past_ceiling(kind: str) -> None:
    if kind == "transcode" and running() >= MAX_CONCURRENT:
        raise PlaybackError(
            f"{running()} pictures are already being re-encoded here, which is "
            "as many as this box will do at once"
        )
    if len(_running) >= MAX_PROCESSES:
        raise PlaybackError(
            f"{len(_running)} streams are already being prepared here, which is "
            "as many as this box will run at once"
        )


async def stream(command: list[str], *, is_gone=None, kind: str = "transcode",
                 viewer: str | None = None):
    """Yield the output as it is produced, and make sure the process dies with
    the response — a browser that seeks away leaves an ffmpeg behind otherwise,
    and ten of those are a host on fire.

    ffmpeg's complaint is read and logged rather than left in a pipe nobody
    empties. An encoder that fails and is not read produces exactly zero bytes
    and a cheerful 200, which is the silent degradation this whole module is
    written to avoid — and it is also what a full stderr pipe would deadlock on.

    `is_gone` is asked between chunks. Relying on the generator being closed when
    the client leaves is not enough: a viewer who closes the tab mid-film left
    encoders running for minutes on a four-core box that also runs the photo
    library's ML. The process is watched, not trusted to be collected."""
    async with _admitting:
        # a seek is the same viewer asking again, so their abandoned encoder
        # must be gone before it is counted against the limit
        if viewer is not None:
            prev = _live.pop(viewer, None)
            if prev is not None and prev.returncode is None:
                log.info("the viewer asked for a new stream; stopping their old %s", kind)
                prev.kill()
                _running.pop(prev, None)
        _refuse_past_ceiling(kind)
        proc = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _running[proc] = kind
        if viewer is not None:
            _live[viewer] = proc
    complaint = asyncio.create_task(proc.stderr.read())

    async def watch_viewer():
        """Asked on its own clock rather than between chunks. ffmpeg races ahead
        and blocks on a full pipe, and a read that never returns is a check that
        never happens — which is how an encoder outlives the tab that wanted
        it."""
        while is_gone is not None:
            await asyncio.sleep(0.5)
            if await is_gone():
                log.info("viewer left; stopping the %s", kind)
                if proc.returncode is None:
                    proc.kill()
                return

    watcher = asyncio.create_task(watch_viewer()) if is_gone is not None else None
    produced = 0
    try:
        while True:
            chunk = await proc.stdout.read(64 * 1024)
            if not chunk:
                break
            produced += len(chunk)
            yield chunk
        if produced == 0:
            if viewer is not None and _live.get(viewer) is not proc:
                # a rapid double-seek: the next request ended this one before
                # its first byte — the viewer is already watching the newer
                # stream, so this is a handover, not a failure
                log.info("superseded before the first byte; nothing to report")
            else:
                said = (await complaint).decode(errors="replace").strip()
                log.error("playback produced nothing: %s | command: %s",
                          said or "ffmpeg said nothing", " ".join(command))
    finally:
        complaint.cancel()
        if watcher is not None:
            watcher.cancel()
        _running.pop(proc, None)
        if viewer is not None and _live.get(viewer) is proc:
            _live.pop(viewer, None)
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
