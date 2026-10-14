# Validation rules

- Overall precedence: any FAIL makes the report FAIL; otherwise any INCONCLUSIVE makes it INCONCLUSIVE; PASS requires all checks to be evaluable and passing.
- The fixture job status is checked as completed/succeeded. No generation endpoint or write action exists in the app.
- Video file paths must resolve inside the application directory. A missing fixture file is INCONCLUSIVE; a path escaping the root is FAIL.
- FFprobe checks are INCONCLUSIVE if FFprobe is unavailable or inspection fails. Explicit expected duration allows ±0.25 seconds; explicitly expected dimensions, frame rate, and codec compare exactly.
- Semantic character/action correctness is INCONCLUSIVE. No AI, image recognition, OCR or speech recognition is used.
- Subtitle/script comparison, frame metrics, full decode, audio silence analysis, artifact extraction, and scene-manifest timing checks are not yet implemented; their absence must not be interpreted as passing.
