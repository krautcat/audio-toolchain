import math
import pathlib

from typing import List, Optional, Union

from krautcat.audio.metadata.types import Date


class ParserError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message


class TrackBounds:
    def __init__(self) -> None:
        self.file = ElementFile()
        self.time = 0 
        self.mseconds = 0
        self.frames = 0

    def __str__(self) -> str:
        minutes = self.time // 60
        seconds = self.time % 60
        
        return f"{minutes}:{seconds}:{self.mseconds}"


class ElementBase:
    def __init__(self, tokens: List[str], parent: "ElementBase") -> None:
        self._parent = parent
        self._tokens = tokens


class ElementFile(ElementBase):
    def __init__(self) -> None:
        self.path: Optional[pathlib.Path] = None
        self.format: Optional[str] = None

    def __str__(self):
        return str(self.path)

 
class ElementTrack(ElementBase):
    def __init__(self, root_element: "ElementRoot") -> None:
        self.track_number = 0
        self.track_artist = "None"
        self.track_name = "None"
    
        self.begin = TrackBounds()
        self.end = TrackBounds()

        self.pre_gap = TrackBounds()
        self.cue_root = root_element

    def __str__(self) -> str:
        return f"{self.track_number:02}. {self.track_name} ({self.begin} — {self.end})"
 

class _Context:
    def __init__(self, current_file: Optional[ElementFile] = None,
                 current_track: Optional[ElementTrack] = None) -> None:
        self.file = current_file
        self.track = current_track

        self.file_previous = None
        self.track_previous = None


class ElementRoot:
    def __init__(self) -> None:
        self.album_date = Date()
        self.album_genre = None
        self.album_name = ""
        self.album_artist = ""
        self.disc_id = 0
        self.disc_number = 0
        self.disc_total = 0
        self.comments = None

        self.files = list()
        self.tracks = list()

    def __ilshift__(self, element: Union[ElementTrack, ElementFile]) -> "ElementRoot":
        if isinstance(element, ElementTrack):        
            self.tracks.append(element)
        elif isinstance(element, ElementFile):
            self.files.append(element)
        return self    
       
    def update_last_track(self, ctx: _Context) -> None:
        pass
 

class Parser:
    def __init__(self, input: Union[pathlib.Path, List[str]]) -> None:
        self.content = (input
                                  if type(input) == List[str]
                                  else input.open("r", encoding="utf-8").readlines())
        self.root_object = ElementRoot()
        self.root_object_path = (input
                            if isinstance(input, pathlib.Path)
                            else pathlib.Path())

        self.ctx = _Context()   
 
    def parse(self) -> ElementRoot:
        parent_object = self.root_object
 
        for line in self.content:
            line = line.lstrip(" ").rstrip("\n")
            tokens = line.split(" ")
            
            cmd = tokens[0]
            cmd_tokens = tokens[1:]

            object = self._invoke(cmd, cmd_tokens)

        self.root_object.update_last_track(self.ctx)
        return self.root_object

    def _invoke(self, cmd: str, tokens: List[str]) -> ElementBase:
        handler_cmd = f"_handler_{cmd.lower()}"
        handler_method = getattr(self, handler_cmd, None)
        if handler_method is None:
            raise ParserError(f"Unknown handler for '{cmd}' directive from .cue file")

        return handler_method(tokens)

    def _handler_rem(self, tokens: List[str]) -> ElementRoot:
        comment_name_to_attribute = {
            "DATE": self.root_object.album_date,
            "GENRE": self.root_object.album_genre,
            "DISCID": self.root_object.disc_id,
            "DISCNUMBER": self.root_object.disc_number,
            "TOTALDISCS": self.root_object.disc_total,
            "COMMENT": self.root_object.comments 
        }
        subcommand = tokens[0]
        subcommand_args = tokens[1:]

        attribute = " ".join(subcommand_args)

        attro = comment_name_to_attribute[subcommand]

        if type(attro) is list:
            attro.append(attribute)
        if type(attro) is Date:
            attro = Date(attribute)
        else:
            attro = attribute

        return self.root_object
        
    def _handler_performer(self, tokens: List[str]) -> ElementRoot:
        if self.ctx.track is None: 
            self.root_object.album_artist = " ".join(tokens).strip('"')
        else:
            self.ctx.track.track_artist = " ".join(tokens).strip('"')

        return self.root_object

    def _handler_title(self, tokens: List[str]) -> ElementRoot:
        if self.ctx.track is None:
            self.root_object.album_name = " ".join(tokens).strip('"')
        else:
            self.ctx.track.track_name = " ".join(tokens).strip('"')

        return self.root_object

    def _handler_file(self, tokens: List[str]) -> ElementFile:
        file_obj = ElementFile()
        self.root_object <<= file_obj

        file_obj.path = self.root_object_path.parent / pathlib.Path(" ".join(tokens[:-1]).strip('"'))
        print(self.root_object_path)
        print(file_obj.path) 
        file_obj.format = tokens[1] 

        self.ctx.file_previous = self.ctx.file
        self.ctx.file = file_obj

        return file_obj 
               
    def _handler_track(self, tokens: List[str]) -> ElementTrack:
        track_obj = ElementTrack(self.root_object)
        self.root_object <<= track_obj

        track_obj.track_number = int(tokens[0])

        self.ctx.track_previous = self.ctx.track
        self.ctx.track = track_obj

        return track_obj

    def _handler_index(self, tokens: List[str]) -> ElementTrack:
        index_type = tokens[0]
        time = tokens[1].split(":")
        
        index_time = int(time[0]) * 60 + int(time[1])
        frames = int(time[2])

        mseconds = int(round(int(time[2]) * 1000 / 75))

        if index_type == "01":
            self.ctx.track.begin.file = self.ctx.file
            self.ctx.track.begin.time = index_time
            self.ctx.track.begin.frames = frames
            self.ctx.track.begin.mseconds = mseconds
        elif index_type == "00":
            self.ctx.track.pre_gap.file = self.ctx.file
            self.ctx.track.pre_gap.time = index_time
            self.ctx.track.pre_gap.frames = frames
            self.ctx.track.pre_gap.mseconds = mseconds

        if index_type == "01":
            if self.ctx.track_previous is not None:
                if self.ctx.file_previous is not None:
                    self.ctx.track_previous.end.file = self.ctx.file_previous
                else:
                    self.ctx.track_previous.end.file = self.ctx.file

                if self.ctx.track.begin.frames == 0:
                    self.ctx.track_previous.end.time = self.ctx.track.begin.time - 1
                    self.ctx.track_previous.end.frames = 75
                    self.ctx.track_previous.end.mseconds = 999
                else:
                    self.ctx.track_previous.end.time = self.ctx.track.begin.time
                    self.ctx.track_previous.end.frames = self.ctx.track.begin.frames - 1
                    self.ctx.track_previous.end.mseconds = int(round((int(time[2]) - 1) * 1000 / 75)) 

        return self.ctx.track
