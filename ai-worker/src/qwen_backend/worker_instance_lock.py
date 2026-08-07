from __future__ import annotations

import ctypes
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import IO


@dataclass(frozen=True, slots=True)
class WorkerInstanceAlreadyRunningError(RuntimeError):
    """The notebook GPU worker is already owned by another process."""

    lock_path: Path

    def __str__(self) -> str:
        return f"another AI Worker process owns the instance lock: {self.lock_path}"


class WorkerInstanceLock:
    """Hold an OS-level lock for the lifetime of one local GPU worker."""

    def __init__(self, lock_path: Path, *, enabled: bool = True) -> None:
        self._lock_path = lock_path
        self._enabled = enabled
        self._handle: IO[str] | None = None
        self._mutex_handle: ctypes.c_void_p | None = None

    def __enter__(self) -> WorkerInstanceLock:
        if not self._enabled:
            return self

        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            self._acquire_windows_mutex()
            return self

        handle = self._lock_path.open("a+", encoding="utf-8")
        try:
            _prepare_lock_byte(handle)
            _acquire_file_lock(handle)
        except OSError as error:
            handle.close()
            if _is_lock_contention(error):
                raise WorkerInstanceAlreadyRunningError(self._lock_path) from error
            raise
        self._handle = handle
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self._handle is None:
            if self._mutex_handle is not None:
                self._release_windows_mutex()
            return None
        try:
            _release_file_lock(self._handle)
        finally:
            self._handle.close()
            self._handle = None
        return None

    def _acquire_windows_mutex(self) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        create_mutex.restype = ctypes.c_void_p
        name = _windows_mutex_name(self._lock_path)
        ctypes.set_last_error(0)
        handle = create_mutex(None, True, name)
        error_code = ctypes.get_last_error()
        if not handle:
            raise OSError(error_code, "CreateMutexW failed")
        if error_code == 183:
            kernel32.CloseHandle(handle)
            raise WorkerInstanceAlreadyRunningError(self._lock_path)
        self._mutex_handle = handle

    def _release_windows_mutex(self) -> None:
        if self._mutex_handle is None:
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [ctypes.c_void_p]
        close_handle.restype = ctypes.c_bool
        release_mutex = kernel32.ReleaseMutex
        release_mutex.argtypes = [ctypes.c_void_p]
        release_mutex.restype = ctypes.c_bool
        handle = self._mutex_handle
        self._mutex_handle = None
        release_error = None
        try:
            if not release_mutex(handle):
                release_error = OSError(ctypes.get_last_error(), "ReleaseMutex failed")
        finally:
            if not close_handle(handle) and release_error is None:
                release_error = OSError(ctypes.get_last_error(), "CloseHandle failed")
        if release_error is not None:
            raise release_error


def _prepare_lock_byte(handle: IO[str]) -> None:
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write("0")
        handle.flush()
    handle.seek(0)


def _acquire_file_lock(handle: IO[str]) -> None:
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release_file_lock(handle: IO[str]) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _is_lock_contention(error: OSError) -> bool:
    return isinstance(error, BlockingIOError) or getattr(error, "winerror", None) == 33


def _windows_mutex_name(lock_path: Path) -> str:
    canonical_path = str(lock_path.resolve()).casefold().encode("utf-8")
    digest = hashlib.sha256(canonical_path).hexdigest()
    return f"Local\\EyesOnU_AI_Worker_{digest}"
