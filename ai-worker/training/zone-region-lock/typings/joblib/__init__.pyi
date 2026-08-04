from io import BufferedIOBase
from os import PathLike

def dump(
    value: object,
    filename: str | PathLike[str] | BufferedIOBase,
    compress: int = ...,
    protocol: int | None = ...,
) -> list[str]: ...

def load(
    filename: str | PathLike[str] | BufferedIOBase,
    mmap_mode: str | None = ...,
    ensure_native_byte_order: str = ...,
) -> object: ...
