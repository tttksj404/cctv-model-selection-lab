from __future__ import annotations

import re
from pathlib import Path

import requests


file_id = "1Y-RFAYdT56vnMjwxH1Ym3DVhZzZuMQZs"
destination = Path(
    "<redacted-local-path>"
)
part = destination.with_suffix(destination.suffix + ".part")
destination.parent.mkdir(parents=True, exist_ok=True)
session = requests.Session()
first = session.get(
    "https://drive.google.com/uc",
    params={"export": "download", "id": file_id},
    timeout=60,
)
first.raise_for_status()
match = re.search(r'name="uuid" value="([^"]+)"', first.text)
params = {"export": "download", "id": file_id, "confirm": "t"}
if match:
    params["uuid"] = match.group(1)
response = session.get(
    "https://drive.usercontent.google.com/download",
    params=params,
    stream=True,
    timeout=60,
)
response.raise_for_status()
content_type = response.headers.get("content-type", "")
if "text/html" in content_type:
    raise RuntimeError(f"unexpected download response: {content_type}")
expected = int(response.headers.get("content-length", "0"))
written = 0
with part.open("wb") as stream:
    for chunk in response.iter_content(chunk_size=8 * 1024 * 1024):
        if chunk:
            stream.write(chunk)
            written += len(chunk)
            if written % (64 * 1024 * 1024) < len(chunk):
                print(f"downloaded={written} expected={expected}", flush=True)
part.replace(destination)
print(f"completed bytes={written} expected={expected} path={destination}")
