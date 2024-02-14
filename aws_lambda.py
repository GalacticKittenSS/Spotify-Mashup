import os
import logging
import json
import boto3

from urllib.parse import urlencode

import string
import random

import Spotify

#Redirect URL
redirect_uri = f'https://s45zbyckyzejd52pj4jgq3floe0znjfl.lambda-url.eu-west-2.on.aws'

# Spotify Setup
client_id = os.environ['CLIENT_ID']
client_secret = os.environ['CLIENT_SECRET']
SpotifyApp = Spotify.Application(client_id, client_secret, redirect_uri + '/callback')

def CreateResponse(status_code, data, content_type):
    return {
        "statusCode": status_code,
        "headers": {
            "content-type": content_type
        },
        "body": data,
        "isBase64Encoded": False
    }

def GenerateRandomString(length: int):
    characters = list(string.ascii_letters + string.digits)
    random.shuffle(characters)

    letters = []
    for i in range(length):
        letters.append(random.choice(characters))

    random.shuffle(letters)
    return "".join(letters)

# Get All Tracks from playlists array
def GetTracksFromPlaylists(playlists):
    tracks = []
    #album_names = ''

    for p in playlists:
        #album_names = album_names + p.GetName() + ", "

        songs = p.GetTracks()
        for s in songs:
            tracks.append(s.URI)

    #album_names = album_names[:-2] + "."
    return tracks
    #AddTracksToPlaylist(final_playlist, tracks)

def AddTracksToPlaylist(playlist, tracks):
    request_list = [tracks[i:i + 100] for i in range(0, len(tracks), 100)]
    for uri in request_list:
        playlist.AddTracks(uri)

class RequestHandler:
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
    def __init__(self, queries, path):
        self.Queries = queries
        self.Path = path

    def GetQuery(self, name):
        if self.Queries.get(name):
            return self.Queries[name]
        return None

    def do_POST(self):
        # 'Create Playlist' form submitted
        if self.Path == "/submit":
            key = self.GetQuery('user')
            user = Spotify.User(key)
            #user = SpotifyApp.GetUserFromKey(key)
            
            self.MashupFromQuery(user, queries)
            self.Content = self.Redirect(redirect_uri + f'?user={key}')
    
    def do_GET(self):
        
        # 'Create Playlist' form submitted
        if self.Path == "/submit":
            key = self.GetQuery('user')
            user = Spotify.User(key)
            #user = SpotifyApp.GetUserFromKey(key)
            
            self.MashupFromQuery(user, queries)
            self.Content = self.Redirect(redirect_uri + f'?user={key}')
            
        # Redirect from form submit
        elif self.Queries.get('user'):
            key = self.GetQuery('user')
            user = Spotify.User(key)
            #user = SpotifyApp.GetUserFromKey(key)
            
            try:
                albums = user.GetPlaylists()
                self.Content = self.ShowPlaylists(albums, key, user.AccessToken)
            except Exception as error:
                print("Redirecting user due to error:", error)
                self.Content = self.Redirect(redirect_url)

        # User logged in (authorization code sent)
        elif self.Path == "/callback":
            code = self.GetQuery('code')
            user = SpotifyApp.GetUser(code)

            #Identify user by key instead of access_token (for security reasons)
            #key = GenerateRandomString(32)
            #SpotifyApp.CreateUserKey(user, key)
            
            self.Content = self.Redirect(redirect_uri + f'?user={user.AccessToken}')

        # Redirect to login
        else:
            self.Content = self.Redirect(SpotifyApp.GetRedirectURL())

    def Redirect(self, url):
        return f'<html><meta http-equiv="refresh" content="0; url={url}"/></html>'

    def MashupFromQuery(self, user, query):
        if not query.get('playlist_name'):
            return None
            
        tracks = []
        
        # Add tracks from Query
        track_query = query.get('tracks')
        if track_query:
            track_ids = track_query.split(',');
            tracks += [Spotify.Track(id, user).URI for id in track_ids]
            
        # Add tracks from queried playlists
        playlist_query = query.get('playlists')
        if playlist_query:
            playlist_ids = playlist_query.split(',')
            playlists = [Spotify.Playlist(id, user) for id in playlists]            
            tracks += GetTracksFromPlaylists(playlists)
        
        # Create Playlist
        print("Adding", len(tracks), "tracks to playlist", self.GetQuery('playlist_name'))
        playlist = user.CreatePlaylist(query.get('playlist_name'), "")
        AddTracksToPlaylist(playlist, tracks)
        return playlist

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

    
        # File Information
        bucket_name = "galactickittenss"
        file_name = "index.html"

        # Amazon S3
        s3 = boto3.resource('s3',region_name='eu-west-2', aws_access_key_id='AKIARELLV3ZAPGKQHHFI', aws_secret_access_key='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')
        obj = s3.Object(bucket_name, file_name)
        html = str(obj.get()['Body'].read(), encoding='utf-8')
        logging.debug(html)

        html = html.replace('{body}', body)
        html = html.replace('{key}', key)
        html = html.replace('{token}', access_token)
        return html


logging.basicConfig(level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)s: %(message)s", datefmt='%H:%M:%S')

# event: JSON data
# context: AWS object
def lambda_handler(event, context):
    if not event.get('requestContext'):
        return CreateResponse(502, { "Error message": "Invalid request structure" }, "application/json")
    
    requestContext = event['requestContext']
    if not requestContext.get('http'):
        return CreateResponse(502, { "Error message": "Invalid request structure" }, "application/json")

    http = requestContext['http']
    if not http.get('method'):
        return CreateResponse(502, { "Error message": "Invalid request structure" }, "application/json")
    
    queries = {}
    if event.get('queryStringParameters'):
        queries = event['queryStringParameters']
        print(queries)

    handler = RequestHandler(queries, event['rawPath'])
    
    method = http['method']
    if method == "GET":
        handler.do_GET()

    if method == "POST":
        handler.do_POST()

    return CreateResponse(200, handler.Content, "text/html")
