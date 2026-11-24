#!/usr/bin/env python3
# ps5-native-app-boilerplate - Create and validate a console app-folder ZIP.
# Copyright (C) 2026 BlackBearReloaded
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
from pathlib import Path
import shutil
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


def add_entry(archive, path, name, ancestors):
    info = ZipInfo.from_file(path, name)
    info.create_system = 3
    if path.is_dir():
        source = path.resolve()
        if source in ancestors:
            raise ValueError(f"directory link cycle at {path}")
        info.external_attr = (0o040777 << 16) | 0x10
        archive.writestr(info, b"")
        for child in sorted(path.iterdir()):
            add_entry(archive, child, f"{name}/{child.name}", ancestors | {source})
    elif path.is_file():
        info.compress_type = ZIP_DEFLATED
        info.external_attr = 0o100777 << 16
        with path.open("rb") as source, archive.open(info, "w") as target:
            shutil.copyfileobj(source, target, length=256 * 1024)
    else:
        raise ValueError(f"not a regular file or directory: {path}")


def package_app(app, output):
    if not app.is_dir():
        raise ValueError(f"application directory does not exist: {app}")
    with tempfile.TemporaryDirectory(prefix=f".{output.name}.", dir=output.parent) as directory:
        temporary = Path(directory) / output.name
        with ZipFile(temporary, "w") as archive:
            add_entry(archive, app, app.name, set())
        with ZipFile(temporary) as archive:
            entries = archive.infolist()
            wrong_modes = [
                info.filename for info in entries if (info.external_attr >> 16) & 0o777 != 0o777
            ]
            corrupt = archive.testzip()
            if wrong_modes or corrupt is not None:
                raise ValueError(f"ZIP check failed: incorrect modes {wrong_modes[:3]}, CRC {corrupt}")
        temporary.replace(output)
    return len(entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(f"{args.output}: {package_app(args.app, args.output)} entries stored as 0777")


if __name__ == "__main__":
    main()
