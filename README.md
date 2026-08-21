# webuntis-agent

Reverse-engineering the WebUntis API to automate **Lehrstoff** (lesson topic
entry) for Georg Graf's teaching at HTL Spengergasse.

## Goal

Automate the manual "Lehrstoff eintragen" step in WebUntis by replaying the
undocumented REST/JSON-RPC endpoints that the WebUntis web UI calls when a
teacher records the topic of a lesson.

## Approach

1. **CDP-Recorder** attaches to a running Brave (Chromium) browser via the
   Chrome DevTools Protocol (`--remote-debugging-port=9222`).
2. While the user performs the "Lehrstoff eintragen" action in the WebUntis
   UI as usual, the recorder captures all `Network.*` and `Runtime.*`
   (console) events for the WebUntis domain into structured JSONL files
   under `recordings/`.
3. The captured requests are analyzed to identify the write endpoint(s).
4. A `client.py` replays those endpoints with session cookies harvested via
   `Network.getAllCookies`.
5. A CLI/agent derives the Lehrstoff from the GRG-* teaching repository Git
   logs (see `~/repos/georgernstgraf/GRG-*` and the AGENTS.md in `~/`) and
   submits it via the client.

## School

- WebUntis host: `https://spengergasse.webuntis.com/`
- School slug (for `?school=...`): `spengergasse`

## Stack

- Python 3.11+
- `playwright` (CDP attach + automation)
- `httpx` (HTTP client, replay)
- `websockets` (raw CDP if needed)

## Project layout

```
webuntis-agent/
  pyproject.toml
  src/webuntis_agent/
    recorder.py        # CDP-Recorder: Network + Runtime -> recordings/
    client.py          # WebUntis API client (replay identified endpoints)
    cli.py             # CLI entry point
  scripts/
    brave-debug.sh      # start Brave with --remote-debugging-port=9222
  recordings/          # gitignored: captured requests + console logs
  docs/
    WEBUNTIS_API.md    # reference doc of known endpoints
  AGENTS.md
```

## Status

Phase 1-3 in progress: skeleton + CDP-Recorder.
