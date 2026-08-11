from pathlib import Path
from zipfile import ZipFile


archive = Path("<redacted-local-path>")
destination = Path("<redacted-local-path>")
with ZipFile(archive) as source:
    count = 0
    for member in source.infolist():
        normalized = member.filename.replace("\\", "/")
        target = destination / normalized
        if member.is_dir() or normalized.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read(member))
        count += 1
print("extracted", count, "files", "to", destination)
