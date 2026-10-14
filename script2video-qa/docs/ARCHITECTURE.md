# Architecture

The local UI (Vite/React/TypeScript) calls the loopback FastAPI service. FastAPI uses a connector boundary currently represented by `discover()` and a synthetic JSON fixture. Tests are run in an asynchronous in-process job registry; the final reports and run history are persisted in SQLite and JSON/HTML/CSV artifacts in `artifacts/`. Media probing is dispatched to a worker thread and invokes FFprobe via a fixed argument list when installed.

This single-user starter does not yet provide durable queued-job recovery or an external application connector. On restart, any in-memory active jobs are lost; completed run history survives. Never configure it for public network exposure.
