import argparse
import concurrent
import json
import pathlib
import sys
import threading

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


class _DirectoryQueueIterator(Iterator):
    def __init__(self, queue):
        self._queue = queue

    def __iter__(self):
        return self

    def __next__(self):
        directory = self._queue.pop()

        if directory is None:
            raise StopIteration

        return directory


class DirectoryQueue(Iterable):
    def __init__(self):
        self._queue = list()

        self._done = False

        self._rlock_queue = threading.RLock()
        self._cv_queue = threading.Condition(self._rlock_queue)

        self._rlock_done = threading.RLock()

    def __iter__(self):
        return _DirectoryQueueIterator(self)

    def __len__(self):
        return len(self._queue)

    def push(self, directory):
        with self._rlock_queue:
            self._queue.append(directory)
            self._cv_queue.notify()

    def pop(self):
        with self._rlock_queue:
            if self.empty():
                if self.done is False:
                    self._cv_queue.wait()
                else:
                    return None
            return self._queue.pop()
    
    def empty(self):
        with self._rlock_queue:
            if len(self._queue) == 0:
                return True
            else:
                return False

    @property
    def done(self):
        with self._rlock_done:
            return self._done

    @done.setter
    def done(self, value):
        with self._rlock_done:
            self._done = value


class DirectoryPushWorker(threading.Thread):
    def __init__(self, queue, config, *thread_args, **thread_kwargs):
        self.directory_queue = queue

        self.config = config

        if config.command_config.library_root:
            self._consume_directories = self._library_root_handler
        else:
            self._consume_directories = self._directories_list_handler

        super().__init__(*thread_args, **thread_kwargs)

    def run(self):
        return self._consume_directories()

    def _consume_directories(self):
        pass

    def _library_root_handler(self):
        library_root = self.config.command_config.directories[0]
        
        for entry in library_root.iterdir():
            if entry.is_dir():
                self.directory_queue.push(entry)
        
        self.directory_queue.done = True

    def _directories_list_handler(self):
        for directory in self.config.command_config.directories:
            self.directory_queue.push(directory)

        self.directory_queue.done = True


class CommandBase:
    def __init__(self, config):
        self._stdout_handler = self._init_stdout_handler(config.stdout)

    def _init_stdout_handler(self, type):
        handler_klass_name = f"Stdout{type.value.capitalize()}"
        handler_klass = getattr(sys.modules[__name__], handler_klass_name, None)
       
        if handler_klass is not None:
            return handler_klass()
        else:
            return None

    def __call__(self, dir_queue, config):
        for album_path in dir_queue:
            for entry in album_path.iterdir():
                if not entry.is_file() or entry.stat().st_size == 0:
                    continue
               
                file_klass = file_class(entry)

                if file_klass is not None and hasattr(file_klass, "save_tags"):
                    file = file_klass(entry)
                    file.metadata.track_name = file._tags

                    self._command_action(file)

                    file.save_tags()
                else:
                    continue
            
            self._print_stdout(album_path)

    def _print_stdout(self, album_path):
        self._stdout_handler.print(album_path)


class CommandCapitalizeTags(CommandBase):
    def _command_action(self, file):
        artist = file.metadata.artist
        file.metadata.artist = " ".join([w.capitalize() for w in artist.split(" ")])
        
        track_name = file.metadata.track_name
        file.metadata.track_name = " ".join([w.capitalize() for w in track_name.split(" ")])


class DateToYearWorker:
    def __init__(self, album_path, config):
        self.album_path = album_path
        self.config = config

    def __call__(self):
        for entry in self.album_path.iterdir():
            if not entry.is_file() or entry.stat().st_size == 0:
                continue
            
            file_klass = file_class(entry)

            if file_klass is not None and hasattr(file_klass, "save_tags"):
                file = file_klass(entry)
                file.metadata.track_name = file._tags

                date = file.metadata.date
                file.metadata.date = date.split("-")[0]
                print(date)

                file.save_tags()
            else:
                continue
        
        self._print_stdout(album_path)


class CanonicalizeArtistNameWorker:
    def __init__(self, album_path, config):
        self.album_path = album_path
        self.config = config

    def __call__(self):
        music_files = list()

        for entry in self.album_path.iterdir():
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


class Command(CommandBase):
    def __call__(self, worker_class, dir_queue, config):
        pass

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
        capitalize_parser.add_argument("album-root", action="store",
                                       type=pathlib.Path,
                                       nargs="+",
                                       help="Path to album")

        date_to_year_parser = subparsers.add_parser("date-to-year")
        date_to_year_parser.add_argument("--library-root", action="store_true",
                                         help="Supply root as library root")
        date_to_year_parser.add_argument("ditrectory", action="store",
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


def main():
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

    dir_queue = DirectoryQueue()

    directory_push_worker = DirectoryPushWorker(dir_queue, config)
    directory_push_worker.start()

    worker_class = get_worker_by_name(cli_args.command)

    pool = ThreadPoolExecutor(max_workers=10)

    future_to_album_path = {
        pool.submit(worker_class(album_path, config)): album_path 
        for album_path in dir_queue
    }

    concurrent.futures.as_completed(future_to_album_path)

    directory_push_worker.join()
