import os
import logging
import json
import boto3
import base64

from urllib.parse import parse_qsl

import string
import random

import Spotify

#Redirect URL
redirect_uri = f'https://minofhoodkvpeuntldj326inzq0lacnc.lambda-url.eu-west-2.on.aws'

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
            
            self.MashupFromQuery(user, self.Queries)
            self.Content = self.Redirect(redirect_uri + f'?user={key}')
    
    def do_GET(self):
        
        # 'Create Playlist' form submitted
        if self.Path == "/submit":
            key = self.GetQuery('user')
            user = Spotify.User(key)
            #user = SpotifyApp.GetUserFromKey(key)
            
            self.MashupFromQuery(user, self.Queries)
            self.Content = self.Redirect(redirect_uri + f'?user={key}')
            
        # Redirect from form submit
        elif self.Queries.get('user'):
            key = self.GetQuery('user')
            user = Spotify.User(key)
            #user = SpotifyApp.GetUserFromKey(key)
            
            if not user:
                self.Content = self.Redirect(redirect_uri)
            else:
                albums = user.GetPlaylists()
                self.Content = self.ShowPlaylists(albums, key, user.AccessToken)
        
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
            
        track_query = self.GetQuery('tracks')
        if track_query:
            tracks = track_query.split(',');
            track_uris = [Spotify.Track(id, user).URI for id in tracks]
            
            return CreateMashupFromTracks(user, 
                query.get('playlist_name'), "",
                track_uris
            )
        
        playlist_query = self.GetQuery('playlists')
        if playlist_query:
            playlists = playlist_query.split(',')
            spotify_playlists = [Spotify.Playlist(id, user) for id in playlists]
            
            return CreateMashupFromPlaylists(user, 
                query.get('playlist_name'),
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

    
        # File Information
        bucket_name = "galactickittenss"
        file_name = "Spotify.html"

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
    print("Received Event: ", event)

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

    elif event.get('body'):
        body = event['body']
        if event['isBase64Encoded'] == True:
            body = str(base64.b64decode(body), 'utf-8')
            print("Raw Decoded Body: ", body)
        
        queries = dict(parse_qsl(body))

    print("with arguments: ", queries)

    handler = RequestHandler(queries, event['rawPath'])
    
    method = http['method']
    if method == "GET":
        print("Handling GET Request")
        handler.do_GET()

    if method == "POST":
        print("Handling POST Request")
        handler.do_POST()

    return CreateResponse(200, handler.Content, "text/html")