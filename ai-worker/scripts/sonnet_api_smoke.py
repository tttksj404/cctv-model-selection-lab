#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx2[http2,brotli,zstd]",
# ]
# ///

# How to run
# 1. Install uv if it is not installed.
# 2. Run: uv run --script scripts/sonnet_api_smoke.py
# 3. The key is read from the user-authorized file and is never printed or written.

from __future__ import annotations

import json
import re
import socket
from pathlib import Path

import httpx2

KEY_FILE = Path(r"C:\Users\SSAFY\Desktop\ai\claude key.env.txt")
MODELS_URL = "https://api.anthropic.com/v1/models"
MESSAGES_URL = "https://api.anthropic.com/v1/messages"


def read_key(path: Path) -> str | None:
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip().strip(chr(34)).strip(chr(39))
        if value.startswith("sk-ant-"):
            return value
    return None


def choose_sonnet(models: list[dict[str, str | None]]) -> str | None:
    sonnet_models = [item for item in models if "sonnet" in str(item.get("id", "")).lower()]
    ordered = sorted(sonnet_models, key=lambda item: str(item.get("created_at", "")), reverse=True)
    return ordered[0].get("id") if ordered else None


def safe_error(response: httpx2.Response) -> dict[str, str | int]:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    error_type = error.get("type", "unknown") if isinstance(error, dict) else "unknown"
    message = error.get("message", "") if isinstance(error, dict) else ""
    safe_message = re.sub(r"sk-ant-[A-Za-z0-9_-]+", "[REDACTED]", str(message))[:240]
    return {"status": response.status_code, "type": str(error_type), "message": safe_message}


def main() -> None:
    result: dict[str, object] = {
        "key_file_exists": KEY_FILE.is_file(),
        "key_detected": False,
        "status": "not_started",
    }
    if not KEY_FILE.is_file():
        result["status"] = "blocked_missing_key_file"
        print(json.dumps(result, ensure_ascii=False))
        return
    key = read_key(KEY_FILE)
    if key is None:
        result["status"] = "blocked_missing_key"
        print(json.dumps(result, ensure_ascii=False))
        return
    result["key_detected"] = True
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    limits = httpx2.Limits(
        max_connections=50, max_keepalive_connections=20, keepalive_expiry=30.0
    )
    timeout = httpx2.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
    transport = httpx2.HTTPTransport(
        http2=True,
        retries=3,
        limits=limits,
        socket_options=[(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)],
    )
    with httpx2.Client(
        transport=transport, timeout=timeout, follow_redirects=True
    ) as client:
        models_response = client.get(MODELS_URL, headers=headers)
        result["models_status"] = models_response.status_code
        if models_response.status_code != 200:
            result["status"] = "models_request_rejected"
            result["error"] = safe_error(models_response)
            print(json.dumps(result, ensure_ascii=False))
            return
        payload = models_response.json()
        raw_models = payload.get("data", []) if isinstance(payload, dict) else []
        models = [
            {
                "id": item.get("id"),
                "created_at": item.get("created_at"),
            }
            for item in raw_models
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
        sonnet_models = [item for item in models if "sonnet" in str(item.get("id", "")).lower()]
        selected = choose_sonnet(models)
        result["sonnet_models"] = sonnet_models
        result["selected_model"] = selected
        if selected is None:
            result["status"] = "blocked_no_sonnet_model"
            print(json.dumps(result, ensure_ascii=False))
            return
        message_response = client.post(
            MESSAGES_URL,
            headers=headers,
            json={
                "model": selected,
                "max_tokens": 32,
                "temperature": 0,
                "messages":[
                    {"role": "user", "content": 'Return JSON only: {"ok":true}'},
                ],
            },
        )
        result["message_status"] = message_response.status_code
        result["message_ok"] = message_response.status_code == 200
        if message_response.status_code == 200:
            response_payload = message_response.json()
            result["usage"] = response_payload.get("usage")
            result["stop_reason"] = response_payload.get("stop_reason")
            result["status"] = "authenticated"
        else:
            result["status"] = "message_request_rejected"
            result["error"] = safe_error(message_response)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
