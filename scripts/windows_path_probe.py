#!/usr/bin/env python3
"""Diagnose Windows rename APIs under pinned parents; never fail the CI step."""
from contextlib import ExitStack, contextmanager
import ctypes
import json
import os
from pathlib import Path
import sys
import tempfile


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def error_details(error):
    return {"type": type(error).__name__, "message": str(error),
            "winerror": getattr(error, "winerror", None),
            "errno": getattr(error, "errno", None),
            "filename": getattr(error, "filename", None)}


@contextmanager
def working_directory(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class WindowsAPI:
    def __init__(self):
        from ctypes import wintypes

        class FileInformation(ctypes.Structure):
            _fields_ = [("attributes", wintypes.DWORD), ("created", wintypes.FILETIME),
                        ("accessed", wintypes.FILETIME), ("written", wintypes.FILETIME),
                        ("volume", wintypes.DWORD), ("size_high", wintypes.DWORD),
                        ("size_low", wintypes.DWORD), ("links", wintypes.DWORD),
                        ("index_high", wintypes.DWORD), ("index_low", wintypes.DWORD)]

        class RenameInformation(ctypes.Structure):
            # The union's DWORD occupies the same first byte as ReplaceIfExists.
            _fields_ = [("flags", wintypes.DWORD), ("root", wintypes.HANDLE),
                        ("name_bytes", wintypes.DWORD), ("name", wintypes.WCHAR * 1)]

        class StatusUnion(ctypes.Union):
            _fields_ = [("status", wintypes.LONG), ("pointer", ctypes.c_void_p)]

        class IOStatusBlock(ctypes.Structure):
            _fields_ = [("result", StatusUnion), ("information", ctypes.c_size_t)]

        self.FileInformation = FileInformation
        self.RenameInformation = RenameInformation
        self.IOStatusBlock = IOStatusBlock
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.native = ctypes.WinDLL("ntdll", use_last_error=True)
        self.kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                           wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                           wintypes.HANDLE]
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE,
                                                           ctypes.POINTER(FileInformation)]
        self.kernel.GetFileInformationByHandle.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                           ctypes.c_void_p, wintypes.DWORD]
        self.kernel.SetFileInformationByHandle.restype = wintypes.BOOL
        self.native.NtSetInformationFile.argtypes = [wintypes.HANDLE,
                                                    ctypes.POINTER(IOStatusBlock),
                                                    ctypes.c_void_p, wintypes.ULONG,
                                                    ctypes.c_int]
        self.native.NtSetInformationFile.restype = wintypes.LONG
        self.native.RtlNtStatusToDosError.argtypes = [wintypes.LONG]
        self.native.RtlNtStatusToDosError.restype = wintypes.ULONG

    @contextmanager
    def open(self, path, directory=False):
        name = str(path)
        if not name.startswith("\\\\?\\"):
            name = "\\\\?\\UNC\\" + name[2:] if name.startswith("\\\\") else "\\\\?\\" + name
        # Parents: TRAVERSE | READ_ATTRIBUTES, sharing READ only.
        # Source: DELETE | READ_ATTRIBUTES, sharing READ | WRITE | DELETE.
        handle = self.kernel.CreateFileW(name, 0xA0 if directory else 0x10080,
                                         0x1 if directory else 0x7, None, 3,
                                         0x00200000 | (0x02000000 if directory else 0), None)
        if handle == ctypes.c_void_p(-1).value:
            error = ctypes.WinError(ctypes.get_last_error())
            error.filename = str(path)
            raise error
        try:
            info = self.FileInformation()
            if not self.kernel.GetFileInformationByHandle(handle, ctypes.byref(info)):
                raise ctypes.WinError(ctypes.get_last_error())
            if info.attributes & 0x400 or bool(info.attributes & 0x10) != directory:
                raise ValueError(f"Refusing reparse point or unexpected file type: {path}")
            yield handle
        finally:
            self.kernel.CloseHandle(handle)

    @contextmanager
    def pin(self, path):
        # Read-open all ancestors. All mutations remain under the new TEMP root.
        with ExitStack() as stack:
            current = Path(path.anchor)
            handle = stack.enter_context(self.open(current, directory=True))
            for part in path.parts[1:]:
                current /= part
                handle = stack.enter_context(self.open(current, directory=True))
            yield handle

    def rename_buffer(self, name, parent):
        if Path(name).name != name or any(c in name for c in ("/", "\\", "\0")):
            raise ValueError("The diagnostic only submits a simple basename")
        encoded = name.encode("utf-16-le")
        offset = self.RenameInformation.name.offset
        size = max(ctypes.sizeof(self.RenameInformation), offset + len(encoded) + 2)
        buffer = ctypes.create_string_buffer(size)
        header = self.RenameInformation.from_buffer(buffer)
        header.flags = 0  # Never replace an existing destination.
        header.root = parent
        header.name_bytes = len(encoded)
        ctypes.memmove(ctypes.addressof(buffer) + offset, encoded, len(encoded))
        return buffer, {"utf16_name_bytes": len(encoded), "name_offset": offset,
                        "buffer_bytes": size, "root_handle_supplied": parent is not None}

    def rename(self, method, source_handle, target_name, parent_handle):
        buffer, details = self.rename_buffer(target_name, parent_handle)
        if method == "win32_root":
            if not self.kernel.SetFileInformationByHandle(source_handle, 3, buffer, len(buffer)):
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            status_block = self.IOStatusBlock()
            status = self.native.NtSetInformationFile(source_handle, ctypes.byref(status_block),
                                                      buffer, len(buffer), 10)
            details.update(ntstatus=f"0x{status & 0xffffffff:08x}",
                           io_status=f"0x{status_block.result.status & 0xffffffff:08x}")
            if status < 0:
                error = ctypes.WinError(self.native.RtlNtStatusToDosError(status))
                error.ntstatus = details["ntstatus"]
                raise error
            if status == 0x103:
                raise RuntimeError("Unexpected STATUS_PENDING from a synchronous source handle")
        return details


def run_case(api, root, method, cross_parent):
    case_name = method + ("_cross_parent" if cross_parent else "_same_parent")
    case_root = root / case_name
    source_parent = case_root / "源目录😀"
    target_parent = case_root / "目标目录🧭" if cross_parent else source_parent
    source_parent.mkdir(parents=True)
    if cross_parent:
        target_parent.mkdir()
    source = source_parent / "原稿📝.txt"
    target = target_parent / "发布稿🚀.txt"
    source.relative_to(root)
    target.relative_to(root)
    original = "中文与非BMP正文：🦋\n".encode("utf-8")
    source.write_bytes(original)
    result = {"case": case_name, "method": method, "cross_parent": cross_parent,
              "source": str(source), "target": str(target), "api_success": False,
              "parent_access": "0xA0", "parent_share": "0x1",
              "source_access": "0x10080", "source_share": "0x7",
              "utf16_name_bytes": len(target.name.encode("utf-16-le"))}
    stage = "pin_source_parent"
    try:
        # Even an API that resolves a relative basename against CWD can only
        # write inside this case's new temporary directory.
        with working_directory(case_root), ExitStack() as stack:
            parent = stack.enter_context(api.pin(source_parent))
            if cross_parent:
                stage = "pin_target_parent"
                parent = stack.enter_context(api.pin(target_parent))
            stage = "open_source_for_delete"
            source_handle = stack.enter_context(api.open(source))
            stage = "rename"
            if method == "os_rename":
                os.rename(source, target)
            else:
                result.update(api.rename(method, source_handle, target.name,
                                         None if method == "native_simple" else parent))
            result["api_success"] = True
    except Exception as error:
        result.update(failed_stage=stage, error=error_details(error))
        if hasattr(error, "ntstatus"):
            result["error"]["ntstatus"] = error.ntstatus
    result.update(source_exists=source.exists(), destination_exists=target.exists(),
                  destination_matches=target.is_file() and target.read_bytes() == original,
                  source_unchanged_if_present=not source.exists() or source.read_bytes() == original,
                  unexpected_cwd_destination=(case_root / target.name).exists())
    return result


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.platform != "win32":
        emit({"event": "summary", "status": "skipped", "reason": "Native Windows required"})
        return 0
    temporary = None
    results = []
    try:
        api = WindowsAPI()
        with tempfile.TemporaryDirectory(prefix="story-windows-rename-probe-") as name:
            temporary = Path(name).resolve()
            for method in ("os_rename", "win32_root", "native_root"):
                for cross_parent in (False, True):
                    try:
                        result = run_case(api, temporary, method, cross_parent)
                    except Exception as error:
                        result = {"method": method, "cross_parent": cross_parent,
                                  "api_success": False, "failed_stage": "fixture_or_observation",
                                  "error": error_details(error)}
                    results.append(result)
                    emit({"event": "case", **result})
            result = run_case(api, temporary, "native_simple", False)
            results.append(result)
            emit({"event": "case", **result})
        emit({"event": "summary", "status": "completed", "cases": len(results),
              "successful_apis": [r.get("case") for r in results if r.get("api_success")],
              "temporary_data_removed": not temporary.exists()})
    except Exception as error:
        emit({"event": "summary", "status": "diagnostic_error", "cases": len(results),
              "error": error_details(error),
              "temporary_data_removed": temporary is None or not temporary.exists()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
