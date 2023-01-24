import musicbrainzngs

 
class MusicBrainzAPI:
    def __init__(self):
        musicbrainzngs.set_useragent("Krautcat Music App", "0.0.1",
                                     "georgiy.odishariya@gmail.com")

        self._artist_of_album_cache = dict()

    def get_artist_of_album(self, artist, album, date=None, *, cache=False):
        if cache:
            artist_in_mb = self._artist_of_album_cache.get(artist, None)
        else:
            artist_in_mb = None

        if artist_in_mb is not None:
            return artist_in_mb
        
        artist_offset = 0
        not_found = True
        page = 1

        while not_found and page < 6:
            mb_artists = musicbrainzngs.search_artists(offset=artist_offset,
                                                       artist=artist)

            for mb_artist in mb_artists["artist-list"]:

                album_offset = 0    
                
                while not_found:
                    mb_albums = musicbrainzngs.search_releases(offset=album_offset,
                                                               arid=mb_artist["id"])
            
                    for mb_album in mb_albums["release-list"]:
                        if date is not None:
                            date = date.split("-")[0]
                            date_cond = (
                                "date" in mb_album
                                and mb_album["date"].split("-")[0] == str(date)
                            )
                        else:
                            date_cond = True
                        
                        if album == mb_album["title"] and date_cond:
                            artist_in_mb = mb_artist["name"]
                            not_found = False

                    if len(mb_albums["release-list"]) == mb_albums["release-count"] - album_offset:
                        break
                    else:
                        album_offset += len(mb_albums["release-list"])

            if len(mb_artists["artist-list"]) == mb_artists["artist-count"] - artist_offset:
                break
            else:
                artist_offset += len(mb_artists["artist-list"])

            page += 1

        if artist_in_mb is not None:
            self._artist_of_album_cache[artist] = artist_in_mb

        return artist_in_mb