#!/usr/bin/env python3
# ps5-native-app-boilerplate - FTP publication of a built application folder.
# Copyright (C) 2026 BlackBearReloaded
# SPDX-License-Identifier: GPL-3.0-or-later

from ftplib import FTP, error_perm
from pathlib import Path
from posixpath import dirname, join
import sys

def reply_code(error):
    return str(error).split(maxsplit=1)[0]


def list_names(ftp, path):
    previous = ftp.pwd()
    ftp.cwd(path)
    try:
        return {name for name, _ in ftp.mlsd() if name not in {".", ".."}}
    finally:
        ftp.cwd(previous)


def ensure_directory(ftp, path):
    current = ""
    for component in path.strip("/").split("/"):
        current += f"/{component}"
        try:
            ftp.mkd(current)
        except error_perm as error:
            if reply_code(error) != "550":
                raise
            previous = ftp.pwd()
            try:
                ftp.cwd(current)
            finally:
                ftp.cwd(previous)


def remove_if_present(ftp, path):
    try:
        # ftpsrv returns 226 for a successful DELE. FTP.sendcmd accepts every
        # valid 2xx completion while ftplib.FTP.delete only permits 200/250.
        ftp.sendcmd(f"DELE {path}")
        return True
    except error_perm as error:
        text = str(error).lower()
        if reply_code(error) == "550" and ("no such" in text or "not found" in text):
            return False
        raise


def upload_atomic(ftp, local, remote):
    directory = dirname(remote)
    temporary = join(directory, f".{remote.rsplit('/', 1)[-1]}.upload")
    ensure_directory(ftp, directory)
    remove_if_present(ftp, temporary)
    with local.open("rb") as source:
        ftp.storbinary(f"STOR {temporary}", source, blocksize=256 * 1024)
    # ftpsrv's RNTO calls rename(2) on the same directory. If the connection
    # drops, the destination contains either the old file or the complete new file.
    ftp.rename(temporary, remote)



def publish(ftp, title_id, artifact):
    critical = [artifact / "eboot.bin", artifact / "sce_sys/param.json"]
    files = sorted(
        path for path in artifact.rglob("*")
        if path.is_file() and path not in critical
    ) + critical
    print(f"==> [deploy] Publishing {len(files)} files; eboot.bin and param.json are last")
    remote_root = join("/data/homebrew", title_id)
    for index, local in enumerate(files, 1):
        relative = local.relative_to(artifact).as_posix()
        if "\n" in relative or "\r" in relative:
            raise RuntimeError(f"deployment paths cannot contain newlines: {relative!r}")
        print(f"==> [deploy] [{index}/{len(files)}] {relative}")
        upload_atomic(ftp, local, join(remote_root, relative))
    if "eboot.bin" not in list_names(ftp, remote_root):
        raise RuntimeError("FTP upload completed but eboot.bin is not listed")
    if "param.json" not in list_names(ftp, join(remote_root, "sce_sys")):
        raise RuntimeError("FTP upload completed but param.json is not listed")
    return remote_root


def main():
    host, port, user, password, title_id, artifact_name = sys.argv[1:]
    with FTP() as ftp:
        ftp.connect(host, int(port), timeout=15)
        ftp.login(user, password)
        remote_root = publish(ftp, title_id, Path(artifact_name))
        print(f"Deployment complete: ftp://{host}:{port}{remote_root}/")
        try:
            ftp.quit()
        except (EOFError, OSError):
            pass


if __name__ == "__main__":
    main()
