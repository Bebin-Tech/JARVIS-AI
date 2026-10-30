"""Windows Credential Manager only; no plaintext fallback."""

import sys


def vault():
    if sys.platform != "win32":
        raise ValueError("Secure credential storage requires Windows Credential Manager")
    from keyring.backends.Windows import WinVaultKeyring

    return WinVaultKeyring()


def get_secret(name: str):
    try:
        return vault().get_password("JARVIS AI", name) or ""
    except Exception:
        return ""


def set_secret(name: str, value: str):
    try:
        backend = vault()
        if value:
            backend.set_password("JARVIS AI", name, value)
        elif backend.get_password("JARVIS AI", name):
            backend.delete_password("JARVIS AI", name)
    except Exception as error:
        raise ValueError("Windows Credential Manager could not save the key") from error
