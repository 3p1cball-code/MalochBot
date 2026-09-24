"""Sichere Ablage von Zugangsdaten.

Bevorzugt das Betriebssystem-Keyring (KWallet / Secret Service / Windows Credential
Manager). Ist kein Keyring verfuegbar, wird eine mit Fernet verschluesselte Datei
verwendet; der Schluessel liegt dann mit Rechten 0600 im Datenordner.
Niemals landen Geheimnisse im Repository.
"""

import base64
import json
import os
import stat

from . import config

SERVICE = "MalochBot"


def _try_keyring():
    try:
        import keyring
        from keyring.errors import KeyringError
        try:
            keyring.get_password(SERVICE, "__probe__")
            return keyring
        except Exception:
            return None
    except Exception:
        return None


class SecretStore:
    def __init__(self):
        self._keyring = _try_keyring()
        self._cache = None

    def _master_key(self) -> bytes:
        if self._keyring:
            value = self._keyring.get_password(SERVICE, "masterkey")
            if value:
                return base64.urlsafe_b64decode(value.encode())
        if config.KEY_FILE.exists():
            return base64.urlsafe_b64decode(config.KEY_FILE.read_bytes())
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        if self._keyring:
            self._keyring.set_password(SERVICE, "masterkey", base64.urlsafe_b64encode(key).decode())
        else:
            config.KEY_FILE.write_bytes(base64.urlsafe_b64encode(key))
            os.chmod(config.KEY_FILE, stat.S_IRUSR | stat.S_IWUSR)
        return key

    def _fernet(self):
        from cryptography.fernet import Fernet
        return Fernet(self._master_key())

    def _load(self) -> dict:
        if self._cache is not None:
            return self._cache
        if config.SECRET_FILE.exists():
            try:
                data = self._fernet().decrypt(config.SECRET_FILE.read_bytes())
                self._cache = json.loads(data.decode())
            except Exception:
                self._cache = {}
        else:
            self._cache = {}
        return self._cache

    def _save(self) -> None:
        config.ensure_dirs()
        payload = json.dumps(self._cache or {}).encode()
        config.SECRET_FILE.write_bytes(self._fernet().encrypt(payload))
        try:
            os.chmod(config.SECRET_FILE, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

    def get(self, key: str, default: str = "") -> str:
        if self._keyring:
            try:
                value = self._keyring.get_password(SERVICE, key)
                if value is not None:
                    return value
            except Exception:
                pass
        return self._load().get(key, default)

    def set(self, key: str, value: str) -> None:
        if self._keyring:
            try:
                self._keyring.set_password(SERVICE, key, value)
                return
            except Exception:
                pass
        self._load()[key] = value
        self._save()

    def delete(self, key: str) -> None:
        if self._keyring:
            try:
                self._keyring.delete_password(SERVICE, key)
            except Exception:
                pass
        data = self._load()
        data.pop(key, None)
        self._save()

    def backend(self) -> str:
        return "keyring" if self._keyring else "verschluesselte Datei"


store = SecretStore()
