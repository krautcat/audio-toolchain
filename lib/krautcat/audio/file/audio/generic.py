import pathlib

from abc import abstractmethod
from typing import Union

from ... import exceptions as _exceptions
from krautcat.audio.metadata.generic import Metadata


class FileNotExistsError(Exception):
    def __init__(self, file_path: Union[pathlib.Path, str]) -> None:
        self.message = f"FIle 'file_path' doesn't exist"
        self.file = str(file_path)


class TagsBackend:
    def __init__(self, audio_file: "AudioFile") -> None:
        self._file = audio_file

    @abstractmethod        
    def load_tags(self) -> Metadata:
        ...

    @abstractmethod
    def save_tags(self) -> bool:
        ...


class AudioFile:
    def __init__(self, path: Union[pathlib.Path, str], *,
                 open=True):
        self._path = pathlib.Path(path)

        self._tags_backend = None

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, path: Union[pathlib.Path, str]) -> None:
        if type(path) == str:
            path = pathlib.Path(path)

        if path.exists():
            self._path = path
        else:
            raise FileNotExistsError(self._path)

    def open(self):
        if self._path is not None:
            return self._open_file(str(self._path))
        else:
            raise FileNotExistsError(self._path)

    @abstractmethod
    def _open_file(self, path):
        ...
