from urllib.parse import urlencode
import requests
from base64 import b64encode


class Track:

  def __init__(self, id, app):
    self.ID = id
    self.URI = f"spotify:track:{self.ID}"
    self.Application = app
    self.Name = None
    self.Type = 'tracks'

  def FromResponse(response, app):
    track = Track(response['id'], app)
    track.Name = response['name']
    return track

  def GetName(self):
    return self.Name


class Album:

  def __init__(self, id, app):
    self.ID = id
    self.URI = f"spotify:album:{self.ID}"
    self.Application = app
    self.Name = None
    self.Image = None
    self.Type = 'albums'

  def FromResponse(response, app):
    if response.get('album'):
      response = response.get('album')

    album = Album(response['id'], app)
    album.Name = response['name']
    
    if len(response['images']) > 0:
        album.Image = response['images'][0]['url']
    
    return album

  def GetTracks(self):
    next_url = f"albums/{self.ID}/tracks"
    items = []

    while next_url:
      response = self.Application.__request__(
          next_url.replace(User.API_URL, ''))
      next_url = response.get('next')
      items += response.get('items')

    return [Track.FromResponse(r['track'], self.Application) for r in items]

  def GetName(self):
    if not self.Name:
      url = f"albums/{self.ID}"
      response = self.Application.__request__(url)
      self.Name = response['name']

    return self.Name


class Playlist:

  def __init__(self, id, app):
    self.ID = id
    self.URI = f"spotify:playlist:{self.ID}"
    self.Application = app
    self.Name = None
    self.Image = None
    self.Type = 'playlists'

  def FromResponse(response, app):
    if response.get('album'):
      response = response.get('album')

    playlist = Playlist(response['id'], app)
    playlist.Name = response['name']
    
    if len(response['images']) > 0:
        playlist.Image = response['images'][0]['url']
    
    return playlist

  def GetTracks(self):
    next_url = f"playlists/{self.ID}/tracks"
    items = []

    while next_url:
      response = self.Application.__request__(
          next_url.replace(User.API_URL, ''))
      next_url = response.get('next')
      items += response.get('items')

    return [Track.FromResponse(r['track'], self.Application) for r in items]

  def AddTracks(self, uris):
    url = f"playlists/{self.ID}/tracks"
    request_headers = {'Content-Type': 'application/json'}
    request_payload = {
        'uris': uris,
    }
    return self.Application.__post__(url, request_headers, request_payload)

  def GetName(self):
    if not self.Name:
      url = f"playlists/{self.ID}"
      response = self.Application.__request__(url)
      self.Name = response['name']

    return self.Name


class User:
  API_URL = "https://api.spotify.com/v1/"

  def __init__(self, access_token):
    self.AccessToken = access_token

  def GetPlaylists(self):
    next_url = "me/playlists/"
    playlists = []

    while next_url:
      response = self.__request__(next_url.replace(User.API_URL, ''))
      next_url = response.get('next')
      playlists += response.get('items')

    playlists = [Playlist.FromResponse(r, self) for r in playlists]

    next_url = "me/albums/"
    albums = []

    while next_url:
      response = self.__request__(next_url.replace(User.API_URL, ''))
      next_url = response.get('next')
      albums += response.get('items')

    albums = [Album.FromResponse(r, self) for r in albums]
    
    return playlists + albums 

  def FindPlaylist(self, id):
    return Playlist(id, self)

  def CreatePlaylist(self, playlist_name: str, playlist_description: str):
    request_headers = {'Content-Type': 'application/json'}
    request_payload = {
        'name': playlist_name,
        'description': playlist_description,
        'public': False
    }

    response = self.__post__("me/playlists", request_headers, request_payload)
    return Playlist(response['id'], self)

  def GenericRequest(self, url: str):
    return self.__request__(url)

  def __post__(self, url: str, headers: dict, data):
    url = User.API_URL + url
    headers['Authorization'] = f'Bearer {self.AccessToken}'
    response = requests.post(url, headers=headers, json=data)
    response_content = response.json()

    if response.status_code != 200 and response.status_code != 201:
      raise Exception(response_content['error'])

    return response_content

  def __request__(self, url: str, headers: dict = {}):
    url = User.API_URL + url
    headers['Authorization'] = f'Bearer {self.AccessToken}'
    response = requests.get(url, headers=headers)
    response_content = response.json()

    if response.status_code != 200:
      raise Exception(response_content['error'])

    return response_content


class Application:
  Users = []

  def __init__(self, client_id, client_secret, redirect_uri):
    self.ClientID = client_id
    self.ClientSecret = client_secret
    self.RedirectURI = redirect_uri
    self.AccessToken = self.__get_client_access_token(client_id, client_secret)

  def GetUser(self, authorization_code):
    return User(self._get_access_token(authorization_code))

  def CreateUserKey(self, user, key):
    self.Users.append((key, user))

  def GetUserFromKey(self, key):
    for k, u in self.Users:
      if k == key:
        return u
    return None

  def GetRedirectURL(self):
    request_payload = {
        "client_id": self.ClientID,
        "response_type": "code",
        "redirect_uri": self.RedirectURI,
        "scope":
        "playlist-read-private playlist-modify-private user-library-read",
        'show_dialog': False
    }

    encoded_payload = urlencode(request_payload)
    url = 'https://accounts.spotify.com/authorize?' + encoded_payload
    return url

  def _get_access_token(self, authorization_code):
    request_payload = {
        "client_id": self.ClientID,
        "client_secret": self.ClientSecret,
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": self.RedirectURI
    }

    response = requests.post('https://accounts.spotify.com/api/token',
            data=request_payload).json()

    if response.get('access_token'):
      return response['access_token']
    else:
      raise Exception("Access Token Error", response['error_description'])
    
  def __get_client_access_token(self, client_id, client_secret):
    headers = { 
      'Authorization': 'Basic ' + b64encode((client_id + ':' + client_secret).encode('ascii')).decode('ascii'),
      'Content-Type': 'application/x-www-form-urlencoded',
    }
    response = requests.post('https://accounts.spotify.com/api/token?grant_type=client_credentials', headers=headers)
    return response.json()['access_token']

  def __request__(self, url: str, headers: dict = {}):
    url = User.API_URL + url
    headers['Authorization'] = f'Bearer {self.AccessToken}'
    response = requests.get(url, headers=headers)
    response_content = response.json()

    if response.status_code != 200:
      raise Exception(response_content['error'])

    return response_content
