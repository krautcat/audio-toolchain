from typing import Optional, Type, Union

import mutagen
import mutagen.flac

from . import generic as _generic
from krautcat.audio.metadata.flac import Metadata as MetadataFLAC
from krautcat.audio.metadata.types import Date
from krautcat.audio.file.audio.generic import TagsBackend as GenericTagsBackend
from krautcat.gstreamer import ElementFLACDecoder, ElementFLACEncoder, ElementFLACParser


class TagsBackend(GenericTagsBackend):
    def __init__(self, audio_file: "AudioFileFLAC") -> None:
        super().__init__(audio_file)

        self._mutagen_file = mutagen.flac.FLAC(audio_file.path)
        
    def load_tags(self) -> MetadataFLAC:
        mutagen_tags = self._mutagen_file.tags    
        def _get_tag(name: str, default: Optional[str] = None) -> Union[str, None]:
            tag_values = mutagen_tags.get(name, default)
            if tag_values is not None:
                return tag_values[0] 

        track_name = _get_tag("title")
        track_number = int(_get_tag("tracknumber") or 0)
        artist = _get_tag("artist")
        album = _get_tag("album")       
      
        date = Date(_get_tag("date", None))

        tracks_total = int(_get_tag("tracktotal") or 0)

        krautcat_tags = MetadataFLAC(artist=artist,
                                                track_name=track_name,
                                                track_number=track_number,
                                                album=album,
                                                date=date)
        return krautcat_tags
        
    def save_tags(self, metadata: MetadataFLAC) -> bool:
        self._mutagen_file.tags["TITLE"] = metadata.track_name
        self._mutaen_file.tags["ALBUM"] = metadata.album
        self._mutaen_file.tags["ARTIST"] = metadata.artist

        if metadata.track_number is not None:
            self._mutaen_file.tags["TRACKNUMBER"] = str(metadata.track_number)
        if metadata.total_tracks is not None: 
            self._mutaen_file.tags["TRACKTOTAL"] = str(metadata.total_tracks)

        if metadata.date is not None:
            self._mutaen_file.tags["DATE"] = metadata.date

        self._mutagen_file.save()


class AudioFileFLAC(_generic.AudioFile):
    EXTENSION = "flac"
    
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
