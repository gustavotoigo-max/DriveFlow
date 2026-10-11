import requests

from driveflow.storage import Database
from driveflow.whatsapp import Notifier, WhatsAppError, batch_name, finished_folders, message, normalize, send


class FakeVault:
    def seal(self, value):
        return 'sealed:' + value if value else ''

    def open(self, value):
        return value.removeprefix('sealed:')


class Response:
    def __init__(self, text='Message queued.', status_code=200):
        self.text, self.status_code = text, status_code


class Http:
    def __init__(self, response=None):
        self.calls, self.response = [], response or Response()

    def get(self, url, params, timeout):
        self.calls.append(params)
        return self.response


def row(ident, status, folder='f1', name='Meu Drive/Clientes/Obra 12'):
    return {'id': ident, 'status': status, 'folder_id': folder, 'folder_name': name, 'account': 'acc'}


def test_message_uses_selected_folder_name():
    assert message(batch_name(row('a', 'x'))) == 'Obra 12 UPLOAD FINALIZADO'
    assert batch_name({'folder_name': 'Meu Drive / Fotos'}) == 'Fotos'
    assert batch_name({'folder_name': 'Meu Drive'}) == 'Meu Drive'
    # Pasta marcada ou compactada: o nome dela, não o da subpasta no Drive.
    assert batch_name({'folder_name': 'Meu Drive/Obras/Obra 12/fotos', 'notify_name': 'Obra 12'}) == 'Obra 12'
    assert normalize('+55 (11) 99999-8888') == '5511999998888'


def test_notifies_once_when_last_upload_of_folder_finishes():
    done_a, done_b = row('a', 'concluído'), row('b', 'concluído')
    assert finished_folders([done_a, row('b', 'aguardando')], [done_a]) == []
    assert finished_folders([done_a, done_b], [done_a, done_b]) == ['Obra 12']
    other = row('c', 'concluído', 'f2', 'Meu Drive/Fotos')
    assert sorted(finished_folders([done_a, other, row('d', 'pausado')], [done_a, other])) == ['Fotos', 'Obra 12']
    sub = dict(row('e', 'concluído', 'f3', 'Meu Drive/Obra 12/sub'), notify_name='Obra 12')
    assert finished_folders([sub, dict(row('f', 'enviando', 'f4', 'Meu Drive/Obra 12'), notify_name='Obra 12')], [sub]) == []
    compressing = {'account': 'acc', 'notify_name': 'Obra 12', 'status': 'aguardando'}
    assert finished_folders([sub, compressing], [sub]) == []


def test_send_reports_callmebot_errors():
    http = Http()
    send('5511999998888', 'k', 'Obra UPLOAD FINALIZADO', http)
    assert http.calls == [{'phone': '5511999998888', 'text': 'Obra UPLOAD FINALIZADO', 'apikey': 'k'}]
    send('1', 'k', 't', Http(Response('<p>Message queued. You will receive it in a few seconds.</p>', 203)))
    for response in (Response('APIKey is invalid', 200), Response('', 500), Response('<b>APIKey is invalid</b>', 203)):
        try:
            send('1', 'k', 't', Http(response))
            assert False
        except WhatsAppError:
            pass

    class Offline:
        def get(self, *args, **kwargs):
            raise requests.ConnectionError()
    try:
        send('1', 'k', 't', Offline())
        assert False
    except WhatsAppError:
        pass


def test_settings_are_sealed_and_notifications_sent(tmp_path):
    db = Database(tmp_path / 'q.sqlite3', FakeVault())
    http = Http()
    notifier = Notifier(db, http)
    notifier.save(True, [('+55 11 99999-8888', ' key1 '), ('5511888887777', 'key2')])
    assert db.setting('whatsapp')['recipients'][0] == {'phone': '5511999998888', 'apikey': 'sealed:key1'}
    assert notifier.recipients() == [('5511999998888', 'key1'), ('5511888887777', 'key2')]
    assert notifier.notify('Obra UPLOAD FINALIZADO', wait=True) == []
    assert [c['phone'] for c in http.calls] == ['5511999998888', '5511888887777']
    notifier.save(False, [('5511999998888', 'key1')])
    http.calls.clear()
    notifier.uploads_completed([row('a', 'concluído')], [row('a', 'concluído')])
    assert http.calls == []
