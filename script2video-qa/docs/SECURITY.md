# Security and operations

- API and Vite bind to `127.0.0.1` by default. CORS is restricted to local dashboard origins.
- Runtime supports no remote video URL fetching. The current fixture only accepts contained local paths, avoiding SSRF in this non-integrated build.
- A future remote connector must implement scheme/domain/IP validation, redirect revalidation, size limits, safe temp-file downloads and secret redaction before it is enabled.
- FFprobe is optional, passed a fixed argument list, and has a 30-second timeout. Set `S2VQA_DATA_DIR` to choose the report/database directory.
- Credentials are not stored. `.env.example` includes no live secrets.
- Retention is currently manual: remove old report artifacts and the SQLite database only when their history is no longer needed. Large media is not copied into SQLite.
