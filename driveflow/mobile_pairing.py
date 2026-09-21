"""Administrative pairing operations; called only from UI background tasks."""
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone

from .firebase_monitor import FirestoreWriter


class PairingError(ValueError):
    pass


def pairing_payload(project, computer_id, name, token):
    return json.dumps(dict(type='driveflow-pair', version=2, project=project,
                           computer_id=computer_id, name=name, token=token), ensure_ascii=False)


class PairingService:
    def __init__(self, config, log, writer_factory=FirestoreWriter):
        self.config, self.log, self.factory = config, log, writer_factory

    def _perform(self, action):
        writer = None
        try:
            if not self.config.get('enabled'):
                raise PairingError('Ative e salve o monitoramento remoto primeiro.')
            writer = self.factory(self.config)
            return action(writer)
        except PairingError:
            raise
        except Exception as exc:
            self.log('', f'MOBILE_PAIRING_ERROR type={type(exc).__name__}')
            raise PairingError('Não foi possível acessar o Firebase. Confira a conexão, a credencial e as permissões.') from None
        finally:
            if writer:
                try:
                    writer.close()
                except Exception:
                    pass

    def create_code(self):
        def action(writer):
            token = secrets.token_urlsafe(32)
            digest = hashlib.sha256(token.encode()).hexdigest()
            expires = datetime.now(timezone.utc) + timedelta(minutes=5)
            writer.client.collection('pairing_codes').document(digest).set(dict(
                computer_id=self.config['computer_id'], computer_name=self.config['computer_name'],
                expiresAt=expires, protocol='spark-v2'), timeout=5, retry=None)
            payload = pairing_payload(writer.client.project, self.config['computer_id'], self.config['computer_name'], token)
            return payload, expires, digest
        return self._perform(action)

    def cancel_code(self, digest):
        return self._perform(lambda writer: writer.client.collection('pairing_codes').document(digest).delete(timeout=5, retry=None))

    def readers(self):
        def action(writer):
            docs = writer.client.collection('computers').document(self.config['computer_id']).collection('readers').stream(timeout=5, retry=None)
            return [(d.id, d.to_dict().get('deviceName', 'Android')) for d in docs]
        return self._perform(action)

    def revoke(self, uid):
        def action(writer):
            ident = self.config['computer_id']
            batch = writer.client.batch()
            batch.delete(writer.client.collection('readers').document(uid).collection('computers').document(ident))
            batch.delete(writer.client.collection('computers').document(ident).collection('readers').document(uid))
            batch.commit(timeout=5, retry=None)
        return self._perform(action)
