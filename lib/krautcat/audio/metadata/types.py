from typing import Optional, Union


class Date:
    def __init__(self, date_string: Optional[Union[str, "Date"]] = None) -> None:
        self.year = 0
        self.month = 0       
        self.day = 0       
 
        if date_string is None:
            return
 
        if type(date_string) is Date:
            self.year = date_string.year
            self.month = date_string.month
            self.day = date_string.day
            return    

        date_parts = date_string.split("-")
        
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
