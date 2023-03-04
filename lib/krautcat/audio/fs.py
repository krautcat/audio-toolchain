import os
import pathlib
import re

import psutil


class FilesystemGeneric:
    @staticmethod
    def escape_filename(filename):
        replacements = [
            (re.compile(r"[/:]"), r"_"),
            (re.compile(r"[\?]"), r"!"),
        ]

        for regexp_replace, regexp_substit in replacements:
            filename = re.sub(regexp_replace, regexp_substit, filename)

        return filename


class FilesystemExFAT(FilesystemGeneric):
    ...


_fsname_klass = {
    "exfat": FilesystemExFAT,
}


def get_fs_class(path):
    path = pathlib.Path(path).resolve(strict=True)

    partitions = {}
    
    for part in psutil.disk_partitions():
        partitions[pathlib.Path(part.mountpoint)] = part.fstype
   
    if path in partitions:
        if partitions[path] in _fsname_klass:
            return _fsname_klass[partitions[path]]
        else:
            return FilesystemGeneric
    
    while path != pathlib.Path("/"):
        path = path.parent

        if path in partitions:
            if partitions[path] in _fsname_klass:
                return _fsname_klass[partitions[path]]
            else:
                return FilesystemGeneric
    
    return FilesystemGeneric
