# by bunny

import colorama
import requests
import re
import os
import m3u8
import sys
import argparse
from shutil import move
from mutagen.mp4 import MP4
try:
    from prettytable.colortable import ColorTable, Theme
    _color = True
except ImportError:
    _color = False
    from prettytable import PrettyTable
from sanitize_filename import sanitize as sanitize_filename
import ffmpeg
from colorama import Fore, Back
colorama.init(autoreset=True)

TOKEN = 'eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IldlYlBsYXlLaWQifQ.eyJpc3MiOiJBTVBXZWJQbGF5IiwiaWF0IjoxNjU3NTk2NjY4LCJleHAiOjE2NzMxNDg2NjgsInJvb3RfaHR0cHNfb3JpZ2luIjpbImFwcGxlLmNvbSJdfQ.D3lSHZi212e7PWV_6tI8IAtkN7KQr1C1ZdcYY2vwdzHf0u5bt2tm1wtYYH87to3S-AAoz0rtANsPUsvDtG_ShA'
Regx = re.compile(r"apple\.com\/(\w\w)\/(playlist|album|artist)\/.+\/(\d+|pl\..+)")

title = """
             /$$$$$$$$          /$$               /$$                          
            | $$_____/         | $$              | $$                          
            | $$     /$$$$$$  /$$$$$$    /$$$$$$$| $$$$$$$   /$$$$$$   /$$$$$$ 
            | $$$$$ /$$__  $$|_  $$_/   /$$_____/| $$__  $$ /$$__  $$ /$$__  $$
            | $$__/| $$$$$$$$  | $$    | $$      | $$  \ $$| $$$$$$$$| $$  \__/
            | $$   | $$_____/  | $$ /$$| $$      | $$  | $$| $$_____/| $$      
            | $$   |  $$$$$$$  |  $$$$/|  $$$$$$$| $$  | $$|  $$$$$$$| $$      
            |__/    \_______/   \___/   \_______/|__/  |__/ \_______/|__/      
                    Apple-Music animated cover artwork downloader                      
                                                                -- by bunny  
    """


def get_auth_token():
    response = requests.get("https://music.apple.com/us/album/positions-deluxe-edition/1553944254")
    return re.search(r"(eyJhbGc.+?)%22%7D", response.text).group(1)


def get_json(country, _id, token, kind):

    headers = {
        'origin': 'https://music.apple.com',
        'authorization': f'Bearer {token}'
    }

    album_params = (
        ('filter[equivalents]', f'{_id}'),
        ('extend', 'editorialVideo'),
    )

    playlist_params = {
        'extend': 'editorialVideo'
    }

    artist_params = (
        ('extend', 'editorialVideo'),
    )

    if kind == 'album':
        response = requests.get(
            f'https://amp-api.music.apple.com/v1/catalog/{country}/albums', headers=headers, params=album_params)
    elif kind == 'playlist':
        response = requests.get(
            f'https://amp-api.music.apple.com/v1/catalog/{country}/playlists/{_id}', headers=headers, params=playlist_params)
    elif kind == 'artist':
        response = requests.get(
            f'https://amp-api.music.apple.com/v1/catalog/{country}/artists/{_id}', headers=headers, params=artist_params)

    return response.json()



def get_m3u8(json, kind, atype):
    BASE = json['data'][0]['attributes']

    if 'editorialVideo' not in BASE: # no animated artwork
        return None

    BASE = BASE['editorialVideo']

    if kind in ['album', 'playlist']:
        if atype == 'full':
            return BASE['motionDetailTall']['video']
        elif atype == 'square':
            try:
                return BASE['motionDetailSquare']['video']
            except KeyError:
                return BASE['motionSquareVideo1x1']['video']
    elif kind == 'artist':
        if atype == 'full':
            try:
                return BASE['motionArtistWide16x9']['video']
            except KeyError:
                return BASE['motionArtistFullscreen16x9']['video']
        elif atype == 'square':
            return BASE['motionArtistSquare1x1']['video']


def listall(json):
    table = ColorTable(theme=Theme(default_color='90')) if _color else PrettyTable()
    table.field_names = ["Track No.", "Name"]
    table.align["Name"] = "l"
    totaltracks = int(json['data'][0]['attributes']['trackCount'])
    for i in range(totaltracks):
        if json['data'][0]['relationships']['tracks']['data'][i]['type'] == "songs":
            song = json['data'][0]['relationships']['tracks']['data'][i]['attributes']['name']
            table.add_row([i+1, song])
    print(table)


def remove_html_tags(text):
    """Remove html tags from a string"""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


def check_token(tkn=None):
    if tkn is None:
        tkn = TOKEN

    headers = {
        'authorization': f'Bearer {tkn}',
        'origin': 'https://music.apple.com',
    }

    params = (
        ('filter[equivalents]', '1551901062'),
        ('extend', 'editorialVideo'),
    )

    response = requests.get(
        'https://amp-api.music.apple.com/v1/catalog/in/albums', headers=headers, params=params)

    if response.status_code != 200:
        return None
    return tkn


def print_table(json):
    tmp = Theme(default_color='90') if _color else None
    table = ColorTable(theme=tmp) if _color else PrettyTable()
    table.field_names = ["ID", "Resolution", "Bitrate", "Codec", "FPS"]
    for i in range(len(json['playlists'])):
        if i == len(json['playlists'])-1:
            pass
        elif json['playlists'][i]['stream_info']['resolution'] == json['playlists'][i+1]['stream_info']['resolution']:
            continue
        table.add_row([i, json['playlists'][i]['stream_info']['resolution'], str(round((int(json['playlists'][i]['stream_info']['bandwidth']) /
                      1000000), 2)) + " Mb/s", json['playlists'][i]['stream_info']['codecs'][0:4], json['playlists'][i]['stream_info']['frame_rate']])
    print(table)

class Album:
    def __init__(self, meta):
        self.album_id = meta["playParams"]["id"]
        self.album = meta["name"]
        self.artist = meta["artistName"]
        self.album_url = meta["url"]
        self.tracks = meta["trackCount"]
        self.release_date = meta["releaseDate"]
        self.upc = meta['upc']
        self.copyright_ = meta.get("copyright")
        self.record_label = meta.get('recordLabel')
        try:
            self.genre = meta["genreNames"][0]
        except (KeyError, TypeError):
            self.genre = None
        self.rating = meta.get("contentRating")
        self.editorial_notes = meta.get('editorialNotes', {}).get('standard')
           

def get_album_download_path(meta):
    album = Album(meta)

    # showing general details
    metadata = f"""
        Album ID         : {album.album_id}
        Album Name       : {album.album}
        Artist           : {album.artist}
        Rating           : {str(album.rating).title()}
        Number of tracks : {album.tracks}
        Copyright        : {album.copyright_}
        Release date     : {album.release_date}
        Genre            : {album.genre}
    """
    print(metadata)
    fname = sanitize_filename(f"{album.album} ({album.album_id}) - {args.type}.mp4")
    ANIMATED_PATH = os.path.join(sys.path[0], "artwork", "artists", album.artist)
    if not os.path.exists(ANIMATED_PATH):
        os.makedirs(ANIMATED_PATH)
    return os.path.join(ANIMATED_PATH, fname)

def get_playlist_download_path(meta):
    metadata = f"""
        Playlist name    : {meta["name"]}
        Curator name     : {meta["curatorName"]}
        Modified date    : {meta["lastModifiedDate"]}
    """
    print(metadata)
    fname = sanitize_filename(f"{meta['name']} ({meta['lastModifiedDate'][:4]}) - {args.type}.mp4")
    ANIMATED_PATH = os.path.join(sys.path[0], "artwork", "playlists", meta["curatorName"])
    if not os.path.exists(ANIMATED_PATH):
        os.makedirs(ANIMATED_PATH)
    return os.path.join(ANIMATED_PATH, fname)

def get_artist_download_path(meta):
    metadata = f"""
        Artist name    : {meta["name"]}
    """
    print(metadata)
    fname = sanitize_filename(f"artist - {args.type}.mp4")
    ANIMATED_PATH = os.path.join(sys.path[0], "artwork", "artists", meta["name"])
    if not os.path.exists(ANIMATED_PATH):
        os.makedirs(ANIMATED_PATH)
    return os.path.join(ANIMATED_PATH, fname)

def download_video(video_file_name, m3u8):
    # downloading video in mp4 container
    print("\nDownloading the video...")

    stream = ffmpeg.input(m3u8)
    stream = ffmpeg.output(stream, video_file_name, codec='copy').global_args(
        '-loglevel', 'quiet', '-y')
    ffmpeg.run(stream)
    del stream

    print("Video downloaded.")

def create_looped_video(video_file_name):
    looped_file_name = 'fixed.mp4'
    # making the new looped video
    stream = ffmpeg.input(video_file_name, stream_loop=rep)
    stream = ffmpeg.output(stream, looped_file_name, codec='copy').global_args(
        '-loglevel', 'quiet', '-y')
    ffmpeg.run(stream)
    del stream
    return looped_file_name

def download_and_mux_audio(json, looped_video_file_name):
    audio_file_name = 'audio.m4a'
    print("\nAudio tracks:")
    listall(json)
    index = int(input("\nSelect the audio track number : "))
    index = index - 1

    m4a = json['data'][0]['relationships']['tracks']['data'][index]['attributes']['previews'][0]['url']
    # downloading the selected m4a track using requests
    print("\nDownloading the audio...")
    r = requests.get(m4a, allow_redirects=True)
    open('audio.m4a', 'wb').write(r.content)

    print("Audio downloaded.")

    # multiplexing
    print("\nMultiplexing...")
    # multiplex audio and video using ffmpeg-python
    stream_video = ffmpeg.input(looped_video_file_name)
    stream_audio = ffmpeg.input(audio_file_name)
    ffmpeg.output(stream_video, stream_audio, video_path, codec='copy',
                    shortest=None).global_args("-shortest", "-y", '-loglevel', 'quiet').run()
    print("Done.")

    os.remove(looped_video_file_name)
    os.remove(audio_file_name)

def tag_album(meta):
    album = Album(meta)
    
    video["\xa9alb"] = album.album
    video["aART"] = album.artist
    video["----:TXXX:URL"] = bytes(album.album_url, 'UTF-8')
    video["----:TXXX:Total tracks"] = bytes(str(album.tracks), 'UTF-8')
    video["----:TXXX:Release date"] = bytes(album.release_date, 'UTF-8')
    video["----:TXXX:UPC"] = bytes(album.upc, 'UTF-8')
    video["----:TXXX:Content Advisory"] = bytes(
        'Explicit' if album.rating != '' else 'Clean', 'UTF-8')
    if album.copyright_ is not None:
        video["cprt"] = album.copyright_
    if album.record_label is not None:
        video["----:TXXX:Record label"] = bytes(album.record_label, 'UTF-8')
    if album.genre is not None:
        video["\xa9gen"] = album.genre
    if album.editorial_notes is not None:
        video["----:TXXX:Editorial notes"] = bytes(
            remove_html_tags(album.editorial_notes), 'UTF-8')
    video.pop("©too")
    video.save()
    print("Done.")

def tag_playlist(meta):
    video["\xa9alb"] = meta["name"]
    video["aART"] = meta["curatorName"]
    video["----:TXXX:URL"] = bytes(meta["url"], 'UTF-8')
    video["----:TXXX:Release date"] = bytes(meta["lastModifiedDate"], 'UTF-8')
    if meta["editorialNotes"]['standard'] != '':
        video["----:TXXX:Editorial notes"] = bytes(
            remove_html_tags(meta["editorialNotes"]['standard']), 'UTF-8')
    video.pop("©too")
    video. save()
    print("Done.")

if __name__ == "__main__":
    # clean screen
    os.system('cls' if os.name == 'nt' else 'clear')

    print(Fore.GREEN + title)

    parser = argparse.ArgumentParser(
        description="Downloads animated cover artwork from Apple music.")
    parser.add_argument(
        '-T', '--type', help="[full,square] (square by default)", default='square', type=str)
    parser.add_argument(
        '-L', '--loops', help="[int] Number of times you want to loop the artwork (No loops by default)", default=0, type=int)
    parser.add_argument(
        '-A', '--audio', help="Pass this flag if you also need the audio", action="store_true")
    parser.add_argument(
        '-R', '--resolution', help="[int] Supply a resolution ID beforehand", type=int)
    parser.add_argument(
        'url', help="URL")

    args = parser.parse_args()

    print("Checking if the static token is still alive...")
    # checking if the token is still alive
    token = check_token(TOKEN)
    if token is None:
        print(Back.RED + "Regenerating a new token.")
        token = get_auth_token()
    print(Back.GREEN + "Token is valid!")

    url = args.url
    artwork_type = args.type
    rep = str(args.loops)
    aud = args.audio

    # extracting out the country and album ID
    result = Regx.search(url)
    if result is None:
        print(Fore.RED + "Invalid URL")
        sys.exit()
    country = result.group(1)
    kind = result.group(2)
    id_ = result.group(3)

    # getting the json response
    json = get_json(country, id_, token, kind)

    # extracting the master m3u8 from json
    m3u8_ = get_m3u8(json, kind, artwork_type)

    if not m3u8_:
        print(Fore.RED + "Album does not have animated artwork")
        sys.exit()

    # metadata stuff
    meta = json['data'][0]['attributes']

    if kind == 'album':
        video_path = get_album_download_path(meta)
    elif kind == 'playlist':
        video_path = get_artist_download_path(meta)
    elif kind == 'artist':
        video_path = get_artist_download_path(meta)

    playlist = m3u8.load(m3u8_)
    print_table(playlist.data)
    playlist_id = args.resolution if args.resolution else int(input("Enter the ID: "))
    m3u8_ = playlist.data["playlists"][playlist_id]['uri']

    video_file_name = "video.mp4"
    download_video(video_file_name, m3u8_)

    looped_video_file_name = create_looped_video(video_file_name)

    if aud and kind == 'album':
        download_and_mux_audio(json, looped_video_file_name)
    else:
        move(looped_video_file_name, video_path)

    # tagging
    print("\nTagging metadata..")
    video = MP4(video_path)
    if kind == 'album':
        tag_album(meta)
    elif kind == 'playlist':
        tag_playlist(neta)

    print('\n'+video_path)

    # deleting temp files
    os.remove(video_file_name)
