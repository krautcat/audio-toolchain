import argparse
import asyncio
import concurrent.futures
import os
import pathlib
import sys

import asyncio_glib
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject, GLib
Gst.init(None)

from krautcat.audio.file.audio import open_audio_file, AudioFileMP3, AudioFileFLAC
from krautcat.audio.file.audio.mp3 import MP3Encoder
from krautcat.audio.fs import FilesystemGeneric
from krautcat.gstreamer import (ElementAudioConvert, ElementAudioParse, ElementAudioResample,
                                ElementFileSink, ElementFileSource,
                                ElementFLACDecoder, ElementFLACParser,
                                ElementPipeline,
                                ElementMP3Encoder)
                                      

class TagStatistics:
    def __init__(self):
        self._artist = {}
        self._album = {}
        self._date = {}

    def update(self, metadata):
        self._update_artist(metadata.artist)
        self._update_album(metadata.album)
        self._update_date(metadata.date)

    def _update_artist(self, tag_value):
        if tag_value in self._artist:
            self._artist[tag_value] += 1
        else:
            self._artist[tag_value] = 1

    def _update_album(self, tag_value):
        if tag_value in self._album:
            self._album[tag_value] += 1
        else:
            self._album[tag_value] = 1

    def _update_date(self, tag_value):
        if tag_value in self._date:
            self._date[tag_value] += 1
        else:
            self._date[tag_value] = 1

    @property
    def artist(self):
        if len(self._artist) == 0:
            return None
        elif len(self._artist) == 1:
            for artist, _ in self._artist.items():
                return artist
        elif len(self._artist) > 1:
            return "VA"

    @property
    def album(self):
        if len(self._album) == 0:
            return None
        else:
            return max(self._album, key=self._album.get)

    @property
    def date(self):
        if len(self._date) == 0:
            return None
        else:
            return max(self._date, key=self._date.get)


class Converter:
    def __init__(self, cli_args):
        self._source_directory = cli_args.source_directory
      
        self._output_basedir = pathlib.Path("/tmp")
        self._output_dirname_format = "{artist} — {date} — {album}"
        self._output_filename_format = "{track:02}. {name}.{extension}"

    async def __call__(self):
        audio_files = []
        stats = TagStatistics()

        for entry in self._source_directory.iterdir():
            if not entry.is_file() or entry.stat().st_size == 0:
                continue

            file = open_audio_file(entry)
            
            if file is None:
                continue
           
            file.load_tags()   
            stats.update(file.metadata)
            audio_files.append(file)

        output_dir = self._output_basedir / self._output_dirname_format.format(
            artist = stats.artist,
            date = stats.date,
            album = stats.album
        )

        await self._convert_files(audio_files, output_dir)

    async def _convert_files(self, files, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
       
        total_tracks = len(files) 

        tasks = list()             
        with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() * 2) as pool:
            for file in files:
                tasks.append(asyncio.get_event_loop().run_in_executor(pool,
                                                                      self._convert_file,
                                                                      file,
                                                                      output_dir,
                                                                      total_tracks))
        await asyncio.wait(tasks)
        return None
            

    def _convert_file(self, file, output_dir, total_tracks):
        output_filename = output_dir / self._output_filename_format.format(
            track=file.metadata.track_number,
            name=FilesystemGeneric.escape_filename(str(file.metadata.track_name)),
            extension=AudioFileMP3.EXTENSION
        )
        
        pipeline = ElementPipeline()

        source_file = ElementFileSource(file.path)
        source_parser = file.gst_parser()
        source_decoder = file.gst_decoder()
       
        audioconvert = ElementAudioConvert()
        audioresample = ElementAudioResample(10)

        mp3_stream = ElementMP3Encoder(ElementMP3Encoder.Bitrate.CBR, bitrate=320)        

        sink_file = ElementFileSink(output_filename) 

        pipeline = pipeline << source_file << source_parser << source_decoder
        pipeline = pipeline << audioconvert << audioresample << mp3_stream << sink_file

        audioconvert = source_file | source_parser | source_decoder | audioconvert 
        sink_file = audioconvert | audioresample | mp3_stream | sink_file
      
        pipeline.state = Gst.State.PLAYING

        pipeline.bus.timed_pop_filtered(
            Gst.CLOCK_TIME_NONE,
            Gst.MessageType.ERROR | Gst.MessageType.EOS
        )
        pipeline.state = Gst.State.NULL

        mp3_file = AudioFileMP3(output_filename)
        
        mp3_file.load_tags()
        mp3_file.metadata <<= file.metadata
        if mp3_file.metadata.total_tracks is None or mp3_file.metadata.total_tracks == 0:
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

    Gst.debug_set_active(True)
    Gst.debug_set_default_threshold(3)
    GObject.threads_init()
    asyncio.set_event_loop_policy(asyncio_glib.GLibEventLoopPolicy())
    
    command = Converter(cli_args)
    status = asyncio.get_event_loop().run_until_complete(command())
