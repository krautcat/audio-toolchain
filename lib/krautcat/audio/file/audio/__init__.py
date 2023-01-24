import puremagic

from .alac import AudioFileALAC
from .flac import AudioFileFLAC
from .mp3 import AudioFileMP3

        
_MIME_MAPPING = {
    "audio/mpeg":   AudioFileMP3,
    "audio/flac":   AudioFileFLAC,
    "audio/x-flac": AudioFileFLAC,
}
_FILE_TYPENAME_MAPPING = {
    "Apple Lossless Audio Codec file":  AudioFileALAC, 
}


def open_audio_file(file_path):
    try:
        magic_info = puremagic.magic_file(str(file_path))
        if len(magic_info) > 0:
            mime_type = magic_info[0].mime_type
            name = magic_info[0].name
        else:
            mime_type = ""
            name = ""
    except puremagic.main.PureError:
        return None

    if mime_type != "":
        if mime_type not in _MIME_MAPPING:
            return None 
        return _MIME_MAPPING[mime_type](file_path)
    else:
        if name not in _FILE_TYPENAME_MAPPING:
            return None 
        return _FILE_TYPENAME_MAPPING[name](file_path)
