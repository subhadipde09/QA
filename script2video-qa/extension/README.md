# Script2Video QA Chrome extension

Manifest V3 popup for detecting visible clip-page hints and calling the local QA service. It uses `activeTab`, `scripting`, and `storage` plus a single host permission for `http://127.0.0.1:8000/*`. It does not have broad access to all websites, read cookies, or send video URLs to the backend.

## Build and install

From PowerShell:

```powershell
cd .\extension
npm install
npm run build
```

Start the QA API using the root README, then open `chrome://extensions`, turn on **Developer mode**, choose **Load unpacked**, and select `script2video-qa\extension\dist`. Pin the extension if desired. Rebuild and press the extension card's reload button after source changes.

The popup asks for active-tab access when used on an HTTP/HTTPS page. It reads the visible page title/path/text and checks `<video>` elements for presence/type and browser-exposed dimensions, duration, readiness, and media error state. It can pick up clip-like visible identifiers matching `CLIP-123`; this generic detector is only a convenience and is not a verified application integration. The input accepts a clip ID, an application page URL containing a `CLIP-123` style ID, or a YouTube URL. Application URLs are parsed locally and only the clip ID is sent to the fixture QA service. For a YouTube URL, the same video must be open in the active tab; the extension sends the YouTube ID plus browser-visible metadata to the local service. It never fetches or downloads the pasted URL or sends a media URL. YouTube reports cover browser-visible metadata only; codec/full-decode, frame, audio/script, and semantic checks remain INCONCLUSIVE.

## Backend and voice settings

The extension calls only the local QA service routes under `/api/v1`. The service currently uses the synthetic `CLIP-102` fixture connector. Testing another identifier will correctly return not found. The current-page endpoint says unavailable until a real adapter exists.

Voice Testing preference persists in local SQLite. When off, the report marks voice checks `SKIPPED`. When on, the report marks them `INCONCLUSIVE`: the local transcription worker and verified source script integration do not exist yet. No model is downloaded and no speech is processed.

## Domain configuration and limitations

There is no approved live domain to configure because the workspace did not include the video-generation application source or a reachable integration contract. Consequently, this version cannot enumerate all clips from a domain URL. The extension uses `activeTab` at the moment the user opens it and does not request persistent domain access. Before wiring a real API or all-clips discovery, verify the authorized origin, clip lookup/list response, expected-script source, generation status, media access method, and read-only auth flow. Add a narrowly scoped optional host permission only after that domain has been confirmed. Never forward cookies, authorization headers, or signed URLs to the QA backend.

The extension build was verified with Vite/TypeScript. Chrome installation and live-site testing still require a Chrome session and an authorized supported application page.
