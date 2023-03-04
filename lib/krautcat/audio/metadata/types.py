from typing import Optional, Union

from mutagen.id3 import ID3TimeStamp


class Date:
    def __init__(self, date_string: Optional[Union[str, "Date"]] = None) -> None:
        self.year = 0
        self.month = 0       
        self.day = 0       
 
        if date_string is None or date_string == "":
            return
 
        if type(date_string) is Date:
            self.year = date_string.year
            self.month = date_string.month
            self.day = date_string.day
            return    
        
        if isinstance(date_string, int):
            self.year = date_string
            return

        if isinstance(date_string, ID3TimeStamp):
            date_string = str(date_string)

        date_parts = list()
        if "-" in date_string: 
            date_parts = date_string.split("-")
        elif " " in date_string:
            date_parts = date_string.split(" ")
        else:
            date_parts.append(date_string)

        self.year = int(date_parts[0])

        if len(date_parts) == 3:
            self.month = int(date_parts[1])
            self.day = int(date_parts[2])

    def __str__(self) -> str:
        date_parts = list()

        for part in [self.year, self.day, self.month]:
            if part != 0:
                date_parts.append(part)

        return "-".join([str(p) for p in date_parts])
