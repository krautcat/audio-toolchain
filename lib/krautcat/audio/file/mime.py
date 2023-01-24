import puremagic

from krautcat.audio.file.audio import *


_MIME_TYPE_MAPPING = {
    "audio/mpeg":   AudioFileMP3,
    "audio/flac":   AudioFileFLAC,
    "audio/x-flac": AudioFileFLAC,
}

_MIME_NAME_MAPPING = {
    "Apple Lossless Audio Codec file":  AudioFileALAC,
}

def file_class(entry):
    try:
        magic_info = puremagic.magic_file(str(entry))
        if len(magic_info) > 0:
            mime_type_mc = magic_info[0].mime_type
            name_mc = magic_info[0].name
            
            mime_type = None
            name = None

            for info in magic_info:
                if (info.mime_type in _MIME_TYPE_MAPPING.keys()
                    or name in _MIME_TYPE_MAPPING.keys()):
                    mime_type = info.mime_type
                    name = info.name
                    break 

            if mime_type is None and name is None:
                mime_type = mime_type_mc
                name = name_mc

        else:
            mime_type = ""
            name = ""
    except puremagic.main.PureError:
        return None

    if mime_type != "":
        return _MIME_TYPE_MAPPING.get(mime_type, None)
    else:
        return _MIME_NAME_MAPPING.get(name, None)

