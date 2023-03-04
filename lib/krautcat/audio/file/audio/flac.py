from typing import Optional, Type, Union

import mutagen
import mutagen.flac

from . import generic as _generic
from krautcat.audio.metadata import Metadata
from krautcat.audio.metadata.types import Date
from krautcat.audio.file.audio.generic import TagsBackend as GenericTagsBackend
from krautcat.gstreamer import ElementFLACDecoder, ElementFLACEncoder, ElementFLACParser


class TagsBackend(GenericTagsBackend):
    def __init__(self, audio_file: "AudioFileFLAC") -> None:
        super().__init__(audio_file)

        self._mutagen_file = mutagen.flac.FLAC(audio_file.path)
        
    def load_tags(self) -> Metadata:
        mutagen_tags = self._mutagen_file.tags

        def _get_tag(name: str, default: Optional[str] = None) -> Union[str, None]:
            tag_values = mutagen_tags.get(name, default)
            if isinstance(tag_values, list):
                return tag_values[0]
            else:
                return tag_values

        track_name = _get_tag("title")
        artist = _get_tag("artist")
        album = _get_tag("album")       
      
        date = Date(_get_tag("date", None))

        track_number_field = _get_tag("tracknumber", 0)
        track_number = 0
        total_tracks = 0
        if isinstance(track_number_field, str) and "/" in track_number_field:
            track_tag = track_number_field.split("/")
            track_number = track_tag[0]
            total_tracks = track_tag[1]
        else:
            track_number = int(track_number_field)
            total_tracks = int(_get_tag("tracktotal") or 0)

        disc_number_field = _get_tag("discnumber", None)
        disc_number = 0
        if isinstance(disc_number_field, str) and (
                "/" in disc_number_field
                or " / " in disc_number_field
                or ";" in disc_number_field):
            if "/" in disc_number_field:
                disc_tag = disc_number_field.split("/")
            elif " / " in disc_number_field:
                disc_tag = disc_number_field.split(" / ")
            elif ";" in disc_number_field:
                disc_tag = disc_number_field.split(";")
            disc_number = disc_tag[0]
            total_discs = disc_tag[1]
        elif disc_number_field is not None:
            disc_number = int(disc_number_field)
        else:
            disc_number = None

        total_discs_field = _get_tag("disctotal", None)
        total_discs = 0
        if total_discs_field is None or total_discs_field == "":
            total_discs = None
        else:
            total_discs = int(total_discs_field)

        krautcat_tags = Metadata(artist=artist,
                                 track_name=track_name,
                                 track_number=track_number,
                                 album=album,
                                 date=date,
                                 tracks_total=total_tracks,
                                 disc_number=disc_number,
                                 discs_total=total_discs)
        return krautcat_tags
        
    def save_tags(self, metadata: Metadata) -> bool:
        self._mutagen_file.tags["TITLE"] = metadata.track_name
        self._mutagen_file.tags["ALBUM"] = metadata.album
        self._mutagen_file.tags["ARTIST"] = metadata.artist

        if metadata.track_number is not None:
            self._mutagen_file.tags["TRACKNUMBER"] = str(metadata.track_number)
        if metadata.total_tracks is not None: 
            self._mutagen_file.tags["TRACKTOTAL"] = str(metadata.total_tracks)

        if metadata.date is not None:
            self._mutagen_file.tags["DATE"] = str(metadata.date)

        if metadata.disc_number is not None:
            self._mutagen_file.tags["DISCNUMBER"] = str(metadata.disc_number)
        if metadata.total_discs is not None: 
            self._mutagen_file.tags["DISCTOTAL"] = str(metadata.total_discs)

        self._mutagen_file.save()


class AudioFileFLAC(_generic.AudioFile):
    EXTENSION = "flac"
    SUFFIX = EXTENSION 

    def __init__(self, path, open=True):
        super().__init__(path)

        self._tags_backend = TagsBackend(self)
 
        if open: 
            self.metadata = self._tags_backend.load_tags()
        else:
            self.metadata = None

    def load_tags(self) -> None:
        self.metadata = self._tags_backend.load_tags()
        print(self.metadata)

    def save_tags(self):
        if self.metadata is not None:
            self._tags_backend.save_tags(self.metadata)
        else:
            raise ValueError()

    @property
    def gst_parser(self) -> Type[ElementFLACParser]:
        return ElementFLACParser

    @property
    def gst_decoder(self) -> Type[ElementFLACDecoder]:
        return ElementFLACDecoder

    @property
    def gst_encoder(self) -> Type[ElementFLACEncoder]:
        return ElementFLACEncoder
