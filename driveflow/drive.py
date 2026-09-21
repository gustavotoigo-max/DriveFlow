import re
from urllib.parse import urlparse

import requests

API = 'https://www.googleapis.com/drive/v3'


class TemporaryError(Exception):
    pass


class DriveError(Exception):
    pass


class ExpiredSession(Exception):
    pass


class DuplicateName(Exception):
    pass


def escape(value):
    return value.replace('\\', '\\\\').replace("'", "\\'")


class Drive:
    def __init__(self, session):
        self.http = session

    def request(self, method, url, **kwargs):
        try:
            r = self.http.request(method, url, timeout=(15, 90), allow_redirects=False, **kwargs)
        except requests.RequestException:
            raise TemporaryError('Conexão interrompida ou tempo limite excedido.') from None
        if r.status_code == 429 or r.status_code >= 500:
            raise TemporaryError(f'Google temporariamente indisponível (HTTP {r.status_code}).')
        if r.status_code == 403:
            try:
                reasons = {x.get('reason') for x in r.json().get('error', {}).get('errors', [])}
            except (ValueError, AttributeError):
                reasons = set()
            if reasons & {'rateLimitExceeded', 'userRateLimitExceeded', 'backendError'}:
                raise TemporaryError('Limite temporário do Google. Aguardando nova tentativa.')
        return r

    def checked(self, r):
        if not 200 <= r.status_code < 300:
            raise DriveError(f'Google retornou HTTP {r.status_code}. Verifique acesso, espaço e limites da conta.')
        return r.json()

    def list_files(self, query):
        files, token = [], None
        while True:
            params = {'q': query, 'fields': 'nextPageToken,files(id,name,size,mimeType)', 'pageSize': 1000,
                      'supportsAllDrives': 'true', 'includeItemsFromAllDrives': 'true'}
            if token:
                params['pageToken'] = token
            data = self.checked(self.request('GET', API + '/files', params=params))
            files.extend(data.get('files', []))
            token = data.get('nextPageToken')
            if not token:
                return sorted(files, key=lambda x: x['name'].casefold())

    def folders(self, parent):
        return self.list_files(f"'{escape(parent)}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder'")

    def children(self, parent):
        rows = self.list_files(f"'{escape(parent)}' in parents and trashed=false")
        return sorted(rows, key=lambda x: (x['mimeType'] != 'application/vnd.google-apps.folder', x['name'].casefold()))

    def duplicates(self, parent, name):
        return self.list_files(f"'{escape(parent)}' in parents and trashed=false and name='{escape(name)}'")

    def create_folder(self, parent, name):
        return self.checked(self.request('POST', API + '/files', params={'fields': 'id,name', 'supportsAllDrives': 'true'},
                                        json={'name': name, 'parents': [parent], 'mimeType': 'application/vnd.google-apps.folder'}))

    def generate_id(self):
        return self.checked(self.request('GET', API + '/files/generateIds', params={'count': 1, 'space': 'drive', 'type': 'files'}))['ids'][0]

    def metadata(self, ident):
        r = self.request('GET', API + '/files/' + ident, params={'fields': 'id,size,name,trashed,webViewLink', 'supportsAllDrives': 'true'})
        if r.status_code == 404:
            return None
        return self.checked(r)

    def start(self, item):
        r = self.request('POST', 'https://www.googleapis.com/upload/drive/v3/files',
                         params={'uploadType': 'resumable', 'fields': 'id,size', 'supportsAllDrives': 'true'},
                         headers={'X-Upload-Content-Type': 'application/octet-stream', 'X-Upload-Content-Length': str(item['size'])},
                         json={'id': item['remote_id'], 'name': item['name'], 'parents': [item['folder_id']]})
        if r.status_code not in (200, 201):
            self.checked(r)
        uri = r.headers.get('Location', '')
        self.validate_uri(uri)
        return uri

    @staticmethod
    def validate_uri(uri):
        parsed = urlparse(uri)
        if parsed.scheme != 'https' or parsed.hostname != 'www.googleapis.com' or parsed.port not in (None, 443) or parsed.username:
            raise DriveError('Endereço de sessão inválido.')

    def transfer(self, uri, size, offset=None, chunk=b''):
        self.validate_uri(uri)
        content_range = f'bytes */{size}' if offset is None or not chunk else f'bytes {offset}-{offset + len(chunk) - 1}/{size}'
        r = self.request('PUT', uri, headers={'Content-Length': str(len(chunk)), 'Content-Range': content_range,
                                            'Content-Type': 'application/octet-stream'}, data=chunk)
        if r.status_code in (404, 410):
            raise ExpiredSession()
        if r.status_code == 308:
            value = r.headers.get('Range')
            match = re.fullmatch(r'bytes=0-(\d+)', value) if value else None
            if value and not match:
                raise DriveError('Resposta de progresso inválida do Google.')
            received = int(match.group(1)) + 1 if match else 0
            if received > size:
                raise DriveError('Progresso remoto maior que o arquivo.')
            return received, False
        self.checked(r)
        return size, True
