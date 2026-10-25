"""Respaldo comprimido (zipfile)"""

import os
import zipfile
from datetime import datetime

from .errors import FileAccessError


def create_backup(files, zip_path):
    """Crea un ZIP con ``files``. Devuelve (tamaño_original, tamaño_comprimido)."""
    original = 0
    try:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in files:
                original += os.path.getsize(path)
                zf.write(path, arcname=os.path.basename(path))
    except FileNotFoundError as exc:
        raise FileAccessError(f"Falta un archivo para el respaldo: {exc}") from exc
    except PermissionError as exc:
        raise FileAccessError(f"Sin permisos para crear el respaldo: {exc}") from exc
    except OSError as exc:
        raise FileAccessError(f"No se pudo crear el respaldo: {exc}") from exc
    return original, os.path.getsize(zip_path)


def file_info(path):
    """Tamaño, última modificación y permisos de lectura o escritura"""
    try:
        st = os.stat(path)
    except FileNotFoundError as exc:
        raise FileAccessError(f"No existe {path}.") from exc
    except OSError as exc:
        raise FileAccessError(f"No se pudo leer la información: {exc}") from exc
    return {
        "ruta": os.path.abspath(path),
        "tamano": st.st_size,
        "modificado": datetime.fromtimestamp(st.st_mtime),
        "lectura": os.access(path, os.R_OK),
        "escritura": os.access(path, os.W_OK),
    }