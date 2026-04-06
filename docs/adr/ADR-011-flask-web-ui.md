# ADR-011: Flask Web UI with Server-Sent Events

## Status
Accepted

## Context

The agent was originally invoked exclusively via the CLI (`main.py`), which required users to:
- Edit `.env` or pass flags to select input files
- Read raw terminal output to track conversion progress
- Have Python/CLI familiarity to operate the tool

To lower the barrier to use and make the conversion pipeline observable in real time, a browser-based UI was needed that would allow users to:
- Browse and select Java source files from the local filesystem
- Trigger a conversion run without touching the command line
- Watch agent progress stream live as each LangGraph node completes
- See structured output (converted files, errors) in context

**Alternatives considered:**

| Option | Reason Rejected |
|---|---|
| Streamlit | Adds a heavyweight dependency (~80 MB); session model conflicts with long-running background threads needed for streaming |
| Gradio | Designed for ML demo UIs; poor fit for file-tree browsing and multi-step pipeline feedback |
| FastAPI + WebSockets | WebSocket lifecycle management adds complexity; SSE is simpler and sufficient for unidirectional server→client streaming |
| Electron / desktop app | Packaging overhead; overkill for a developer-internal tool |
| Rich TUI (terminal) | Stays CLI-only; no shareable link, no browser-native copy/paste of generated code |

## Decision

Use **Flask** (`flask>=3.0.0`) as the HTTP server with a **single-file UI** (`ui.py`) that:

- Serves one HTML page rendered via `render_template_string` — no `templates/` directory, keeping the UI self-contained in a single file.
- Exposes the following routes backed by `CodeScanner`, `DependencyMapper`, and the LangGraph workflow:
  - `GET /` — serves the single-page UI
  - `POST /scan` — scans a Java project directory and returns the file/class tree
  - `POST /save` — persists user-selected class choices to state
  - `POST /convert` — triggers the full conversion pipeline; streams progress back via SSE
- Streams conversion progress to the browser via **Server-Sent Events** (`text/event-stream`) using `flask.stream_with_context` and a `queue.Queue` bridging the background worker thread to the SSE response.
- Runs the conversion in a **`threading.Thread`** so the Flask response thread is never blocked while the LangGraph pipeline executes.

```python
# SSE endpoint pattern
@app.route("/convert", methods=["POST"])
def convert():
    q = queue.Queue()
    threading.Thread(target=_run_conversion, args=(files, q), daemon=True).start()

    def generate():
        while True:
            msg = q.get()
            yield f"data: {json.dumps(msg)}\n\n"
            if msg.get("type") == "done":
                break

    return Response(stream_with_context(generate()), mimetype="text/event-stream")
```

Reference files:
- [`ui.py`](../../ui.py)

## Consequences

**Positive:**
- Flask is already a transitive dependency of many Python environments and adds minimal weight (`flask>=3.0.0` < 1 MB).
- The single-file approach (`render_template_string` + inline CSS/JS) means the UI ships with zero additional asset files — the entire frontend is readable in one place.
- SSE requires no WebSocket handshake or persistent connection management; the browser's native `EventSource` API handles reconnection automatically.
- The `queue.Queue` bridge decouples the LangGraph worker thread from Flask's response thread cleanly, with no shared mutable state beyond the queue.
- The server is started directly with `python ui.py` — no external process supervisor is required for single-user developer use.

**Negative:**
- Flask's development server (`app.run()`) is single-threaded by default — concurrent conversion requests from multiple browser tabs will queue. A production WSGI server (e.g., Gunicorn) would be needed if multi-user access becomes a requirement.
- Embedding the full HTML/CSS/JS in a Python string makes the frontend harder to edit with IDE tooling (no syntax highlighting, no hot reload). This trade-off is acceptable while the UI remains a developer convenience tool.
- SSE connections are unidirectional; if bidirectional communication (e.g., cancel a running conversion) is needed in the future, WebSockets or a polling endpoint would need to be introduced.
