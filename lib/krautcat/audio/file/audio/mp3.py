from typing import Optional, Union

import mutagen.id3
import mutagen.mp3

from . import generic as _generic
from ... import exceptions as _exceptions

from krautcat.audio.file.audio.generic import TagsBackend as GenericTagsBackend
from krautcat.audio.metadata import Metadata
from krautcat.audio.metadata.types import Date


class TagsBackend(GenericTagsBackend):
    def __init__(self, audio_file: "AudioFileMP3") -> None:
        super().__init__(audio_file)

        self._mutagen_file = mutagen.mp3.MP3(audio_file.path)

    def load_tags(self) -> Metadata: 
        mutagen_tags = self._mutagen_file.tags
        if mutagen_tags is None:
            self._mutagen_file.add_tags()
            mutagen_tags = self._mutagen_file.tags

        def _get_tag(name: str, default: Optional[str] = None) -> Union[str, None]:
            frame = mutagen_tags.getall(name)
            if len(frame) > 0:
                return frame[0].text[0]
            return default

        track_number_field = _get_tag("TRCK") or 0
        total_tracks_field = 0
        if (isinstance(track_number_field, str) 
                and ("/" in track_number_field
                        or " " in track_number_field)):
            sep = ""
            if "/" in track_number_field:
                sep = "/"
            elif " " in track_number_field:
                sep = " "
            track_tag = track_number_field.split(sep)
            track_number_field = track_tag[0]
            total_tracks_field = track_tag[1]
        track_number = int(track_number_field)
        tracks_total = int(_get_tag("TXXX:TOTALTRACKS") or total_tracks_field or 0)
        
        track_name = _get_tag("TIT2")
        artist = _get_tag("TPE1")
        album = _get_tag("TALB")

        date = Date(_get_tag("TDRC", None))

        disc_number = int(_get_tag("TXXX:DISCNUMBER", 0)) or None
        discs_total = int(_get_tag("TXXX:TOTALDISCS", 0)) or None

        krautcat_tags = Metadata(artist=artist,
                                 track_name=track_name,
                                 track_number=track_number,
                                 album=album,
                                 date=date,
                                 tracks_total=tracks_total,
                                 disc_number=disc_number,
                                 discs_total=discs_total)
        return krautcat_tags

    def save_tags(self, metadata: Optional[Metadata] = None) -> bool:
        mutagen_tags = self._mutagen_file.tags

        mutagen_tags.setall("TIT2", [mutagen.id3.TIT2(encoding=3, text=metadata.track_name)])
        mutagen_tags["TALB"] = mutagen.id3.TALB(encoding=3, text=metadata.album)
        mutagen_tags["TPE1"] = mutagen.id3.TPE1(encoding=3, text=metadata.artist)

        if metadata.track_number is not None:
            mutagen_tags["TRCK"] = mutagen.id3.TRCK(encoding=3, text=str(metadata.track_number))
       
        if metadata.total_tracks is not None: 
            mutagen_tags["TXXX:TOTALTRACKS"] = mutagen.id3.TXXX(
                encoding=mutagen.id3.Encoding.UTF8,
                desc="TOTALTRACKS",
                text=str(metadata.total_tracks)
            )

        if metadata.date is not None:
            mutagen_tags["TDRC"] = mutagen.id3.TDRC(encoding=3, text=str(metadata.date))

        if metadata.disc_number is not None:
            mutagen_tags["TXXX:DISCNUMBER"] = mutagen.id3.TXXX(
                encoding=mutagen.id3.Encoding.UTF8,
                desc="DISCNUMBER",
                text=str(metadata.disc_number)
            )

        if metadata.total_discs is not None:
            mutagen_tags["TXXX:TOTALDISCS"] = mutagen.id3.TXXX(
                encoding=mutagen.id3.Encoding.UTF8,
                desc="TOTALDISCS",
                text=str(metadata.total_discs)
            )

        self._mutagen_file.save()


class AudioFileMP3(_generic.AudioFile):
    EXTENSION = "mp3"
    SUFFIX = EXTENSION 
        
    def __init__(self, path, *, open=True):
        super().__init__(path)

        self._tags_backend = TagsBackend(self)

        if open:
            self.metadata = self._tags_backend.load_tags()
        else:
            self.metadata = None

    def load_tags(self) -> None:
        self.metadata = self._tags_backend.load_tags()

    def save_tags(self):
        if self.metadata is not None:
            self._tags_backend.save_tags(self.metadata)
        else:
            raise ValueError()



class MP3Encoder:
    def __init__(self, audio_file):
        self._mp3_encoder = lameenc.Encoder()
        self._mp3_encoder.set_bit_rate(320)
        self._mp3_encoder.set_in_sample_rate(44100)
        self._mp3_encoder.set_channels(2)
        self._mp3_encoder.set_quality(2)

        self._file_path = audio_file.path
        self._file = None

    def __enter__(self):
        self._file = self._file_path.open("wb")

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._file.flush()
        self._file.close()

    def encode(self, pcm_frames):
        self._file.write(self._mp3_encoder.encode(pcm_frames))
