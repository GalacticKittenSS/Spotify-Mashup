import os
import logging
import json
import boto3
import base64

from urllib.parse import parse_qsl

import string
import random

import Spotify

# Redirect URL
redirect_url = os.environ['AWS_URL']

# AWS Bucket Info (Webpage src)
bucket_name = os.environ['AWS_BUCKET']
file_name = os.environ['AWS_FILEPATH']
preview_file = os.environ['AWS_PREVIEW']

# AWS Access Token
aws_id = os.environ['AWS_ID']
aws_secret = os.environ['AWS_SECRET']

# Spotify Setup
client_id = os.environ['CLIENT_ID']
client_secret = os.environ['CLIENT_SECRET']
SpotifyApp = Spotify.Application(client_id, client_secret, redirect_url + '/callback')

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
    def __init__(self, queries, path, headers):
        self.Queries = queries
        self.Path = path
        self.Headers = headers
        self.ContentType = "text/html"

    def GetQuery(self, name):
        if self.Queries.get(name):
            return self.Queries[name]
        return None

    def do_POST(self):
        # 'Create Playlist' form submitted
        if self.Path == "/submit":
            key = self.Headers.get('user')
            user = Spotify.User(key)
            
            try:
                playlist = self.MashupFromQuery(user, self.Queries)
                image = user.__request__(f'playlists/{playlist.ID}')['images'][0]
                self.Content = json.dumps({ 'playlist': {'name': playlist.GetName(), 'id': playlist.ID, 'image': image['url'] } })
            except Exception as error:
                print('Could not create mashup playlist due to error:', error)
                self.Content = json.dumps({ 'error': 'Could not create playlist' })

            self.ContentType = 'application/json'

    def do_GET(self):
        self.ContentType = "text/html"
        
        # GET tracks in playlist [JSON]
        if self.Path == "/tracks":
            key = self.Headers.get('user')
            user = Spotify.User(key)
            
            playlist_id = self.GetQuery('playlists_id')
            album_id = self.GetQuery('albums_id')

            tracks = []

            if playlist_id:
                playlist = Spotify.Playlist(playlist_id, user)
                tracks = playlist.GetTracks()

            elif album_id:
                album = Spotify.Album(album_id, user)
                tracks = album.GetTracks()

            # TODO: Use pages
            self.Content = json.dumps({ 'items': [{ "id": track.ID, "name": track.GetName() } for track in tracks], 'next': '' })
            self.ContentType = 'application/json'
        
        # 'Create Playlist' form submitted [JSON]
        elif self.Path == "/submit":
            key = self.Headers.get('user')
            user = Spotify.User(key)
            
            try:
                playlist = self.MashupFromQuery(user, self.Queries)
                image = user.__request__(f'playlists/{playlist.ID}')['images'][0]
                self.Content = json.dumps({ 'playlist': {'name': playlist.GetName(), 'id': playlist.ID, 'image': image['url'] } });
            except Exception as error:
                print('Could not create mashup playlist due to error:', error)
                self.Content = json.dumps({ 'error': 'Could not create playlist' })
            
            self.ContentType = 'application/json'

        # Redirect from User Login [HTML]
        elif self.Queries.get('user'):
            key = self.GetQuery('user')
            user = Spotify.User(key)
            
            try:
                albums = user.GetPlaylists()
                self.Content = self.ShowPlaylists(albums, key, user.AccessToken)
            except Exception as error:
                print("Redirecting user due to error:", error)
                self.Content = self.Redirect(redirect_url)

        # User logged in (authorization code sent) [HTML]
        elif self.Path == "/callback":
            code = self.GetQuery('code')
            user = SpotifyApp.GetUser(code)

            #Identify user by key instead of access_token (for security reasons)
            #key = GenerateRandomString(32)
            #SpotifyApp.CreateUserKey(user, key)
            
            self.Content = self.Redirect(redirect_url + f'?user={user.AccessToken}')

        # Preview website with Spotify's top playlist [HTML]
        elif self.Path == "/preview":
            response = SpotifyApp.__request__('browse/categories/toplists/playlists/')
            albums = [Spotify.Playlist.FromResponse(r, SpotifyApp) for r in response['playlists']['items']]
            self.Content = self.ShowPlaylists(albums, SpotifyApp.AccessToken, SpotifyApp.AccessToken)

        # Read File
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
            playlists = [Spotify.Playlist(id, user) for id in playlist_ids]            
            tracks += GetTracksFromPlaylists(playlists)
        
        # Create Playlist
        print("Creating playlist", self.GetQuery('playlist_name'), "with", len(tracks), "tracks");
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

        # Amazon S3
        s3 = boto3.resource('s3',region_name='eu-west-2', aws_access_key_id=aws_id, aws_secret_access_key=aws_secret)
        file = preview_file if self.Path == "/preview" else file_name
        obj = s3.Object(bucket_name, file)
        html = str(obj.get()['Body'].read(), encoding='utf-8')
        
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

    handler = RequestHandler(queries, event['rawPath'], event['headers'])
    
    method = http['method']
    if method == "GET":
        print("Handling GET Request")
        handler.do_GET()

    if method == "POST":
        print("Handling POST Request")
        handler.do_POST()

    return CreateResponse(200, handler.Content, handler.ContentType)
