from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, urlencode, parse_qs
import requests

import os
from dotenv import load_dotenv
load_dotenv()

client_id = os.getenv('CLIENT_ID')
client_secret = os.getenv('CLIENT_SECRET')

hostName = "localhost"
serverPort = 3000
redirect_uri = f'http://{hostName}:{serverPort}'

class SpotifyAuth(BaseHTTPRequestHandler):
    authorization_code = None

    def _set_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

    def do_GET(self):
        self._set_headers()

        path = urlparse(self.path)
        if not path.query:
            request_payload = {
                "client_id": client_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "scope": "playlist-read-private playlist-modify-private"
            }

            encoded_payload = urlencode(request_payload)
            url = 'https://accounts.spotify.com/authorize?' + encoded_payload
            self.wfile.write(
                f'<html><meta http-equiv="refresh" content="0; url={url}"/></html>'
                .encode('utf-8'))
        else:
            query = parse_qs(path.query)

            if query.get('code'):
                SpotifyAuth.authorization_code = query['code']
                self.wfile.write(
                    f'<html><head><body>Authentication Code: {SpotifyAuth.authorization_code}</body></head>'
                    .encode('utf-8'))
            else:
                self.wfile.write(
                    f'<html><head><body>Error: {query["error_description"]}</body></head>'
                    .encode('utf-8'))
                raise Exception(query['error'], query['error_description'])

def GetAuthorizationCode():
    webServer = HTTPServer((hostName, serverPort), SpotifyAuth)
    while not SpotifyAuth.authorization_code:
        webServer.handle_request()

    webServer.server_close()
    return SpotifyAuth.authorization_code

def GetAccessToken(authorization_code):
    request_payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": GetAuthorizationCode(),
        "redirect_uri": redirect_uri
    }

    response = requests.post('https://accounts.spotify.com/api/token', data=request_payload).json()

    if response.get('access_token'):
        return response['access_token']
    else:
        raise Exception("Access Token Error", response['error_description'])

def Validate(access_token):
    #url = 'https://id.twitch.tv/oauth2/validate'
    #response = requests.get(url, headers={'Authorization': f'OAuth {access_token}'})
    return True #response.status_code == 200

if __name__ == "__main__":
    print(f'Please open your browser to {redirect_uri}')
    authorization_code = GetAuthorizationCode()

    access_token = GetAccessToken(authorization_code)
    print(f'Access Token: {access_token}')

    valid = Validate(access_token)
    print(f"Access Token Valid: {valid}")
