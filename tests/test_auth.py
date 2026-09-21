from contextlib import contextmanager
from unittest.mock import patch

import pytest
import requests

from driveflow.auth import Auth, AuthError, DesktopFlow, LIMITED, safe_auth_error
from google_auth_oauthlib.flow import InstalledAppFlow


CONFIG = {'installed': {'client_id': 'test.apps.googleusercontent.com', 'client_secret': 'test-secret',
                       'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                       'token_uri': 'https://oauth2.googleapis.com/token', 'redirect_uris': ['http://localhost']}}


def flow():
    return DesktopFlow.from_client_config(CONFIG, LIMITED)


def scope_warning(scopes):
    warning = Warning('Scope changed')
    warning.token = {'access_token': 'private-test-token', 'token_type': 'Bearer', 'scope': ' '.join(scopes)}
    return warning


def test_previously_granted_extra_scope_does_not_break_login():
    client = flow()
    with patch.object(InstalledAppFlow, 'fetch_token', side_effect=scope_warning(LIMITED + ['openid'])):
        token = client.fetch_token(code='test')
    assert token['access_token'] == 'private-test-token'
    assert client.oauth2session.token == token


def test_missing_requested_scope_is_rejected():
    client = flow()
    with patch.object(InstalledAppFlow, 'fetch_token', side_effect=scope_warning(['openid'])):
        with pytest.raises(AuthError, match='AUTH_SCOPE_MISSING'):
            client.fetch_token(code='test')


def test_other_oauth_warning_is_not_ignored():
    with patch.object(InstalledAppFlow, 'fetch_token', side_effect=Warning('other')):
        with pytest.raises(Warning):
            flow().fetch_token(code='test')


@pytest.mark.parametrize('reason', ['accessNotConfigured', 'SERVICE_DISABLED'])
def test_disabled_drive_api_has_actionable_error(tmp_path, monkeypatch, reason):
    monkeypatch.setenv('DRIVEFLOW_DATA_DIR', str(tmp_path))
    auth = Auth()
    class Response:
        status_code = 403
        def json(self):
            return {'error': {'details': [{'reason': reason}]}}
    class Session:
        def get(self, *args, **kwargs):
            return Response()
    @contextmanager
    def session():
        yield Session()
    auth.session = session
    with pytest.raises(AuthError, match='AUTH_DRIVE_API_DISABLED'):
        auth.identify()
    assert auth.account_id == ''
    assert not auth.path.exists()


def test_browser_message_does_not_claim_connection_before_api_check(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv('DRIVEFLOW_DATA_DIR', str(tmp_path))
    config = tmp_path / 'client.json'
    config.write_text(json.dumps(CONFIG))
    auth = Auth()
    with patch.object(DesktopFlow, 'run_local_server', return_value=object()) as local_server:
        with patch.object(auth, 'identify', side_effect=AuthError('API desativada [AUTH_DRIVE_API_DISABLED]')):
            with pytest.raises(AuthError, match='AUTH_DRIVE_API_DISABLED'):
                auth.login(config)
    assert 'DriveFlow conectado' not in local_server.call_args.kwargs['success_message']
    assert auth.credentials is None and auth.account_id == ''


def test_diagnostics_do_not_include_request_secrets():
    error = requests.exceptions.ConnectionError('https://oauth2.googleapis.com/token?code=private-secret')
    result = str(safe_auth_error('Obter autorização', error))
    assert 'private-secret' not in result
    assert 'AUTH_ConnectionError' in result
