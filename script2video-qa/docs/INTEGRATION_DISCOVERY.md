# Integration discovery

## Confirmed facts

- The supplied workspace `C:\Users\91863\OneDrive\Desktop\QA` was empty at inspection: it contained no application files, repository metadata, source code, API documentation, database models, environment configuration, or tests.
- Consequently, no frontend framework, backend framework, clip/job identifier format, generation state, authentication flow, data fields, or video retrieval interface could be verified.
- No endpoints belonging to the user's video-generation application have been assumed or called.
- The runnable application in this directory is isolated under `script2video-qa/` and its only current connector is a clearly labeled synthetic fixture connector. The `CLIP-102` fixture is mock data, not a real clip.
- FFmpeg/FFprobe was not found on PATH at implementation time, so local media inspection cannot currently be demonstrated.

## Assumptions and implementation boundary

- QA service routes under `/api` are newly proposed application routes; they are not routes of the existing generator.
- The fixture schema is an internal example only. No claim is made that the source application uses these names or fields.
- No real authentication has been attempted. No credentials are needed by the fixture connector.

## Information needed for a real connector

Provide access to the existing repository (or its relevant clip detail page and source modules), plus one authorized, redacted example of a clip lookup response and its associated generation-job/media response. Include the documented read-only authentication method and the fields that identify the existing completed video. If integration is via UI, provide a reachable authorized instance or documented stable selectors. These are needed to verify lookup, script/scene provenance, status polling, video retrieval, and authorization without guessing.
