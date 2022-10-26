# by bunny

import colorama
import requests
import re
import os
import m3u8
import sys
import time
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
Regx = re.compile(r"apple\.com\/(\w\w)\/(playlist|album|artist)\/(.+\/)?(\d+|pl\..+)")

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


    json = response.json()

    if "message" in json:
        print(json["message"])
        time.sleep(0.1)
        return get_json(country, _id, token, kind)

    return json


def get_m3u8(json, kind, atype):
    BASE = json['data'][0]['attributes']

    if 'editorialVideo' not in BASE: # no animated artwork
        return None

    BASE = BASE['editorialVideo']

    if kind in ['album', 'playlist']:
        if atype == 'full':
            try:
                return BASE['motionDetailTall']['video']
            except:
                try:
                    return BASE['motionTallVideo3x4']['video']
                except:
                    return None
        elif atype == 'square':
            try:
                return BASE['motionDetailSquare']['video']
            except KeyError:
                try:
                    return BASE['motionSquareVideo1x1']['video']
                except:
                    return None
    elif kind == 'artist':
        if atype == 'full':
            try:
                return BASE['motionArtistWide16x9']['video']
            except KeyError:
                return BASE['motionArtistFullscreen16x9']['video']
        elif atype == 'square':
            try:
                return BASE['motionArtistSquare1x1']['video']
            except:
                return None


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
           

def get_album_download_path(meta, artwork_type):
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
    fname = sanitize_filename(f"{album.album} ({album.album_id})-{artwork_type}.mp4")
    ANIMATED_PATH = os.path.join(sys.path[0], "artwork", "artists", album.artist)
    if not os.path.exists(ANIMATED_PATH):
        os.makedirs(ANIMATED_PATH)
    return os.path.join(ANIMATED_PATH, fname)

def get_playlist_download_path(meta, artwork_type):
    metadata = f"""
        Playlist name    : {meta["name"]}
        Curator name     : {meta["curatorName"]}
        Modified date    : {meta["lastModifiedDate"]}
    """
    print(metadata)
    fname = sanitize_filename(f"{meta['name']} ({meta['lastModifiedDate'][:4]})-{artwork_type}.mp4")
    ANIMATED_PATH = os.path.join(sys.path[0], "artwork", "playlists", meta["curatorName"])
    if not os.path.exists(ANIMATED_PATH):
        os.makedirs(ANIMATED_PATH)
    return os.path.join(ANIMATED_PATH, fname)

def get_artist_download_path(meta, artwork_type):
    metadata = f"""
        Artist name    : {meta["name"]}
    """
    print(metadata)
    fname = sanitize_filename(f"artist-{artwork_type}.mp4")
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

def tag_album(video, meta):
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

def extract_info(url):
    # extracting out the country and ID
    result = Regx.search(url)
    if result is None:
        return None, None, None
    country = result.group(1)
    kind = result.group(2)
    id_ = result.group(4)
    return country, kind, id_

def download_item(url, artwork_type, rep, aud):
    country, kind, id_ = extract_info(url)

    if not country:
        print(Fore.RED + "Invalid URL")
        return

    # getting the json response
    json = get_json(country, id_, token, kind)

    # extracting the master m3u8 from json
    m3u8_ = get_m3u8(json, kind, artwork_type)

    if not m3u8_:
        print(Fore.RED + "Item does not have animated artwork")
        return

    # metadata stuff
    meta = json['data'][0]['attributes']

    if kind == 'album':
        video_path = get_album_download_path(meta, artwork_type)
    elif kind == 'playlist':
        video_path = get_artist_download_path(meta, artwork_type)
    elif kind == 'artist':
        video_path = get_artist_download_path(meta, artwork_type)

    if os.path.exists(video_path):
        print("File already exists. Skipping...")
        return

    playlist = m3u8.load(m3u8_)
    print_table(playlist.data)
    if args.max_resolution:
        m3u8_ = playlist.data["playlists"][-1]['uri']
    else:
        playlist_id = int(input("Enter the ID: "))
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
        tag_album(video, meta)
    elif kind == 'playlist':
        tag_playlist(video, meta)

    print('\n'+video_path)

    # deleting temp files
    os.remove(video_file_name)

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
        '-T', '--type', help="[full,square,all] (square by default)", default='square', type=str)
    parser.add_argument(
        '-L', '--loops', help="[int] Number of times you want to loop the artwork (No loops by default)", default=0, type=int)
    parser.add_argument(
        '-A', '--audio', help="Pass this flag if you also need the audio", action="store_true")
    parser.add_argument(
        '-M', '--max-resolution', help="Pass this flag if you need the maximum resolution", action="store_true")
    parser.add_argument(
        '-B', '--all-artist-albums', help="Pass this flag if you need all of an artist's albums (ignored if input is not an artist)", action="store_true")
    parser.add_argument(
        '-F', '--input-file', help="Pass this flag if your input is a path to a file with URLs for batch processing (one per line)", action="store_true")
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

    artwork_type = args.type
    rep = str(args.loops)
    aud = args.audio

    urls = []
    if args.input_file:
        with open(args.url, 'r') as f:
            lines = [line for line in f.readlines() if line.strip()]
            for line in lines:
                urls.append(line)
    else:
        urls =  [args.url]

    for url in urls:
        if artwork_type == 'all':
            download_item(url, 'full', rep, aud)
            download_item(url, 'square', rep, aud)
        else:
            download_item(url, artwork_type, rep, aud)

        if args.all_artist_albums:
            country, kind, id_ = extract_info(url)
            if kind == "artist":
                print("Downloading all albums...")
                json = get_json(country, id_, token, kind)
                albums = json['data'][0]['relationships']['albums']['data']
                for album in albums:
                    url = "https://music.apple.com/us/album/" + album['id']
                    if artwork_type == 'all':
                        download_item(url, 'full', rep, aud)
                        download_item(url, 'square', rep, aud)
                    else:
                        download_item(url, artwork_type, rep, aud)