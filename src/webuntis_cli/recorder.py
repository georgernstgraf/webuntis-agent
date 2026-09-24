"""CDP-Recorder: attach to a running Brave browser via the Chrome DevTools
Protocol and capture Network + Runtime (console) events for the WebUntis
domain into structured JSONL files under recordings/.

Usage:
    python -m webuntis_cli.recorder [--host localhost] [--port 9222] \\
        [--domain spengergasse.webuntis.com]

Prerequisites:
    Brave must be running with --remote-debugging-port=9222 (see
    scripts/brave-debug.sh).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import websockets

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9222
DEFAULT_DOMAIN = "spengergasse.webuntis.com"
RECORDINGS_DIR = Path(__file__).resolve().parents[2] / "recordings"


async def list_targets(host: str, port: int) -> list[dict[str, Any]]:
    """List the open browser targets (tabs) from the CDP HTTP endpoint."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"http://{host}:{port}/json")
        r.raise_for_status()
        return r.json()


async def find_webuntis_target(
    targets: list[dict[str, Any]], domain: str
) -> dict[str, Any] | None:
    """Find a page target whose URL contains the WebUntis domain."""
    for t in targets:
        if t.get("type") == "page" and domain in t.get("url", ""):
            return t
    return None


async def pick_target(
    targets: list[dict[str, Any]], domain: str
) -> dict[str, Any]:
    """Pick the WebUntis target if present, otherwise the first page target."""
    wt = await find_webuntis_target(targets, domain)
    if wt is not None:
        print(f"[recorder] attached to WebUntis tab: {wt.get('url')}", file=sys.stderr)
        return wt
    pages = [t for t in targets if t.get("type") == "page"]
    if not pages:
        raise RuntimeError(
            "No browser page target found. Open a tab in Brave first."
        )
    print(
        f"[recorder] WARNING: no WebUntis tab for '{domain}', "
        f"attaching to first page: {pages[0].get('url')}",
        file=sys.stderr,
    )
    return pages[0]


def open_recordings(domain: str) -> tuple[Path, Path, Path]:
    """Create the recordings dir and return the three output paths."""
    RECORDINGS_DIR.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    stem = RECORDINGS_DIR / f"{ts}_{domain.replace('.', '_')}"
    net_path = stem.with_name(stem.name + "_network.jsonl")
    con_path = stem.with_name(stem.name + "_console.jsonl")
    cookies_path = stem.with_name(stem.name + "_cookies.json")
    return net_path, con_path, cookies_path


def write_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


async def record(
    ws_url: str, domain: str, net_path: Path, con_path: Path,
    cookies_path: Path, stop_event: asyncio.Event
) -> None:
    requests: dict[str, dict[str, Any]] = {}
    async with websockets.connect(ws_url, max_size=None) as ws:
        # Enable Network + Runtime domains.
        await ws.send(json.dumps({"id": 1, "method": "Network.enable",
                                  "params": {"maxPostDataSize": 1_048_576}}))
        await ws.send(json.dumps({"id": 2, "method": "Runtime.enable"}))
        print(
            f"[recorder] recording -> {net_path.name}, {con_path.name}",
            file=sys.stderr,
        )
        print("[recorder] press Ctrl-C to stop", file=sys.stderr)

        # Map CDP message id -> requestId for pending getResponseBody calls.
        pending_bodies: dict[int, str] = {}
        next_body_id = 100_000

        while not stop_event.is_set():
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            msg = json.loads(raw)
            method = msg.get("method")
            params = msg.get("params", {})

            if method == "Network.requestWillBeSent":
                rid = params.get("requestId")
                req = params.get("request", {})
                if domain not in req.get("url", ""):
                    continue
                record = {
                    "ts": time.time(),
                    "type": "request",
                    "requestId": rid,
                    "url": req.get("url"),
                    "method": req.get("method"),
                    "headers": req.get("headers", {}),
                    "postData": req.get("postData"),
                    "resourceType": params.get("type"),
                    "frameId": params.get("frameId"),
                }
                requests[rid] = {
                    "url": req.get("url"),
                    "method": req.get("method"),
                    "headers": req.get("headers", {}),
                    "postData": req.get("postData"),
                }
                write_jsonl(net_path, record)

            elif method == "Network.responseReceived":
                rid = params.get("requestId")
                resp = params.get("response", {})
                if domain not in resp.get("url", ""):
                    continue
                write_jsonl(net_path, {
                    "ts": time.time(),
                    "type": "response",
                    "requestId": rid,
                    "url": resp.get("url"),
                    "status": resp.get("status"),
                    "statusText": resp.get("statusText"),
                    "headers": resp.get("headers", {}),
                    "mimeType": resp.get("mimeType"),
                })

            elif method == "Network.loadingFinished":
                rid = params.get("requestId")
                if rid not in requests:
                    continue
                write_jsonl(net_path, {
                    "ts": time.time(),
                    "type": "loadingFinished",
                    "requestId": rid,
                    "encodedDataLength": params.get("encodedDataLength"),
                })
                # Request the response body for this request. The result
                # arrives asynchronously as a CDP response with our id.
                body_id = next_body_id
                next_body_id += 1
                pending_bodies[body_id] = rid
                try:
                    await ws.send(json.dumps({
                        "id": body_id,
                        "method": "Network.getResponseBody",
                        "params": {"requestId": rid},
                    }))
                except Exception as e:
                    print(
                        f"[recorder] getResponseBody send failed for "
                        f"{rid}: {e}", file=sys.stderr,
                    )

            elif msg.get("id") in pending_bodies:
                # CDP response to a getResponseBody call.
                body_id = msg["id"]
                rid = pending_bodies.pop(body_id)
                result = msg.get("result", {})
                write_jsonl(net_path, {
                    "ts": time.time(),
                    "type": "responseBody",
                    "requestId": rid,
                    "body": result.get("body"),
                    "base64Encoded": result.get("base64Encoded", False),
                })

            elif method == "Runtime.consoleAPICalled":
                write_jsonl(con_path, {
                    "ts": time.time(),
                    "type": params.get("type"),
                    "args": [a.get("value") or a.get("description")
                             for a in params.get("args", [])],
                    "stackTrace": params.get("stackTrace", {}).get(
                        "callFrames", []),
                    "executionContextId": params.get("executionContextId"),
                })

            elif method == "Runtime.exceptionThrown":
                exc = params.get("exceptionDetails", {})
                write_jsonl(con_path, {
                    "ts": time.time(),
                    "type": "exception",
                    "text": exc.get("text"),
                    "exception": exc.get("exception", {}).get("description"),
                    "stackTrace": exc.get("stackTrace", {}).get(
                        "callFrames", []),
                })

        # Session end: harvest cookies.
        print("[recorder] harvesting cookies via Network.getAllCookies",
              file=sys.stderr)
        await ws.send(json.dumps({"id": 99_999,
                                  "method": "Network.getAllCookies"}))
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
            except asyncio.TimeoutError:
                break
            msg = json.loads(raw)
            if msg.get("id") == 99_999:
                cookies = msg.get("result", {}).get("cookies", [])
                cookies_path.write_text(
                    json.dumps(cookies, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                print(f"[recorder] cookies -> {cookies_path.name} "
                      f"({len(cookies)} cookies)", file=sys.stderr)
                break


async def amain(host: str, port: int, domain: str) -> int:
    targets = await list_targets(host, port)
    if not targets:
        print(
            f"[recorder] no CDP targets at http://{host}:{port}. "
            f"Is Brave running with --remote-debugging-port={port}?",
            file=sys.stderr,
        )
        return 2
    target = await pick_target(targets, domain)
    ws_url = target["webSocketDebuggerUrl"]
    net_path, con_path, cookies_path = open_recordings(domain)

    stop_event = asyncio.Event()

    def _stop(*_: Any) -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    await record(ws_url, domain, net_path, con_path, cookies_path,
                 stop_event)
    print("[recorder] done", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--domain", default=DEFAULT_DOMAIN)
    args = p.parse_args(argv)
    return asyncio.run(amain(args.host, args.port, args.domain))


if __name__ == "__main__":
    raise SystemExit(main())
