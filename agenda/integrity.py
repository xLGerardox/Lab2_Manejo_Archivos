"""Integridad del archivo de contactos"""

import hashlib
import os

from .errors import FileAccessError

OK = "ok"
MISMATCH = "mismatch"
NO_HASH = "no_hash"
NO_FILE = "no_file"


def sha256_file(path):
    """Calcula el SHA-256 leyendo el archivo solo por bloques..."""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                digest.update(block)
    except FileNotFoundError as exc:
        raise FileAccessError(f"No existe {path}.") from exc
    except PermissionError as exc:
        raise FileAccessError(f"Sin permisos para leer {path}") from exc
    return digest.hexdigest()


def save_hash(data_path, hash_path):
    """Calcula y guarda el hash"""
    value = sha256_file(data_path)
    try:
        with open(hash_path, "w", encoding="utf-8") as f:
            f.write(f"{value}  {os.path.basename(data_path)}\n")
    except OSError as exc:
        raise FileAccessError(f"No se pudo guardar {hash_path}: {exc}") from exc
    return value


def read_saved_hash(hash_path):
    try:
        with open(hash_path, "r", encoding="utf-8") as f:
            parts = f.read().split()
        return parts[0] if parts else None
    except (FileNotFoundError, UnicodeDecodeError):
        return None
    except OSError as exc:
        raise FileAccessError(f"No se pudo leer {hash_path}: {exc}") from exc


def verify(data_path, hash_path):
    """Compara el hash guardado con el actual

    Devuelve (estado, hash_guardado, hash_actual)
    """
    if not os.path.exists(data_path):
        return NO_FILE, None, None
    saved = read_saved_hash(hash_path)
    if saved is None:
        return NO_HASH, None, sha256_file(data_path)
    current = sha256_file(data_path)
    return (OK if saved == current else MISMATCH), saved, current