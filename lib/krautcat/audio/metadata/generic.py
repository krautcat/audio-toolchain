from abc import abstractmethod


class Metadata:
    def __init__(self, tags=None):
        self._artist = None
        self._track_name = None
        self._album = None
        self._date = None

        self._track_number = None
        self._total_tracks = None

        if tags is not None:
            self.track_name = tags
            self.track_number = tags
            
            self.artist = tags
            self.date = tags
            self.album = tags

    def __str__(self):
        return (f"{self.track_number}. {self.track_name} ({self.artist} - {self.date} - {self.album})")

    def __ilshift__(self, other):
        self.track_name = other.track_name
        self.track_number = other.track_number

        self.total_tracks = other.total_tracks

        self.artist = other.artist
        self.date = other.date
        self.album = other.album

        return self
