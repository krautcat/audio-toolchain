import mutagen.id3
import mutagen.mp3

from . import generic as _generic
from ... import exceptions as _exceptions

class MetadataMP3(_generic.Metadata):
    def _track_name_setter_impl(self, source):
        if isinstance(source, mutagen.Tags):
            track_name_frame = source.getall("TIT2")
            if len(track_name_frame) > 0:
                self._track_name = track_name_frame[0].text[0]
            else:
                self._track_name = None

        elif isinstance(source, str):
            self._track_name = source

    def _artist_setter_impl(self, source):
        if isinstance(source, mutagen.Tags):
            artist_frame = source.getall("TPE1")
            if len(artist_frame) > 0:
                self._artist = artist_frame[0].text[0]
            else:
                self._artist = None

        elif isinstance(source, str):
            self._artist = source

    def _album_setter_impl(self, source):
        if isinstance(source, mutagen.Tags):
            album_frame = source.getall("TALB")
            if len(album_frame) > 0:
                self._album = album_frame[0].text[0]
            else:
                self._album = None 

        elif isinstance(source, str):
            self._album = source

    def _date_setter_impl(self, source):
        if isinstance(source, mutagen.Tags):
            date_frame = source.getall("TDRC")
            if len(date_frame) > 0:
                self._date = str(date_frame[0].text[0])
            else:
                self._date = None

        elif isinstance(source, str):
            self._date = source

        elif isinstance(source, int):
            self._date = str(source)

    def _track_number_setter_impl(self, source):
        if isinstance(source, mutagen.Tags):
            track_number_frame = source.getall("TRCK")
            if len(track_number_frame) > 0:
                self._track_number = str(track_number_frame[0].text[0])
            else:
                self._track_number = None

        elif isinstance(source, str):
            self._track_number = source

        elif isinstance(source, int):
            self._track_number = str(source)

    def _total_tracks_setter_impl(self, source):
        if isinstance(source, mutagen.Tags):
            total_tracks_frame = source.getall("TXXX:TOTALTRACKS")
            if len(total_tracks_frame) > 0:
                self._total_tracks = str(total_tracks_frame[0].text[0])
            else:
                self._total_tracks = None

        elif isinstance(source, str):
            self._total_tracks = source

        elif isinstance(source, int):
            self._total_tracks = str(source)

    def update(self, other_metadata):
        self._track_name = other_metadata._track_name
        self._track_number = other_metadata._track_number

        self._artist = other_metadata._artist
        self._album = other_metadata._album
        self._date = other_metadata._date

        self._total_tracks = other_metadata._total_tracks


class AudioFileMP3(_generic.AudioFile):
    EXTENSION = "mp3"
    SUFFIX = EXTENSION 
        
    def __init__(self, path, *, open=True):
        super().__init__(path, open=open)

        self.metadata = MetadataMP3(tags=self._tags)

    @property
    def file(self):
        return self._raw_file

    def _open_file(self, file_path):
        try:
            return mutagen.mp3.MP3(file_path)
        except mutagen.mp3.HeaderNotFoundError:
            return None

    def save_tags(self):
        if self._tags is None:
            if self._mutagen_file is None:
                self._mutagen_file, _ = self._open_file(self._path)
            if self._mutagen_file is None:
                raise _exceptions.MutagenOpenFileError(self._path)          
            self._mutagen_file.add_tags()
            self._tags = self._mutagen_file.tags

        self._tags.setall("TIT2", [mutagen.id3.TIT2(encoding=3, text=self.metadata.track_name)])
        self._tags["TALB"] = mutagen.id3.TALB(encoding=3, text=self.metadata.album)
        self._tags["TPE1"] = mutagen.id3.TPE1(encoding=3, text=self.metadata.artist)

        if self.metadata.track_number is not None:
            self._tags["TRCK"] = mutagen.id3.TRCK(encoding=3, text=str(self.metadata.track_number))
       
        if self.metadata.total_tracks is not None: 
            self._tags["TXXX:TOTALTRACKS"] = mutagen.id3.TXXX(
                encoding=mutagen.id3.Encoding.UTF8,
                desc="TOTALTRACKS",
                text=str(self.metadata.total_tracks)
            )

        if self.metadata.date is not None:
            self._tags["TDRC"] = mutagen.id3.TDRC(encoding=3, text=self.metadata.date)

        self._mutagen_file.save()


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
