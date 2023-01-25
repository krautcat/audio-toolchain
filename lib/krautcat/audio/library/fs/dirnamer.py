#!/usr/bin/env python3

import argparse
import asyncio
import concurrent
import concurrent.futures
import json
import pathlib
import re
import shutil
import string
import sys
import threading

from collections.abc import Iterable, Iterator
from enum import Enum
from pathlib import Path
from typing import Tuple, Callable, Any, Optional, Union, Awaitable, Pattern, ClassVar

if sys.version_info >= (3, 8):
    from typing import Protocol
else:
    from typing_extensions import Protocol

import puremagic
import puremagic.main
import mutagen.mp3
import mutagen.flac

import krautcat.audio.fs

from krautcat.audio.exceptions import MutagenOpenFileError
from krautcat.audio.file.audio import *
from krautcat.audio.file.mime import file_class
from krautcat.ui.tui import TextMessageWithSpinner, UI as TUI


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

        if config.command_config.stdin is not StdinType.NONE:
            handler_klass_name = f"StdinHandler{config.command_config.stdin.value.capitalize()}"
            handler_klass = getattr(sys.modules[__name__], handler_klass_name, None)

            if handler_klass is not None:
                self._consume_directories = self._stdin_handler
                self._stdin_handler_obj = handler_klass()
        else:
            if config.command_config.library_root:
                self._consume_directories = self._library_root_handler
            else:
                self._consume_directories = self._directories_list_handler

        super().__init__(*thread_args, **thread_kwargs)

    def run(self):
        return self._consume_directories()

    def _consume_directories(self):
        pass

    def _stdin_handler(self):
        directory = self._stdin_handler_obj.readline()
        while directory is not None: 
            self.directory_queue.push(Path(directory))
            directory = self._stdin_handler_obj.readline()

        self.directory_queue.done = True

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


class _DirectoriesIterator:
    def __init__(self, dirs):
        self.directories = dirs

        self._len = len(self.directories._directories)
        self._cursor = 0

    def __iter__(self):
        return self
        
    def __next__(self):
        if self._cursor < self._len:
            value = self.directories._directories[self._cursor]
            self._cursor += 1
            return value
        else:
            raise StopIteration


class Directories:
    def __init__(self, config):
        if config.command_config.library_root:
            self._directories = [
                e
                for e in config.command_config.directories[0].iterdir()
                if e.is_dir()
            ]
        else:
            self._directories = config.command_config.directories

    def __iter__(self):
        return _DirectoriesIterator(self)


class RenameAlbumDirWorker:
    def __init__(self, album_path, config):
        self.command_config = config.command_config
        self.common_config = config

        self.album_path = album_path 

    def __call__(self, *args, **kwargs):
        self._rename_directory(self.album_path)
        return self.album_path

    def _rename_directory(self, directory):
        directory_filesystem = krautcat.audio.fs.get_fs_class(directory)

        if not directory.is_dir():
            return 

        name = self._get_name_from_dir_content(directory, directory_filesystem)
        old_name = directory.name
        target_name = name

        if target_name is not None and target_name != directory.name:
            count = 2
            renamed = False
            while not renamed:
                try:
                    new_directory_name = self.command_config.directories[0] / target_name
                    new_directory_name.mkdir(parents=True, exist_ok=True)
                    for entry in directory.iterdir():
                        entry_name = entry.name
                        shutil.move(directory / entry_name, new_directory_name / entry_name) 
                    renamed = True
                    if target_name != old_name:
                        shutil.rmtree(old_name)
                except OSError as e:
                    target_name = f"{name} ({count})"
                    count += 1


    def _get_name_from_dir_content(self, album_dir: Path,
                                   directory_filesystem: krautcat.audio.fs.FilesystemGeneric):
        stats = TagStatistics() 

        audio_files = 0
        for entry in album_dir.iterdir():
            if entry.is_dir():
                self._rename_directory(entry)

            if not entry.is_file() or entry.stat().st_size == 0:
                continue
            
            file_kls = file_class(entry)

            if file_kls is None:
                continue

            try:
                file = file_kls(entry)
            except MutagenOpenFileError:
                continue

            audio_files += 1 
            stats.update(file.metadata)

        if audio_files == 0:
            return None

        artist = stats.artist
        album = stats.album
        date = stats.date

        format_kwargs = {}
        if "artist" in self.command_config.dirname_format_fields:
            if artist is None:
                artist = "None"
            format_kwargs["artist"] = directory_filesystem.escape_filename(artist)
        if "album" in self.command_config.dirname_format_fields:
            if album is None:
                album = "None"
            format_kwargs["album"] = directory_filesystem.escape_filename(album)
        if "year" in self.command_config.dirname_format_fields:
            if date is None:
                date = None
            format_kwargs["year"] = date

        return self.command_config.dirname_format.format(**format_kwargs)


class RenameFilesWorker:
    def __init__(self, album_path, config):
        self.command_config = config.command_config
        self.common_config = config

        self.album_path = album_path 

    def __call__(self):
        self._rename_files(self.album_path)

    def _rename_files(self, album_path):
        directory_filesystem = krautcat.audio.fs.get_fs_class(album_path)

        if not album_path.is_dir():
            return 

        for entry in album_path.iterdir():
            if not entry.is_file() or entry.stat().st_size == 0:
                print("Not a file")
                continue
            
            file_kls = file_class(entry)

            if file_kls is None:
                print(f"Not found audiofile class for {entry}")
                continue 

            file = file_kls(entry)

            format_kwargs = {}
            if "artist" in self.command_config.dirname_format_fields:
                format_kwargs["artist"] = file.metadata.artist
            if "album" in self.command_config.dirname_format_fields:
                format_kwargs["album"] = file.metadata.album
            if "year" in self.command_config.dirname_format_fields:
                format_kwargs["year"] = file.metadata.date
            if "track_number" in self.command_config.dirname_format_fields:
                if file.metadata.track_number is not None:
                    format_kwargs["track_number"] = file.metadata.track_number.split("/")[0]
                else:
                    format_kwargs["track_number"] = ""
            if "track_name" in self.command_config.dirname_format_fields:
                format_kwargs["track_name"] = file.metadata.track_name

            print(file.extension)
            new_name = self.command_config.dirname_format.format(**format_kwargs) + "." + file.extension

            name = directory_filesystem.escape_filename(new_name)

            if name == entry.name:
                continue
            else:
                print(f"Renamed {entry} to {name}")

            entry.rename(entry.parent / name)



class ConfigurationRenameAlbumDir:
    def __init__(self, cli_args, config_file=None):
        self.directories = cli_args.directory
        self.library_root = cli_args.library_root

        self.stdin = cli_args.stdin

        self.dirname_format_fields = set()
        if cli_args.format is not None and self._validate_dirname_format(cli_args.format):
            self.dirname_format = cli_args.format
        else:
            self.dirname_format = "{artist} — {year} — {album}"
            self.dirname_format_fields.update(["artist", "year", "album"])

    def _validate_dirname_format(self, format_str):
        allowed_format_name = set(["artist", "year", "album"]) 
    
        fmtter = string.Formatter()
        for _, field_name, _, _ in fmtter.parse(format_str):
            if field_name in allowed_format_name:
                self.dirname_format_fields.add(field_name)
            else:
                return False

        return True

    def validate(self, cli_args):
        if cli_args.stdin is StdinType.NONE and len(self.directories) == 0:
            return False
        else:
            return True

    
class ConfigurationRenameFiles:
    def __init__(self, cli_args, config_file=None):
        self.directories = cli_args.directory
        self.library_root = cli_args.library_root

        self.stdin = cli_args.stdin

        self.dirname_format_fields = set()
        if cli_args.format is not None and self._validate_dirname_format(cli_args.format):
            self.dirname_format = cli_args.format
        else:
            self.dirname_format = "{track_number}. {track_name}"
            self.dirname_format_fields.update(["track_number", "track_name"])

    def _validate_dirname_format(self, format_str):
        allowed_format_name = set(["artist", "year", "album", "track_number", "track_name"]) 
        
        for literal_text, field_name, format_spec, conversion in string.Formatter.parse(format_str):
            if field_name in allowed_format_name:
                self.dirname_format_fields.add(field_name)
            else:
                return False

        return True

    def validate(self, cli_args):
        if cli_args.stdin is StdinType.NONE and len(self.directories) == 0:
            return False
        else:
            return True
        

class Configuration:
    def __init__(self, cli_args, config_file=None):
        self.no_escaping = cli_args.no_escaping

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

    def validate(self, cli_args):
        return self.command_config.validate(cli_args)


class Argparser:
    def __init__(self):
        argparser =  self.argparser = argparse.ArgumentParser(
               description="Tagger toolchain for krautcat's needs")
        
        argparser.add_argument("--no-escaping",
                               action="store_true",
                               help="Escape paths")
        argparser.add_argument("-u", "--ui",
                               type=str,
                               choices=["tui", "no-ui"],
                               help="UI type",
                               default="tui")

        subparsers = argparser.add_subparsers(title="Commands", dest="command")

        rename_album_dir_parser = subparsers.add_parser("rename-album-dir")
        rename_album_dir_parser.add_argument("--stdin", action="store",
                                             type=StdinType,
                                             choices=list(StdinType),
                                             default=StdinType.NONE,
                                             help="Stdin input type")
        rename_album_dir_parser.add_argument("--library-root", action="store_true",
                                             help="Supply root as library root")
        rename_album_dir_parser.add_argument("directory", action="store",
                                             type=Path,
                                             nargs="*",
                                             help="Directory with album or library root directory")
        rename_album_dir_parser.add_argument("-f", "--format", action="store",
                                             default=None, help="Format for naming albums'"
                                             " directories")

        rename_files_parser = subparsers.add_parser("rename-files")
        rename_files_parser.add_argument("--stdin", action="store",
                                         type=StdinType,
                                         choices=list(StdinType),
                                         default=StdinType.NONE,
                                         help="Stdin input type")
        rename_files_parser.add_argument("--library-root", action="store_true",
                                         help="Supply root as library root")
        rename_files_parser.add_argument("directory", action="store",
                                         type=Path,
                                         nargs="*",
                                         help="Directory with album or library root directory")
        rename_files_parser.add_argument("-f", "--format", action="store",
                                         default=None, help="Format for naming albums'"
                                         " directories")
    
    def parse(self, args):
        return self.argparser.parse_args(args[1:])

    def help(self):
        return self.argparser.format_help()


def get_worker_by_name(command_name: str, ui: str) -> Any:
    command_name_prepared = "".join([ui.capitalize()] +
                                    [w.capitalize() for w in command_name.split("-")])         
    command_class_name = f"{command_name_prepared}Worker"
    
    klass = getattr(sys.modules[__name__], command_class_name, None)

    return klass


class TuiRenameAlbumDirWorker:
    def __init__(self, directory: pathlib.Path,
                 config: Configuration, ui: TUI) -> None:
        self.directory = directory
        self._config = config
        self._ui = ui
    
    def __call__(self) -> pathlib.Path:
        widget_key = self._ui.view << TextMessageWithSpinner(f"Scanning {self.directory}...",
                                                           "Scanning done")       
        worker = RenameAlbumDirWorker(self.directory, self._config)
        album_path = worker()
        
        if album_path == self.directory:
            done_msg = f"Directory '{album_path}' didn't change"
        else:
            done_msg = f"Renamed {self.directory} to {album_path}"
        self._ui.view[widget_key]._msg_done = done_msg

        self._ui.view[widget_key].done() 
        del self._ui.view[widget_key]

        return album_path


def classic_unix_ui_main(config: Configuration, ns: argparse.Namespace) -> int:
    pass


async def tui_main(config: Configuration, ns: argparse.Namespace) -> int: 
    worker = get_worker_by_name(ns.command, ns.ui)
    loop = asyncio.get_event_loop()

    tasks = list()

    async with TUI() as ui:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            for directory in Directories(config):
                tasks.append(loop.run_in_executor(pool,
                                                  worker(directory, config, ui)))
            ui_task = loop.create_task(ui.process_messages())
            completed, pending = await asyncio.wait([*tasks])
    await asyncio.gather(*pending)
    ui_task.cancel()

    return 0


def main():
    args = sys.argv
    argparser = Argparser()

    namespace = argparser.parse(args)

    config = Configuration(namespace)
    if not config.validate(namespace):
        print(argparser.help())
        exit()

    if namespace.command is None:
        print("Command must be supplied!")
        print(argparser.help())
        exit()

    if namespace.ui == "tui":
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(asyncio.ensure_future(tui_main(config,
                                                                        namespace)))
        loop.close()
        return result
    elif namespace.ui == "no-ui":
        return classic_unix_ui(config)
