import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

import mutagen.mp4

from . import generic as _generic
class MetadataALAC(_generic.Metadata):
    def _track_name_setter_impl(self, source):
        if isinstance(source, mutagen.Tags):
            track_name = source.get("\xa9nam", None)
            if track_name is not None:
                self._track_name = track_name[0]

        elif isinstance(source, str):
            self._track_name = source

    def _artist_setter_impl(self, source):
        if isinstance(source, mutagen.Tags):
            artist = source.get("\xa9ART", None)
            if artist is not None:
                self._artist = artist[0]

        elif isinstance(source, str):
            self._artist = source

    def _album_setter_impl(self, source):
        if isinstance(source, mutagen.Tags):
            album = source.get("\xa9alb", None)
            if album is not None:
                self._album = album[0]

        elif isinstance(source, str):
            self._album = source

    def _date_setter_impl(self, source):
        if isinstance(source, mutagen.Tags):
            self._date = date = source.get("\xa9day", None)
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

    def _track_number_setter_impl(self, source):
        if isinstance(source, mutagen.Tags):
            track_number = source.get("trkn")
            if len(track_number) > 0:
                self._track_number = track_number[0][0]
            else:
                self._track_number = None

        elif isinstance(source, str):
            self._track_number = source

        elif isinstance(source, int):
            self._track_number = str(source)

    def _total_tracks_setter_impl(self, source):
        if isinstance(source, mutagen.Tags):
            track_number = source.get("trkn")
            if len(track_number) > 0:
                self._track_number = track_number[0][1]
            else:
                self._track_number = None

        elif isinstance(source, str):
            self._track_number = source

        elif isinstance(source, int):
            self._track_number = str(source)


class AudioFileALAC(_generic.AudioFile):
    def __init__(self, path):
        super().__init__(path, open=True)
        self.extension = "m4a"

        self.metadata = MetadataALAC(tags=self._tags)

    def _open_file(self, file_path):
        return mutagen.mp4.MP4(file_path)

    @property
    def gst_encoder(self):
        return Gst.ElementFactory.make("acdec_alac", None)


