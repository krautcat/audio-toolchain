import pathlib

from enum import Enum, IntEnum
from typing import Optional, Union

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject, GLib
Gst.init(None)


class _GstreamerEnumExposer(type):
    def __new__(cls, name, bases, namespace, **kwargs):
        new_cls = super().__new__(cls, name, bases, namespace)
        if getattr(new_cls, "__gstreamer_name__", "") == "":
            raise AttributeError(f"Class '{name}' has invalid '__gobject_name__' attribute")

        gst_obj = Gst.ElementFactory.make(new_cls.__gstreamer_name__)
        for enum_cls_name, prop in kwargs.items():
            enum_cls_obj = gst_obj.find_property(prop).enum_class
            setattr(new_cls, enum_cls_name, IntEnum(enum_cls_obj.__name__, {v.value_nick.upper(): k
                                                                            for k, v
                                                                            in enum_cls_obj.__enum_values__.items()}))

        return new_cls


class ElementBase:
    __gstreamer_name__ = ""

    def __init__(self, *, name: Optional[str] = None) -> None:
        self.__gobject__ = Gst.ElementFactory.make(self.__gstreamer_name__, name)


class MixinElementLinkable:
    def __or__(self, other: ElementBase) -> ElementBase:
        self.__gobject__.link(other.__gobject__)
        return other


class ElementPipeline(ElementBase):
    __gstreamer_name__ = "pipeline"

    def __lshift__(self, other: ElementBase) -> "ElementPipeline":
        self.__gobject__.add(other.__gobject__)
        return self

    def __ilshift__(self, other: ElementBase) -> "ElementPipeline":
        return self << other

    @property
    def bus(self) -> Gst.Bus:
        return self.__gobject__.get_bus()

    @property
    def state(self) -> Gst.State:
        return self.__gobject__.get_state()

    @state.setter
    def state(self, stt: Gst.State) -> None:
        self.__gobject__.set_state(stt)


class ElementFileSource(ElementBase, MixinElementLinkable):
    __gstreamer_name__ = "filesrc"

    def __init__(self, location: Optional[Union[pathlib.Path, str]],
                 *, name: Optional[str] = None) -> None:
        super().__init__(name=name)
        if location is not None:
            self.location = location

    @property
    def location(self) -> Optional[pathlib.Path]:
        prop = self.__gobject__.get_property("location")
        if prop is not None:
            return pathlib.Path(prop)

    @location.setter
    def location(self, path: Union[str, pathlib.Path]) -> None:
        self.__gobject__.set_property("location", str(path))


class ElementFileSink(ElementBase, MixinElementLinkable):
    __gstreamer_name__ = "filesink"

    def __init__(self, location: Optional[Union[pathlib.Path, str]] = None,
                 *, name: Optional[str] = None) -> None:
        super().__init__(name=name)
        if location is not None:
            self.location = location

    @property
    def location(self) -> Optional[pathlib.Path]:
        prop = self.__gobject__.get_property("location")
        if prop is not None:
            return pathlib.Path(prop)

    @location.setter
    def location(self, path: Union[str, pathlib.Path]) -> None:
        self.__gobject__.set_property("location", str(path))


class ElementFLACParser(ElementBase, MixinElementLinkable):
    __gstreamer_name__ = "flacparse"


class ElementFLACDecoder(ElementBase, MixinElementLinkable):
    __gstreamer_name__ = "flacdec"


class ElementFLACEncoder(ElementBase, MixinElementLinkable):
    __gstreamer_name__ = "flacenc"


class ElementAudioParse(ElementBase, MixinElementLinkable):
    __gstreamer_name__ = "rawaudioparse"


class ElementAudioConvert(ElementBase, MixinElementLinkable):
    __gstreamer_name__ = "audioconvert"


class ElementAudioResample(ElementBase, MixinElementLinkable):
    __gstreamer_name__ = "audioresample"
    
    def __init__(self, quality: Optional[int] = None, *, name: Optional[str] = None) -> None:
        super().__init__(name=name)
        if quality is not None:
            self.quality = quality

    @property
    def quality(self) -> Optional[int]:
        return self.__gobject__.get_property("quality")
       
    @quality.setter
    def quality(self, quality: int) -> None:
        self.__gobject__.set_property("quality", quality)


class ElementMP3Encoder(ElementBase, MixinElementLinkable, metaclass=_GstreamerEnumExposer,
                        Target="target", EngineQuality="encoding-engine-quality"):
    __gstreamer_name__ = "lamemp3enc"

    class Bitrate(str, Enum):
        CBR = "cbr"
        VBR = "vbr"

    def __init__(self, bitrate_type: Bitrate = Bitrate.CBR, *,
                 bitrate: int = 320,
                 quality: float = 10,
                 engine_quality: Optional["ElementMP3Encoder.EngineQuality"] = None,
                 name: Optional[str] = None):
        super().__init__(name=name)

        if bitrate_type == self.Bitrate.CBR:
            self.cbr = bitrate
        elif bitrate_type == self.Bitrate.VBR:
            self.vbr = quality
        else:
            raise ValueError

        if engine_quality is not None:
            self.engine_quality = engine_quality

    @property
    def cbr(self) -> Optional[int]:
        if not self.__gobject__.get_property(self.Bitrate.CBR):
            return None

        return self.__gobject__.get_property("bitrate")

    @cbr.setter
    def cbr(self, bitrate: int) -> None:
        self._set_target(self.Target.BITRATE)
        self.__gobject__.set_property(self.Bitrate.CBR, True)
        self.__gobject__.set_property("bitrate", bitrate)

    @property
    def vbr(self) -> Optional[float]:
        if self.__gobject__.get_property(self.Bitrate.CBR):
            return None

        return self.__gobject__.get_property("quality")

    @vbr.setter
    def vbr(self, quality: float) -> None:
        self._set_target(self.Target.QUALITY)
        self.__gobject__.set_property("quality", quality)

    @property
    def engine_quality(self) -> "ElementMP3Encoder.EngineQuality":
        return ElementMP3Encoder.EngineQuality(
            self.__gobject__.get_property("encoding-engine-quality")
        )

    @engine_quality.setter
    def engine_quality(self, quality: "ElementMP3Encoder.EngineQuality") -> None:
        self.__gobject__.set_property("encoding-engine-quality", quality)

    def _set_target(self, tgt: "ElementMP3Encoder.Target") -> None:
        self.__gobject__.set_property("target", tgt)
