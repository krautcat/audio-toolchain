
import argparse
import re
import sys

from pathlib import Path

import audiotools
import mutagen
import mutagen.flac
import mutagen._vorbis

import krautcat.fs

class Filesystem:
    @staticmethod
    def escape(string):
        replacements = [
            (re.compile(r"[/:]"), r"_"),
            (re.compile(r"[?]"), r"!"),
        ]

        
        for pat, repl in replacements:
            string = re.sub(pat, repl, string)

        return string


class Metadata:
    def __init__(self):
        self.artist = None
        self.album_name = None
        self.track_name = None

        self.date = None

        self.track_number = None
        self.total_tracks = None

    @classmethod
    def from_cuesheet(cls, cuesheet_info):
        self = cls()

        self.track_number = cuesheet_info.track_number
        self.total_tracks = cuesheet_info.track_total

        self.track_name = cuesheet_info.track_name
        self.album_name = cuesheet_info.album_name
        self.artist = cuesheet_info.artist_name

        self.date = cuesheet_info.year

        return self

    def fill_tags(self, tags):
        if isinstance(tags, mutagen._vorbis.VCommentDict):
            tags["TITLE"] = self.track_name
            tags["ALBUM"] = self.album_name
            tags["ARTIST"] = self.artist

            tags["TRACKNUMBER"] = str(self.track_number)
            tags["TRACKTOTAL"] = str(self.total_tracks)

            if self.date is not None:
                tags["DATE"] = self.date


class Outputfile:
    def __init__(self, metadata, *, directory=Path.cwd()):
        self.metadata = metadata

        self.name_format = "{{track_number:0{}d}}. {{track_name}}.flac"

        self._directory = directory
        self._filesystem = krautcat.fs.get_fs_class(self._directory)

    @property
    def name(self):
        fmt_str = self.name_format.format(len(str(self.metadata.total_tracks)) + 1)
        unescaped_name = fmt_str.format(track_number=self.metadata.track_number,
                                        track_name=self.metadata.track_name)

        return self._filesystem.escape_filename(unescaped_name)

    @property
    def path(self):
        return self._directory / self.name

    def write_metadata(self):
        flac_file = mutagen.flac.FLAC(self.path)

        try:
            flac_file.add_tags()
        except mutagen.flac.FLACVorbisError:
            pass

        self.metadata.fill_tags(flac_file.tags)

        flac_file.save()


class AudiofileInfo:
    def __init__(self, audio_file):
        if not isinstance(audio_file, str):
            audio_file = str(audio_file)

        self.path = Path(audio_file)

        self.audio_file = audiotools.open(audio_file)

        self.size = self.audio_file.seconds_length()

        self.bits_per_sample = self.audio_file.bits_per_sample()
        self.samples_per_second = self.audio_file.sample_rate()

        self.metadata = mutagen.flac.FLAC(self.path)


class CuesheetInfo:
    def __init__(self, cue_file):
        if not isinstance(cue_file, str):
            cue_file = str(cue_file)

        self.path = Path(cue_file)

        self.cuesheet = audiotools.read_sheet(cue_file)

        self.offsets = [
                self.cuesheet.track_offset(t)
                for t in self.cuesheet.track_numbers()
            ]
        self.lengths = [
                self.cuesheet.track_length(t)
                for t in self.cuesheet.track_numbers()
            ]

        self.total_tracks = len(self.lengths)

    def last_track_length_fix(self, audiofile_info):
        if self.lengths[-1] is None:
            # Last track length unknown, so eunsure there's enough room
            # based on the total size of the source.
            last_track_size = (audiofile_info.size
                               - sum(self.lengths[0:-1])
                               - self.cuesheet.pre_gap())

            if last_track_size >= 0:
                self.lengths.pop()
                self.lengths.append(last_track_size)
            else:
                raise ValueError

        else:
            # Last track length is known, so ensure the sizeof all lengths
            #aand the pre-gap is the same size as the source.
            if (self.cuesheet.pre_gap() + sum(self.lengths)) != audiofile_info.size:
                raise ValueError

    @property
    def metadata(self):
        return [ track.get_metadata() for track in self.cuesheet ]


def pcm_reader_progress(current, total):
    print("Progress {}/{}".format(current, total))


def split_file(source_audiofile, audiofile_info, length, offset, file, metadata=None):
    pcmreader = source_audiofile.to_pcm()

    print(length, offset)

    pcm_frames_offset = int(offset * audiofile_info.samples_per_second)
    pcm_frames_total = int(length * audiofile_info.samples_per_second)

    # if PCMReader has seek()
    # use it to reduce the amount of frames to skip
    if hasattr(pcmreader, "seek") and callable(pcmreader.seek):
        pcm_frames_offset -= pcmreader.seek(pcm_frames_offset)

    destination_audiofile = audiotools.FlacAudio.from_pcm(
        str(file.path),
        audiotools.PCMReaderWindow(pcmreader,
                                   pcm_frames_offset,
                                   pcm_frames_total),
        source_audiofile.COMPRESSION_MODES[4],
        pcm_frames_total)

    if metadata is not None:
        destination_audiofile.set_metadata(metadata)


def main():
    audio_file = AudiofileInfo(sys.argv[1])
    cuesheet_info = CuesheetInfo(sys.argv[2])

    cuesheet_info.last_track_length_fix(audio_file)

    output_files_metadata = [
            Metadata.from_cuesheet(t.get_metadata())
            for t in cuesheet_info.cuesheet
        ]
   
    # Trying to set album name if it was not set via cuesheet.
    for mdata in output_files_metadata:
        if mdata.album_name is None:
            mdata.album_name = audio_file.metadata["album"]
        if mdata.artist is None:
            mdata.artist = audio_file.metadata["artist"]


    for i in range(0, len(output_files_metadata)):
        mdata = output_files_metadata[i]
        
        if mdata.total_tracks is None:
            mdata.total_tracks = cuesheet_info.total_tracks
       
        if mdata.track_number is None:
            mdata.track_number = i + 1


    output_files = [
        Outputfile(metadata, directory=audio_file.path.parent)
        for metadata in output_files_metadata
    ]

    for length, offset, file, metadata in zip(
            cuesheet_info.lengths,
            cuesheet_info.offsets,
            output_files,
            output_files_metadata
        ):
        split_file(audio_file.audio_file, audio_file,
                   length, offset,
                   file)

        file.write_metadata()
