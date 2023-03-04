import argparse
import asyncio
import concurrent
import concurrent.futures
import json
import pathlib
import sys

from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from enum import Enum

from krautcat.audio.file.audio import *
from krautcat.audio.file.mime import file_class
from krautcat.audio.metadata.tags import TagFactory
from krautcat.audio.musicbrainz import MusicBrainzAPI


class StdinType(Enum):
    JSON = "json"
    PLAIN = "plain"
    NONE = "none"

    def __str__(self):
        return self.value


class StdinHandler:
    def readline(self):
        pass


class StdinHandlerNone(StdinHandler):
    def readline(self):
        return None


class StdinHandlerPlain(StdinHandler):
    def readline(self):
        directory = sys.stdin.readline()
        if directory == "":
            return None
        
        return directory.rstrip("\n")


class StdinHandlerJson(StdinHandler):
    def readline(self):
        directory = sys.stdin.readline()
        if directory == "":
            return None
            
        obj = json.loads(directory.rstrip("\n"))

        return obj["directory"]


class StdoutType(Enum):
    JSON = "json"
    PLAIN = "plain"
    NONE = "none"

    def __str__(self):
        return self.value


class StdoutHandler:
    def __init__(self):
        pass

    def print(self, obj_string):
        if not obj_string.endswith("\n"):
            obj_string += "\n"

        sys.stdout.write(obj_string)


class StdoutJson(StdoutHandler):
    def print(self, album_path):
        super().print(json.dumps({"directory": str(album_path)}))


class StdoutPlain(StdoutHandler):
    def print(self, album_path):
        super().print(str(album_path))


class StdoutNone(StdoutHandler):
    def print(self, album_path):
        pass


class CapitalizeTagsWorker:
    def __init__(self, config):
        self._stdout_handler = self._init_stdout_handler(config.stdout)

    def _init_stdout_handler(self, type):
        handler_klass_name = f"Stdout{type.value.capitalize()}"
        handler_klass = getattr(sys.modules[__name__], handler_klass_name, None)
       
        if handler_klass is not None:
            return handler_klass()
        else:
            return None

    def __call__(self, album_path):
        for entry in album_path.iterdir():
            if entry.is_dir():
                self(entry)

            if not entry.is_file() or entry.stat().st_size == 0:
                continue
           
            file_klass = file_class(entry)

            if file_klass is not None and hasattr(file_klass, "save_tags"):
                file = file_klass(entry)
            else:
                continue

            artist = file.metadata.artist
            file.metadata.artist = " ".join([w.capitalize() for w in artist.split(" ")])
            
            track_name = file.metadata.track_name
            file.metadata.track_name = " ".join([w.capitalize() for w in track_name.split(" ")])

            self._print_stdout(f"Saving tags for '{entry}' file")
            file.save_tags()
        
        self._print_stdout(album_path)

    def _print_stdout(self, album_path):
        self._stdout_handler.print(album_path)


class DateToYearWorker:
    def __init__(self, config):
        self.config = config

    def __call__(self, album_path):
        for entry in album_path.iterdir():
            if entry.is_dir():
                self(entry)

            if not entry.is_file() or entry.stat().st_size == 0:
                continue
            
            file_klass = file_class(entry)

            if file_klass is not None and hasattr(file_klass, "save_tags"):
                file = file_klass(entry)
                
                date = file.metadata.date
                file.metadata.date = date.year
                print(date)

                file.save_tags()
            else:
                continue
        
        print(album_path, file=sys.stderr)


class CanonicalizeArtistNameWorker:
    def __init__(self, config):
        self.config = config

    def __call__(self, album_path):
        music_files = list()

        for entry in album_path.iterdir():
            if entry.is_dir():
                self(entry)

            if not entry.is_file() or entry.stat().st_size == 0:
                continue
            
            file_klass = file_class(entry)
            if file_klass is None or not hasattr(file_klass, "save_tags"):
                continue

            file = file_klass(entry)
            music_files.append(file)
            
            file.metadata.track_name = file._tags
            file.metadata.artist = file._tags
            file.metadata.album = file._tags
            file.metadata.date = file._tags

            mb_api = MusicBrainzAPI()

            artist = mb_api.get_artist_of_album(file.metadata.artist,
                                                file.metadata.album,
                                                file.metadata.date,
                                                cache=True)

            if artist != file.metadata.artist:
                print("Renamed artist '{}' to '{}' in file '{}'".format(
                    file.metadata.artist, artist, file.path
                ))
                file.metadata.artist = artist
                file.save_tags()


class ConfigurationCapitalizeTags:
    def __init__(self, cli_args, config_file=None):
        self.directories = vars(cli_args)["album-root"]
        self.library_root = cli_args.library_root


class ConfigurationDateToYear:
    def __init__(self, cli_args, config_file=None):
        self.directories = cli_args.directory
        self.library_root = cli_args.library_root


class ConfigurationCanonicalizeArtistName:
    def __init__(self, cli_args, config_file=None):
        self.directories = cli_args.directory
        self.library_root = cli_args.library_root

    def validate(self):
        return True
        

class Configuration:
    def __init__(self, cli_args, config_file=None):
        self.stdout = cli_args.stdout

        command_config_class = self.get_command_config_class(cli_args.command)
        if command_config_class is not None:
            self.command_config = command_config_class(cli_args, config_file)
        else:
            self.command_config = None

    @staticmethod
    def get_command_config_class(command_name):
        command_name_prepared = "".join([w.capitalize() for w in command_name.split("-")])         
        command_config_class_name = f"Configuration{command_name_prepared}"
        
        klass = getattr(sys.modules[__name__], command_config_class_name, None)

        return klass

    def validate(self):
        return self.command_config.validate()


class Argparser:
    def __init__(self):
        argparser = self.argparser = argparse.ArgumentParser(
                description="Tagger toolchain for krautcat's needs")

        argparser.add_argument("--stdout", action="store",
                               type=StdoutType,
                               choices=list(StdoutType),
                               default=StdoutType.NONE,
                               help="Stdout output format")

        subparsers = argparser.add_subparsers(title="Commands", dest="command")

        capitalize_parser = subparsers.add_parser("capitalize-tags")
        capitalize_parser.add_argument("--library-root", action="store_true",
                                       help="Supply root as library root")
        capitalize_parser.add_argument("album-root", action="store",
                                       type=pathlib.Path,
                                       nargs="+",
                                       help="Path to album")

        date_to_year_parser = subparsers.add_parser("date-to-year")
        date_to_year_parser.add_argument("--library-root", action="store_true",
                                         help="Supply root as library root")
        date_to_year_parser.add_argument("directory", action="store",
                                         type=pathlib.Path,
                                         nargs="+",
                                         help="Path to album")

        canonicalize_artist_name_parser = subparsers.add_parser("canonicalize-artist-name")
        canonicalize_artist_name_parser.add_argument("-t", "--tags", action="store",
                                                     type=TagFactory,
                                                     nargs="+",
                                                     help="Tags to canonicalize")
        canonicalize_artist_name_parser.add_argument("--library-root", action="store_true",
                                                     help="Supply root as library root")
        canonicalize_artist_name_parser.add_argument("directory", action="store",
                                                      type=pathlib.Path,
                                                      nargs="+",
                                                      help="Path to directory")


    def parse(self, args):
        return self.argparser.parse_args(args[1:])

    def help(self):
        return self.argparser.format_help()


def get_worker_by_name(command_name):
    command_name_prepared = "".join([w.capitalize() for w in command_name.split("-")])

    command_class_name = f"{command_name_prepared}Worker"

    return getattr(sys.modules[__name__], command_class_name, None)


async def async_main(config: Configuration,
                     cli_args: argparse.Namespace) -> int:
    if config.command_config.library_root:
        directories = [
            e
            for e in config.command_config.directories[0].iterdir()
            if e.is_dir()
        ]
    else:
        directories = config.command_config.directories


    worker = get_worker_by_name(cli_args.command)

    if worker is None:
        raise ValueError(f"Unknown command '{cli_args.command}'")

    loop = asyncio.get_event_loop()
    tasks = list()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        for directory in directories:
            tasks.append(loop.run_in_executor(pool,
                                              worker(config),
                                              directory))
        completed, pending = await asyncio.wait([*tasks])
    await asyncio.gather(*pending)
    loop.close()

    return 0


def main() -> int:
    args = sys.argv
    argparser = Argparser()
    cli_args = argparser.parse(args)

    config = Configuration(cli_args)
    if not config.validate:
        print(argparser.help())
        exit()

    if cli_args.command is None:
        print("Command must be supplied!")
        print(argparser.help())
        exit(1)

    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(asyncio.ensure_future(async_main(config, cli_args)))
    loop.close()
    
    return result
