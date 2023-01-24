import pathlib

from abc import abstractmethod

from ... import exceptions as _exceptions


class Metadata:
    def __init__(self, tags=None):
        self._artist = None
        self._track_name = None
        self._album = None
        self._date = None

        self._track_number = None
        self._total_tracks = None

        if tags is not None:
            self.track_name = tags
            self.track_number = tags
            
            self.artist = tags
            self.date = tags
            self.album = tags

    def __str__(self):
        return (f"{self.track_number}. {self.track_name} ({self.artist} - {self.date} - {self.album})")

    def __ilshift__(self, other):
        self.track_name = other.track_name
        self.track_number = other.track_number

        self.total_tracks = other.total_tracks

        self.artist = other.artist
        self.date = other.date
        self.album = other.album

        return self

    @property
    def track_name(self):
        return self._track_name

    @track_name.setter
    def track_name(self, source):
        return self._track_name_setter_impl(source)

    @property
    def artist(self):
        return self._artist

    @artist.setter
    def artist(self, source):
        return self._artist_setter_impl(source)

    @property
    def album(self):
        return self._album

    @album.setter
    def album(self, source):
        return self._album_setter_impl(source)

    @property
    def date(self):
        return self._date

    @date.setter
    def date(self, source):
        return self._date_setter_impl(source)

    @property
    def track_number(self):
        return self._track_number

    @track_number.setter
    def track_number(self, source):
        return self._track_number_setter_impl(source)

    @property
    def total_tracks(self):
        return self._total_tracks

    @total_tracks.setter
    def total_tracks(self, source):
        return self._total_tracks_setter_impl(source)


class AudioFile:
    def __init__(self, path, *, open=True):
        self._path = pathlib.Path(path)

        if open:
            self._mutagen_file = self.open()
            if self._mutagen_file is not None:
                self._tags = self._mutagen_file.tags
            else:
                raise _exceptions.MutagenOpenFileError()
        else:
            self._mutagen_file = None
            self._tags = None

    @property
    def path(self):
        return self._path

    def open(self):
        return self._open_file(str(self._path))

    @abstractmethod
    def _open_file(self, path):
        ...
