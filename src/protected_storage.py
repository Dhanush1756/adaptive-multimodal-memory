"""Opt-in local encrypted workspace snapshots using cryptography Fernet.

SQLite operates only in RAM. A process holds an OS file lock for the workspace;
another session must close/reconnect rather than risk lost-update snapshots.
Not SQLCipher, E2EE, scalable storage, or protection against a running-process attack.
"""
import base64
import os
from pathlib import Path
from uuid import uuid4


class ProtectionError(ValueError):
    pass


class EncryptedWorkspace:
    def __init__(self, path, account_id):
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives.kdf.hkdf import HKDF
            from cryptography.hazmat.primitives import hashes
            key = base64.urlsafe_b64decode(os.environ.get('AEGM_DATA_KEY','').encode())
            if len(key) != 32:raise ValueError()
            derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                info=('aegm-account-v1:'+account_id).encode()).derive(key)
            self.cipher = Fernet(base64.urlsafe_b64encode(derived))
        except Exception:
            raise ProtectionError('Encrypted storage requires cryptography and a valid external AEGM_DATA_KEY; no plaintext fallback.') from None
        self.path = Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock = self.path.with_suffix('.lock').open('a+b')
        try:
            self.lock.seek(0)
            if os.name == 'nt':
                import msvcrt
                if self.lock.read(1) == b'':self.lock.write(b'0');self.lock.flush()
                self.lock.seek(0);msvcrt.locking(self.lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            raise ProtectionError('Encrypted workspace is already open. Close its other session before reconnecting.') from None

    def decrypt(self, data):
        try:return self.cipher.decrypt(data)
        except Exception:raise ProtectionError('Encrypted data could not be authenticated; check the key and backup. Nothing was overwritten.') from None

    def load(self):
        return self.decrypt(self.path.read_bytes()) if self.path.exists() else None

    def save(self, data):
        encrypted = self.cipher.encrypt(data)
        temporary = self.path.with_name(self.path.name+'.'+uuid4().hex+'.tmp')
        try:
            with temporary.open('xb') as stream:
                stream.write(encrypted);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def close(self):
        if not self.lock.closed:self.lock.close()
