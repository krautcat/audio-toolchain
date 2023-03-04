from typing import Optional
import sys

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

import mutagen.mp4

from krautcat.audio.metadata import Metadata
from krautcat.audio.metadata.types import Date
from krautcat.audio.file.audio.generic import (
        AudioFile, TagsBackend as GenericTagsBackend
    )


class TagsBackend(GenericTagsBackend):
    def __init__(self, audio_file: "AudioFileALAC") -> None:
        super().__init__(audio_file)

        self._mutagen_file = mutagen.mp4.MP4(audio_file.path)

    def load_tags(self) -> Metadata: 
        mutagen_tags = self._mutagen_file.tags
        if mutagen_tags is None:
            print("No tags!", file=sys.stderr)
            self._mutagen_file.add_tags()
            mutagen_tags = self._mutagen_file.tags

        track_number_field = mutagen_tags.get("trkn", None)
        if track_number_field is not None and len(track_number_field) > 0:
            track_number = int(track_number_field[0][0])
            tracks_total = int(track_number_field[0][1])
        else:
            track_number = 0
            tracks_total = 0
        
        track_name = mutagen_tags.get("\xa9nam", None) or ""
        artist = mutagen_tags.get("\xa9ART", None) or ""
        album = mutagen_tags.get("\xa9alb", None) or ""

        date_field = mutagen_tags.get("\xa9day", None)
        date_tag = date_field[0] if isinstance(date_field, list) else date_field
        date = Date(date_tag)

        disc_number_field = mutagen_tags.get("disk", None)
        if disc_number_field is not None and len(disc_number_field) > 0:
            disc_number = disc_number_field[0][0]
            discs_total = disc_number_field[0][1]
        else:
            disc_number = 1
            discs_total = 1

        krautcat_tags = Metadata(artist=artist,
                                 track_name=track_name,
                                 track_number=track_number,
                                 album=album,
                                 date=date,
                                 tracks_total=tracks_total,
                                 disc_number = disc_number,
                                 discs_total = discs_total)
        return krautcat_tags

    def save_tags(self, metadata: Optional[Metadata] = None) -> bool:
        mutagen_tags = self._mutagen_file.tags

        mutagen_tags["\xa9nam"] = metadata.track_name
        mutagen_tags["\xa9ART"] = metadata.album
        mutagen_tags["\xa9alb"] = metadata.artist

        track_number_field = list(list())
        if metadata.track_number is not None:
            track_number_field[0][0] = metadata.track_number
        if metadata.total_tracks is not None: 
            track_number_field[0][1] = metadata.total_tracks
        mutagen_tags["trkn"] = track_number_field

        if metadata.date is not None:
            mutagen_tags["\xa9day"] = str(metadata.date)

        disc_number_field = list(list())
        if metadata.disc_number is not None:
            disc_number_field[0][0] = metadata.disc_number
        if metadata.total_discs is not None:
            disc_number_field[0][1] = metadata.total_discs
        mutagen_tags["disk"] = disc_number_field

        self._mutagen_file.save()


class AudioFileALAC(AudioFile):
    EXTENSION = "m4a"
    SUFFIX = EXTENSION

    def __init__(self, path, *, open=True):
        print(f"Initing '{path}' file", file=sys.stderr)
        super().__init__(path)

        self._tags_backend = TagsBackend(self)

        if open:
            self.metadata = self.load_tags()
        else:
            self.metadata = None

    def load_tags(self) -> None:
        self.metadata = self._tags_backend.load_tags()

    def save_tags(self):
        if self.metadata is not None:
            self._tags_backend.save_tags(self.metadata)
        else:
            raise ValueError()

    @property
    def gst_encoder(self):
        return Gst.ElementFactory.make("acdec_alac", None)


