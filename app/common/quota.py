from __future__ import annotations

SOURCE_MAX_BYTES = 128 * 1024
STDIN_MAX_BYTES = 32 * 1024

class QuotaError(ValueError):
    pass

def enforce_source_stdin(source: str, stdin: str | None):
    if len(source.encode()) > SOURCE_MAX_BYTES:
        raise QuotaError("payload_too_large: source_code exceeds 128KiB limit")
    if stdin and len(stdin.encode()) > STDIN_MAX_BYTES:
        raise QuotaError("payload_too_large: stdin exceeds 32KiB limit")

__all__ = ["enforce_source_stdin", "QuotaError"]
