import json
import threading
from pathlib import Path
import requests

from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError, TransportError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .storage import Vault, data_dir
from .drive import TemporaryError

LIMITED = ['https://www.googleapis.com/auth/drive.file']
FULL = ['https://www.googleapis.com/auth/drive']
# Desktop OAuth client copied into the build by DriveFlow.spec. Google treats
# installed-app secrets as non-confidential, but the file stays out of Git.
BUNDLED_CLIENT = Path(__file__).with_name('oauth_client.json')


class AuthError(ValueError):
    """Only curated, credential-free messages may be displayed or logged."""


class AccountSession(requests.Session):
    """Serialize credential refresh only; uploads keep independent HTTP sessions."""
    def __init__(self, owner, credentials):
        super().__init__()
        self.owner, self.credentials = owner, credentials

    def request(self, method, url, **kwargs):
        headers = dict(kwargs.pop('headers', {}) or {})
        for attempt in range(2):
            with self.owner.lock:
                self.owner.authorize(self.credentials)
                self.credentials.apply(headers)
                token = self.credentials.token
            response = super().request(method, url, headers=headers, **kwargs)
            if response.status_code != 401:
                return response
            response.close()
            if attempt:
                with self.owner.lock:
                    if self.credentials is self.owner.credentials:
                        self.owner.reauth_required = True
                raise AuthError('O Google recusou a autorização após renovação. Reconecte a conta. [AUTH_HTTP_401]')
            self.owner.authorize(self.credentials, rejected_token=token)


class DesktopFlow(InstalledAppFlow):
    def fetch_token(self, **kwargs):
        kwargs.setdefault('timeout', 30)
        try:
            return super().fetch_token(**kwargs)
        except Warning as warning:
            # OAuthlib raises before assigning the token if Google returns a
            # different scope set. Accept a superset only; never bypass state,
            # PKCE, TLS or a missing requested permission.
            token = getattr(warning, 'token', None)
            if not isinstance(token, dict) or not token.get('access_token'):
                raise
            granted = token.get('scope', '')
            granted = set(granted.split() if isinstance(granted, str) else granted)
            if not set(self.oauth2session.scope or []) <= granted:
                raise AuthError('O Google não concedeu todas as permissões solicitadas. Conecte novamente e autorize o acesso ao Drive. [AUTH_SCOPE_MISSING]') from None
            self.oauth2session.token = dict(token)
            return self.oauth2session.token


def safe_auth_error(stage, exc):
    if isinstance(exc, AuthError):
        return exc
    if isinstance(exc, RefreshError) and any(isinstance(arg, dict) and arg.get('error') == 'invalid_grant' for arg in exc.args):
        return AuthError('O Google expirou ou revogou a autorização. Reconecte a conta. Projetos OAuth externos em modo Teste podem expirar em 7 dias. A credencial local e a fila foram preservadas. [AUTH_REAUTH_REQUIRED]')
    if isinstance(exc, RefreshError) and not exc.retryable:
        return AuthError('O Google recusou a renovação da autorização. Confira a credencial OAuth e reconecte a conta. [AUTH_REFRESH_REJECTED]')
    if isinstance(exc, requests.exceptions.SSLError):
        detail = 'Falha ao validar o certificado HTTPS. Verifique data/hora do Windows e eventual inspeção HTTPS do antivírus ou proxy.'
    elif isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        detail = 'Não foi possível alcançar o Google. Verifique a conexão e tente novamente.'
    elif isinstance(exc, OSError):
        detail = 'O Windows não conseguiu acessar o arquivo, abrir a conexão local ou salvar a credencial.'
    else:
        code = getattr(exc, 'error', '')
        detail = {
            'access_denied': 'A autorização foi recusada. Confira a conta e os usuários de teste no projeto Google Cloud.',
            'invalid_grant': 'A autorização expirou ou já foi utilizada. Inicie uma nova conexão.',
            'invalid_client': 'O Google recusou o cliente OAuth. Importe o JSON correto de Aplicativo para computador.',
            'redirect_uri_mismatch': 'A credencial não aceita o retorno local. Use um cliente OAuth de Aplicativo para computador.',
        }.get(code, 'A operação não foi concluída. Informe o código abaixo para diagnosticar.')
    return AuthError(f'{stage}: {detail} [AUTH_{type(exc).__name__}]')


def bundled_client():
    """Return the client embedded in this build, or None to ask for a JSON."""
    try:
        config = json.loads(BUNDLED_CLIENT.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    client = config.get('installed') if isinstance(config, dict) else None
    if not isinstance(client, dict) or not client.get('client_id') or not client.get('client_secret'):
        return None
    return config


class Auth:
    def __init__(self):
        self.path = data_dir() / 'account.bin'
        self.vault = Vault()
        self.lock = threading.RLock()
        self.credentials = None
        self.email = ''
        self.account_id = ''
        self.reauth_required = False
        self.save_pending = False

    def save(self):
        with self.lock:
            payload = json.loads(self.credentials.to_json())
            payload['driveflow_account'] = {'email': self.email, 'id': self.account_id}
            raw = self.vault.seal(json.dumps(payload))
            temp = self.path.with_suffix('.tmp')
            temp.write_text(raw, encoding='utf-8')
            temp.replace(self.path)

    def restore(self):
        if not self.path.exists():
            return False
        self.credentials = None
        try:
            payload = json.loads(self.vault.open(self.path.read_text(encoding='utf-8')))
            self.credentials = Credentials.from_authorized_user_info(payload)
            account = payload.get('driveflow_account', {})
            self.email, self.account_id = account.get('email', ''), account.get('id', '')
            # New saves can restore offline. Legacy credentials are upgraded
            # after the first successful account lookup, without another OAuth.
            if not self.email or not self.account_id:
                self.identify()
        except Exception as exc:
            if self.credentials is None:
                self.reauth_required = True
            self.email = self.account_id = ''
            raise safe_auth_error('Restaurar conexão', exc) from None
        return True

    def login(self, client, full=False):
        """client: path of an imported JSON, or the bundled client config."""
        stage = 'Ler credencial do aplicativo'
        previous = self.credentials, self.email, self.account_id, self.reauth_required, self.save_pending
        try:
            config = client if isinstance(client, dict) else json.loads(Path(client).read_text(encoding='utf-8'))
            if 'installed' not in config:
                raise AuthError('Importe uma credencial OAuth do tipo Aplicativo para computador. [AUTH_CLIENT_TYPE]')
            flow = DesktopFlow.from_client_config(config, FULL if full else LIMITED, autogenerate_code_verifier=True)
            stage = 'Obter autorização do Google'
            self.credentials = flow.run_local_server(host='127.0.0.1', port=0, timeout_seconds=180,
                                                    authorization_prompt_message=None,
                                                    success_message='Resposta recebida do Google. Volte ao DriveFlow para conferir se a conexão foi concluída. Você pode fechar esta aba.',
                                                    access_type='offline', prompt='consent')
            stage = 'Consultar conta e salvar conexão'
            self.email = self.account_id = ''
            self.reauth_required = self.save_pending = False
            self.identify()
            self.reauth_required = False
        except Exception as exc:
            self.credentials, self.email, self.account_id, self.reauth_required, self.save_pending = previous
            raise safe_auth_error(stage, exc) from None

    def session(self):
        with self.lock:
            if self.credentials is None:
                raise AuthError('Conecte sua conta Google. [AUTH_NOT_CONNECTED]')
            self.authorize(self.credentials)
            return AccountSession(self, self.credentials)

    def authorize(self, credentials, rejected_token=None):
        with self.lock:
            if credentials is not self.credentials or credentials is None:
                raise AuthError('A conta foi desconectada ou alterada. [AUTH_ACCOUNT_CHANGED]')
            if self.reauth_required:
                raise AuthError('Reconecte a conta: autorização recusada pelo Google. [AUTH_REAUTH_REQUIRED]')
            if not credentials.valid or (rejected_token is not None and credentials.token == rejected_token):
                try:
                    with requests.Session() as transport:
                        request = Request(session=transport)
                        credentials.refresh(lambda **kwargs: request(**dict(kwargs, timeout=(15, 30))))
                except (TransportError, requests.RequestException):
                    raise TemporaryError('Falha temporária ao renovar a conexão Google. [AUTH_TRANSPORT]') from None
                except RefreshError as exc:
                    if exc.retryable:
                        raise TemporaryError('Google temporariamente indisponível para renovar a conexão. [AUTH_REFRESH_RETRYABLE]') from None
                    self.reauth_required = True
                    raise safe_auth_error('Renovar conexão', exc) from None
                self.save_pending = True
            if self.save_pending:
                try:
                    self.save()
                except OSError:
                    raise TemporaryError('Não foi possível salvar a credencial renovada. [AUTH_SAVE_RETRY]') from None
                self.save_pending = False

    def identify(self):
        with self.session() as session:
            response = session.get('https://www.googleapis.com/drive/v3/about', params={'fields': 'user(emailAddress,permissionId)'}, timeout=30)
            if response.status_code != 200:
                try:
                    error = response.json().get('error', {})
                    reasons = {e.get('reason') for e in error.get('errors', []) + error.get('details', [])}
                except (ValueError, AttributeError, TypeError):
                    reasons = set()
                if reasons & {'accessNotConfigured', 'SERVICE_DISABLED'}:
                    raise AuthError('A Google Drive API está desativada no projeto da credencial. Ative-a em Google Cloud → APIs e serviços → Biblioteca e tente conectar novamente. [AUTH_DRIVE_API_DISABLED]')
                if response.status_code == 403:
                    raise AuthError('O Google autorizou o login, mas negou a consulta ao Drive. Confira as permissões concedidas e possíveis restrições da organização. [AUTH_DRIVE_HTTP_403]')
                raise AuthError(f'Não foi possível consultar a conta no Google Drive. Tente novamente. [AUTH_DRIVE_HTTP_{response.status_code}]')
            user = response.json()['user']
            if not user.get('emailAddress') or not user.get('permissionId'):
                raise AuthError('A resposta do Drive não trouxe a identificação da conta. [AUTH_ACCOUNT_INCOMPLETE]')
            self.email, self.account_id = user['emailAddress'], user['permissionId']
            self.save()

    def logout(self):
        with self.lock:
            self.path.unlink(missing_ok=True)
            self.path.with_suffix('.tmp').unlink(missing_ok=True)
            self.credentials = None
            self.email = self.account_id = ''
            self.reauth_required = False
            self.save_pending = False
