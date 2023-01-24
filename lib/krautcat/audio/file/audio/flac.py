import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

import mutagen.flac

from . import generic as _generic


class MetadataFLAC(_generic.Metadata):
    def _track_name_setter_impl(self, source):
        if isinstance(source, mutagen.Tags):
            track_name = source.get("TITLE", None)
            if track_name is not None:
                self._track_name = track_name[0]

        elif isinstance(source, str):
            self._track_name = source

    def _track_number_setter_impl(self, source):
        if isinstance(source, mutagen.Tags):
            track_name = source.get("TRACKNUMBER", None)
            if track_name is not None:
                self._track_number = track_name[0]

        elif isinstance(source, str):
            self._track_number = source

    def _artist_setter_impl(self, source):
        if isinstance(source, mutagen.Tags):
            artist = source.get("artist", None)
            if artist is not None:
                self._artist = artist[0]

        elif isinstance(source, str):
            self._artist = source

    def _album_setter_impl(self, source):
        if isinstance(source, mutagen.Tags):
            album = source.get("album", None)
            if album is not None:
                self._album = album[0]

        elif isinstance(source, str):
            self._album = source

    def _date_setter_impl(self, source):
        if isinstance(source, mutagen.Tags):
            self._date = date = source.get("date", None)
            if isinstance(date, list):
                date_new = date[0]
                for d in date:
                    try:
                        int(d)
                        date_new = d
                        break
                    except ValueError:
                        continue

                self._date = date_new

        elif isinstance(source, str):
            self._date = source

        elif isinstance(source, int):
            self._date = str(source)


class AudioFileFLAC(_generic.AudioFile):
    def __init__(self, path, open=True):
        super().__init__(path, open=open)
        self.extension = "flac"

        self.metadata = MetadataFLAC(tags=self._tags)

    def _open_file(self, file_path):
        return mutagen.flac.FLAC(file_path)

    def save_tags(self):
        self._tags["TITLE"] = self.metadata.track_name
        self._tags["ALBUM"] = self.metadata.album
        self._tags["ARTIST"] = self.metadata.artist

        if self.metadata.track_number is not None:
            self._tags["TRACKNUMBER"] = str(self.metadata.track_number)
        if self.metadata.total_tracks is not None: 
            self._tags["TRACKTOTAL"] = str(self.metadata.total_tracks)

        if self.metadata.date is not None:
            self._tags["DATE"] = self.metadata.date

        self._mutagen_file.save()

    @property
    def gst_decoder(self):
        return Gst.ElementFactory.make("flacdec", None)

