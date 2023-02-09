from typing import Optional

from krautcat.audio.metadata.generic import Metadata as GenericMetadata
from krautcat.audio.metadata.types import Date


class Metadata(GenericMetadata):
    def __init__(self, *, artist: Optional[str] = None, track_name: Optional[str] = None,
                 album: Optional[str] = None, date: Optional[Date] = None,
                 track_number: Optional[int] = None,
                 tracks_total: Optional[int] = None) -> None:
        super().__init__()

        self._artist = artist
        self._track_name = track_name
        self._album = album
        self._date = date

        self._track_number = track_number
        self._total_tracks = tracks_total       

    @property
    def track_name(self) -> str:
        return self._track_name

    @track_name.setter
    def track_name(self, source):
        self._track_name = source

    @property
    def track_number(self) -> int:
        return self._track_number

    @track_number.setter
    def track_number(self, source):
        self._track_number = int(source)

    @property
    def artist(self):
        return self._artist 

    @artist.setter
    def artist(self, source):
        self._artist = source

    @property
    def album(self) -> str:
        return self._album

    @album.setter
    def album(self, source):
        self._album = source

    @property
    def date(self) -> str:
        return self._date

    @date.setter
    def date(self, source):
            self._date = str(source)

    @property
    def total_tracks(self) -> int:
        return self._total_tracks

    @total_tracks.setter
    def total_tracks(self, source) -> None:
        self._total_tracks = int(source)
