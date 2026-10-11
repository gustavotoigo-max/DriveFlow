import re
import threading

import requests

API = 'https://api.callmebot.com/whatsapp.php'
# Statuses that mean a file of the folder is still going to be sent in this batch.
ACTIVE = {'aguardando', 'iniciando', 'enviando', 'retomando'}


class WhatsAppError(Exception):
    pass


def normalize(phone):
    return re.sub(r'\D', '', phone or '')


def folder_label(folder_name):
    name = [x for x in (folder_name or '').replace(' / ', '/').split('/') if x.strip()]
    return name[-1].strip() if name else 'Meu Drive'


def batch_name(item):
    """Pasta escolhida para o envio: a pasta marcada, a origem da compactação ou o destino."""
    return item.get('notify_name') or folder_label(item.get('folder_name'))


def message(name):
    return f'{name} UPLOAD FINALIZADO'


def send(phone, apikey, text, http=requests):
    try:
        response = http.get(API, params={'phone': phone, 'text': text, 'apikey': apikey}, timeout=30)
    except requests.RequestException as exc:
        raise WhatsAppError('Sem conexão com o CallMeBot.') from exc
    text = ' '.join(re.sub(r'<[^>]+>', ' ', response.text or '').split())
    body = text.lower()
    if 'queued' in body or 'message sent' in body:
        return
    # O CallMeBot responde páginas HTML; o motivo vem no texto.
    if response.status_code != 200 or any(x in body for x in ('apikey', 'invalid', 'not activated', 'error')):
        raise WhatsAppError(f'CallMeBot recusou o envio (HTTP {response.status_code}): {text[:200] or "sem resposta"}')


def finished_folders(rows, newly_done):
    """Lotes cujo último upload ativo acabou de terminar."""
    names = []
    for item in newly_done:
        key = (item['account'], batch_name(item))
        if key[1] not in names and not any((x['account'], batch_name(x)) == key and x['status'] in ACTIVE for x in rows):
            names.append(key[1])
    return names


class Notifier:
    def __init__(self, db, http=requests):
        self.db, self.http = db, http

    def config(self):
        config = self.db.setting('whatsapp')
        return config if isinstance(config, dict) else {'enabled': False, 'recipients': []}

    def recipients(self):
        result = []
        for row in self.config().get('recipients', []):
            try:
                result.append((row['phone'], self.db.vault.open(row['apikey'])))
            except Exception:
                self.db.event('', f'WHATSAPP_KEY_UNREADABLE phone=…{row.get("phone", "")[-4:]}')
        return result

    def save(self, enabled, recipients):
        self.db.save_setting('whatsapp', {'enabled': bool(enabled), 'recipients': [
            {'phone': normalize(phone), 'apikey': self.db.vault.seal(apikey.strip())} for phone, apikey in recipients]})

    def uploads_completed(self, rows, newly_done):
        if not newly_done or not self.config().get('enabled'):
            return
        for name in finished_folders(rows, newly_done):
            self.notify(message(name))

    def notify(self, text, recipients=None, wait=False):
        targets = self.recipients() if recipients is None else recipients
        errors = []

        def run():
            for phone, apikey in targets:
                try:
                    send(phone, apikey, text, self.http)
                    self.db.event('', f'WHATSAPP_SENT phone=…{phone[-4:]}')
                except WhatsAppError as exc:
                    errors.append(f'{phone}: {exc}')
                    self.db.event('', f'WHATSAPP_ERROR phone=…{phone[-4:]} reason={exc}')
        if wait:
            run()
            return errors
        threading.Thread(target=run, daemon=True, name='whatsapp').start()
        return errors
