# Script2Video QA

Local dashboard and deterministic report service for validating generated clips. The supplied workspace had no video-generation application source or integration documentation, so this build runs with **synthetic mock fixture data only**. It does not yet retrieve a real application's clip or video. It never starts generation jobs.

## Requirements

- Python 3.12 or later
- Node.js 20 or later
- FFmpeg/FFprobe is optional; install it and put `ffprobe` on PATH to enable media inspection.

## Run on Windows PowerShell

```powershell
cd .\backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd .\frontend
npm install
npm run dev
```

## Run on Linux/macOS

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal run `cd frontend && npm install && npm run dev`.

Open `http://127.0.0.1:5173`, enter `CLIP-102`, and run the mock workflow. Interactive API docs are at `http://127.0.0.1:8000/docs`. Output is stored under `artifacts/` (or `S2VQA_DATA_DIR`).

## Tests and build

```powershell
cd backend
python -m pytest
cd ..\frontend
npm install
npm run build
```

## Integration status and limitations

See [`docs/INTEGRATION_DISCOVERY.md`](docs/INTEGRATION_DISCOVERY.md). To complete the real connector, the source repository or reachable authorized instance and redacted examples of clip lookup, generation job, metadata, and completed-video retrieval responses are required. Credentials must be configured through an approved secret mechanism; none are stored by this app.

The current implementation has a fixture connector, SQLite history, API job state, and JSON/HTML/CSV report downloads. It does not yet implement durable queue recovery, multi-match selection UI, external authentication, source URL download security, full decode, subtitle matching, scene timing validation, audio checks, frame evidence, or run-to-run UI comparisons. Unsupported semantic checks are explicitly INCONCLUSIVE. See `docs/VALIDATION_RULES.md` and `docs/SECURITY.md`.

## Chrome extension

The separate Manifest V3 extension is in [`extension/`](extension/). Build it with `cd extension; npm install; npm run build`, then load `extension/dist` through Chrome's `chrome://extensions` → Developer mode → Load unpacked. The extension currently detects generic visible page hints and uses the local fixture QA API; no live application domain has been verified. Its integration limits and permissions are described in [`extension/README.md`](extension/README.md).
