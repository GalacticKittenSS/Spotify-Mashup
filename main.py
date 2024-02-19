from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import string
import random
import json

import os
from dotenv import load_dotenv
load_dotenv()

import Spotify

# Web Server Details
hostName = "localhost"
serverPort = 3000
redirect_uri = f'http://{hostName}:{serverPort}'

# Spotify Setup
client_id = os.getenv('CLIENT_ID')
client_secret = os.getenv('CLIENT_SECRET')
SpotifyApp = Spotify.Application(client_id, client_secret, redirect_uri + '/callback')

def GenerateRandomString(length: int):
    characters = list(string.ascii_letters + string.digits)
    random.shuffle(characters)

    letters = []
    for i in range(length):
        letters.append(random.choice(characters))

    random.shuffle(letters)
    return "".join(letters)


def CreateMashupFromPlaylists(user, playlist_name, albums):
    tracks = []
    album_names = ''

    for p in albums:
        album_names = album_names + p.GetName() + ", "

        songs = p.GetTracks()
        for s in songs:
            tracks.append(s.URI)

    album_names = album_names[:-2] + "."
    return CreateMashupFromTracks(user, 
        playlist_name, f'A mashup of the playlists: {album_names}',
        tracks
    )

def CreateMashupFromTracks(user, playlist_name, playlist_description, tracks):
    playlist = user.CreatePlaylist(playlist_name, playlist_description)

    request_list = [tracks[i:i + 100] for i in range(0, len(tracks), 100)]
    for uri in request_list:
        playlist.AddTracks(uri)
    
    return playlist

class RequestHandler(BaseHTTPRequestHandler):
    Content = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Spotify</title>
</head>
</html>
"""

    ContentType = "text/html"

    def GetQuery(self, query, name):
        if query.get(name):
            return query.get(name)[0]
        return None

    def _get_path(self):
        return urlparse(self.path)

    def _send_headers(self):
        self.send_response(200)
        self.send_header("Content-Type", self.ContentType)
        self.end_headers()

    def _send_content(self):
        self.wfile.write(self.Content.encode('utf-8'))

    def do_POST(self):
        path = self._get_path()
        self.ContentType = 'text/html'

        # Get Post Body
        content_len = int(self.headers.get('Content-Length'))
        post_body = self.rfile.read(content_len)
        queries = parse_qs(post_body.decode('utf-8'))

        # 'Create Playlist' form submitted [JSON]
        if path.path == "/submit":
            key = self.headers.get('user')
            user = SpotifyApp.GetUserFromKey(key)
            
            playlist = self.MashupFromQuery(user, queries)
            #TODO: Fix image
            self.Content = json.dumps({ 'playlist': {'name': playlist.GetName(), 'id': playlist.ID, 'image': playlist.Image } });
            self.ContentType = 'application/json'

        self._send_headers()
        self._send_content()
    
    def do_GET(self):
        path = self._get_path()
        queries = parse_qs(path.query)
        self.ContentType = 'text/html'

        # GET tracks in playlist [JSON]
        if path.path == "/tracks":
            key = self.headers.get('user')
            user = SpotifyApp.GetUserFromKey(key)
            
            playlist_id = self.GetQuery(queries, 'playlist_id')
            playlist = Spotify.Playlist(playlist_id, user)
            
            # TODO: Use pages
            self.Content = json.dumps({ 'items': [{ "id": track.ID, "name": track.GetName() } for track in playlist.GetTracks()], 'next': '' })
            self.ContentType = 'application/json'
        
        # 'Create Playlist' form submitted [JSON]
        elif path.path == "/submit":
            key = self.headers.get('user')
            user = SpotifyApp.GetUserFromKey(key)
            
            playlist = self.MashupFromQuery(user, queries)
            self.Content = json.dumps({ 'playlist': {'name': playlist.GetName(), 'id': playlist.ID, 'image': playlist.Image } });
            self.ContentType = 'application/json'

        # Redirect from User Login [HTML]
        elif queries.get('user'):
            key = self.GetQuery(queries, 'user')
            user = SpotifyApp.GetUserFromKey(key)
            
            # TODO: Refresh token if user exists
            try:
                albums = user.GetPlaylists()
                self.Content = self.ShowPlaylists(albums, key, user.AccessToken)
            except Exception as error:
                print("Redirecting user due to error:", error)
                self.Content = self.Redirect(redirect_uri)
            
        # User logged in (authorization code sent) [HTML]
        elif path.path == "/callback":
            code = self.GetQuery(queries, 'code')
            user = SpotifyApp.GetUser(code)

            #Identify user by key instead of access_token (for security reasons)
            key = GenerateRandomString(32)
            SpotifyApp.CreateUserKey(user, key)
            
            self.Content = self.Redirect(redirect_uri + f'?user={key}')

        # Redirect to Spotify (get authorization code) [HTML]
        else:
            self.Content = self.Redirect(SpotifyApp.GetRedirectURL())

        self._send_headers()
        self._send_content()

    def Redirect(self, url):
        return f'<html><meta http-equiv="refresh" content="0; url={url}"/></html>'

    def MashupFromQuery(self, user, query):
        if not query.get('playlist_name'):
            print('No name detected, skipping playlist creation!')
            return None
            
        track_query = self.GetQuery(query, 'tracks')
        if track_query:
            tracks = track_query.split(',');
            track_uris = [Spotify.Track(id, user).URI for id in tracks]
            
            return CreateMashupFromTracks(user, 
                query.get('playlist_name')[0], "",
                track_uris
            )
        
        playlist_query = self.GetQuery(query, 'playlists')
        if playlist_query:
            playlists = playlist_query.split(',')
            spotify_playlists = [Spotify.Playlist(id, user) for id in playlists]
            
            return CreateMashupFromPlaylists(user, 
                query.get('playlist_name')[0],
                spotify_playlists
            )

    def ShowPlaylists(self, albums, key, access_token):
        body = ""
        for i, a in enumerate(albums):
            perPlaylist = f"""
<div class="Playlist" id="{a.ID}" name="{a.ID}">
  <div class="centre">
    <img src="{a.Image}" class="playlist-preview">
    <div class="label">
      <h4 onclick="ToggleShowElements('{a.ID}', '{a.Type}')">{a.GetName()}</h4>
    </div>
    <div class="checkbox">
        <input type="checkbox" onclick="ToggleEnableElements('{a.ID}', this.checked)">
    </div>
  </div>
  <div class="Tracks" style="display: none;"></div>
</div>
"""
            body = body + perPlaylist

        with open('index.html', 'r') as f:
            html = f.read()

        html = html.replace('{body}', body)
        html = html.replace('{key}', key)
        html = html.replace('{token}', access_token)
        return html


# Run Web Server
print(f'Please open your browser to {redirect_uri}')
webServer = HTTPServer((hostName, serverPort), RequestHandler)
while True:
    webServer.handle_request()
webServer.server_close()
