"""Opt-in integration: real MPD, disposable null output, local HTTP radio.

OPUS_TEST_MPD must name a throwaway MPD, never the household DAC. The first
connection stalls without closing; only reopening the stream restores audio.
"""
import asyncio
import os
import socket
import struct
from types import SimpleNamespace

import pytest

from conftest import run
from opus import dac, dac_watchdog as watchdog


@pytest.mark.skipif(not os.environ.get("OPUS_TEST_MPD"), reason="requires disposable MPD")
@pytest.mark.parametrize("failure", ["stall", "eof", "reset"])
def test_real_mpd_recovers_a_stalled_http_stream(monkeypatch, failure):
    async def scenario():
        connections = []
        handlers = set()
        stall = asyncio.Event()
        failures = 1 if failure == "stall" else 2
        # Streaming WAV: synthetic quiet PCM, no microphones or household audio.
        header = struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 0x7fffffff, b"WAVE", b"fmt ",
                             16, 1, 2, 44100, 176400, 4, 16, b"data", 0x7fffffff - 36)

        async def serve(reader, writer):
            handlers.add(asyncio.current_task())
            try:
                await reader.readuntil(b"\r\n\r\n")
                connections.append(1)
                first = len(connections) <= failures
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: audio/wav\r\nConnection: close\r\n\r\n" + header)
                for _ in range(2000):
                    if first and stall.is_set():
                        if failure == "stall":
                            await reader.read()  # connected, but no new audio bytes
                        elif failure == "reset":
                            writer.transport.abort()
                        break
                    writer.write(b"\x01\x00\x01\x00" * 4410)
                    await writer.drain()
                    await asyncio.sleep(.1)
            except (ConnectionError, asyncio.IncompleteReadError):
                pass
            finally:
                writer.close()
                handlers.discard(asyncio.current_task())

        server = await asyncio.start_server(serve, "0.0.0.0", 0)
        host = socket.gethostbyname(socket.gethostname())
        url = f"http://{host}:{server.sockets[0].getsockname()[1]}/test.wav"
        m = watchdog.RadioMonitor()
        m.probed[url] = {"codec": "pcm_s16le", "sample_rate_hz": 44100}

        async def station(address):
            return SimpleNamespace(id=1) if address == url else None

        monkeypatch.setattr(dac, "ADDRESS", (os.environ["OPUS_TEST_MPD"], 6600))
        monkeypatch.setattr(dac, "_station", station)
        monkeypatch.setattr(watchdog, "monitor", m)
        # WAV probing buffers longer than AAC; arm the injected failure only
        # after MPD has really started advancing, using the production timeout.
        monkeypatch.setattr(watchdog, "output_status", lambda: None)
        seen = []
        empty_stopped = False
        try:
            await dac.play([url], 0)
            for step in range(360):
                status, current = await dac._talk(["status"], ["currentsong"])
                empty_stopped |= status.get("state") == "stop" and not current
                await m.tick()
                seen.append(m.state)
                if m.state == "healthy" and len(connections) == 1:
                    stall.set()
                if step % 20 == 0:
                    print(f"step={step} health={m.state} connections={len(connections)} injected={stall.is_set()}", flush=True)
                if len(connections) > failures and m.state == "healthy":
                    break
                await asyncio.sleep(.5)
            assert "recovering" in seen, seen
            assert stall.is_set(), "must be playing before injecting the outage"
            assert len(connections) > failures
            if failure != "stall":
                assert empty_stopped, "must reproduce MPD losing currentsong at EOF"
            assert m.state == "healthy"
            print(f"real MPD recovered: failure={failure} connections={len(connections)} attempts={m.attempts} empty_stopped={empty_stopped}")
            await dac.control("pause")
            count = len(connections)
            await asyncio.sleep(2.5)
            await m.tick()
            assert len(connections) == count and m.state == "idle"
            await dac.control("stop")
            await m.tick()
            assert len(connections) == count and not m.address
        finally:
            await dac.control("stop")
            server.close()
            server.close_clients()
            for task in list(handlers):
                task.cancel()
            await asyncio.gather(*handlers, return_exceptions=True)
    run(scenario())
