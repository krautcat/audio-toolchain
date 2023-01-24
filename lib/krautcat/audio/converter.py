import argparse
import pathlib
import sys

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject, GLib

from krautcat.audio.file.audio import open_audio_file, AudioFileMP3, AudioFileFLAC
from krautcat.audio.file.audio.mp3 import MP3Encoder
from krautcat.audio.fs import FilesystemGeneric
from krautcat.audio.metadata import TagStatistics


class Converter:
    def __init__(self, cli_args):
        self._source_directory = cli_args.source_directory
      
        self._output_basedir = pathlib.Path("/tmp")
        self._output_dirname_format = "{artist} — {date} — {album}"
        self._output_filename_format = "{track}. {name}.{extension}"

    def __call__(self):
        audio_files = []
        stats = TagStatistics()

        for entry in self._source_directory.iterdir():
            if not entry.is_file() or entry.stat().st_size == 0:
                continue

            file = open_audio_file(entry)
            
            if file is None:
                continue
        
            stats.update(file.metadata)
            audio_files.append(file)

        output_dir = self._output_basedir / self._output_dirname_format.format(
            artist = stats.artist,
            date = stats.date,
            album = stats.album
        )

        self._convert_files(audio_files, output_dir)

    def _convert_files(self, files, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
       
        total_tracks = len(files) 

        Gst.init(None)

        Gst.debug_set_active(True)
        Gst.debug_set_default_threshold(3)
        GObject.threads_init()

        for file in files:
            output_filename = output_dir / self._output_filename_format.format(
                track=file.metadata.track_number,
                name=FilesystemGeneric.escape_filename(str(file.metadata.track_name)),
                extension=AudioFileMP3.EXTENSION
            )
            
            pipeline = Gst.ElementFactory.make("pipeline", None)          

            source_file = Gst.ElementFactory.make("filesrc", None)
            source_file.set_property("location", str(file.path))
            
            source_decoder = file.gst_decoder
            
            audioconvert = Gst.ElementFactory.make("audioconvert", None)
            
            mp3_stream = Gst.ElementFactory.make("lamemp3enc", None)
            mp3_stream.set_property("cbr", True)
            mp3_stream.set_property("bitrate", 320)

            mp3_file = Gst.ElementFactory.make("filesink", None)
            mp3_file.set_property("location", str(output_filename))

            pipeline.add(source_file, source_decoder, audioconvert, mp3_stream,
                         mp3_file)
            source_file.link(source_decoder)
            source_decoder.link(audioconvert)
            audioconvert.link(mp3_stream)
            mp3_stream.link(mp3_file)
            pipeline.set_state(Gst.State.PLAYING)

            loop = GLib.MainLoop()
            loop.run()

            pipeline.set_state(Gst.State.NULL)
            pipeline.get_state(Gst.CLOCK_TIME_NONE)

            mp3_file.metadata <<= file.metadata
            if mp3_file.metadata.total_tracks is None:
                mp3_file.metadata.total_tracks = total_tracks

            mp3_file.save_tags()
 

class Argparser:
    def __init__(self):
        argparser = self._argparser = argparse.ArgumentParser()

        argparser.add_argument("source_directory", action="store",
                               type=pathlib.Path, help="Path to directory with album")

    def parse(self, args):
        return self._argparser.parse_args(args)


def main():
    argparser = Argparser()

    cli_args = argparser.parse(sys.argv[1:])

    command = Converter(cli_args)
    status = command()
