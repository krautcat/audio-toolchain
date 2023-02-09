
import argparse
import pathlib
import re
import sys

import mutagen
import mutagen.flac
import mutagen._vorbis

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject, GLib
Gst.init(None)

from krautcat.audio.file.audio.flac import AudioFileFLAC
from krautcat.audio.file.cuesheet import (ElementTrack as CuesheetElementTrack,
                                          ElementRoot as CuesheetElementRoot,
                                          Parser as CuesheetParser)
from krautcat.audio.metadata.flac import Metadata as MetadataFLAC
from krautcat.gstreamer import (ElementFileSink, ElementFileSource,
                                ElementFLACDecoder, ElementFLACEncoder, ElementFLACParser,
                                ElementPipeline)


class _OutputFile:
    def __init__(self, cuesheet_track: CuesheetElementTrack) -> None:
        self.file_begin = cuesheet_track.begin
        self.file_end = cuesheet_track.end

        self.metadata = MetadataFLAC(
            artist=cuesheet_track.track_artist,
            track_name=cuesheet_track.track_name,
            album=cuesheet_track.cue_root.album_artist,
            date=cuesheet_track.cue_root.album_date,
            track_number=cuesheet_track.track_number,
        )

        self.path = self.file_begin.file.path.parent / f"{cuesheet_track.track_number:02}. {cuesheet_track.track_name}.{AudioFileFLAC.EXTENSION}"


def main():
    cue_file_path = pathlib.Path(sys.argv[1]).resolve()
    flac_file_path = cue_file_path.parent
    cuesheet_info = CuesheetParser(cue_file_path).parse()

    _output_tracks = list()
    for track in cuesheet_info.tracks:
        _output_tracks.append(_OutputFile(track))

    for track in _output_tracks:
        track.metadata.total_tracks = len(_output_tracks)

    flac_file_path /= cuesheet_info.files[0].path

    Gst.debug_set_active(True)
    Gst.debug_set_default_threshold(3)
    GObject.threads_init()
    
    pipeline = ElementPipeline()

    source_file = ElementFileSource(flac_file_path)
    source_parser = ElementFLACParser()
    source_decoder = ElementFLACDecoder()
    sink_encoder = ElementFLACEncoder()
    sink_file = ElementFileSink() 

    pipeline = pipeline << source_file << source_parser << source_decoder
    pipeline = pipeline << sink_encoder << sink_file

    sink_file = source_file | source_parser | source_decoder | sink_encoder | sink_file 

    source_file.__gobject__.get_static_pad("src").set_active(True)
    for track in _output_tracks:
        pipeline.__gobject__.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                                         (track.file_begin.time * 1000 + track.file_begin.mseconds) * Gst.MSECOND)
        sink_file.location = track.path

        pipeline.state = Gst.State.PLAYING

        if track.file_end.time == 0 and track.file_end.mseconds == 0:
            pipeline.bus.timed_pop_filtered(
                Gst.CLOCK_TIME_NONE,
                Gst.MessageType.EOS
            )
            pipeline.state = Gst.State.NULL
        else:
            # clock_id = pipeline.__gobject__.get_pipeline_clock()
            # id = clock_id.new_single_shot_id((track.file_end.time * 1000 + track.file_end.mseconds) * Gst.MSECOND)
            # clk_ret, jitter = clock_id.id_wait(id)
            # print(f"Jitter: {jitter}, {(track.file_end.time * 1000 + track.file_end.mseconds) * Gst.MSECOND}")
            pipeline.bus.timed_pop_filtered(
                (track.file_begin.time * 1000 + track.file_begin.mseconds) * Gst.MSECOND,
            )
            pipeline.state = Gst.State.PAUSED

        output_audiofile = AudioFileFLAC(track.path)
        output_audiofile.metadata <<= track.metadata
        output_audiofile.save_tags() 
