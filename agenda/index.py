"""Índice primario, relaciona cada id de contacto con el número de registro
"""

import json
import os

from .errors import CorruptFileError, FileAccessError


class IndexFile:
    def __init__(self, path):
        self.path = path

    def exists(self):
        return os.path.exists(self.path)

    def load(self):
        """Devuelve {id: número_de_registro}. ERROR si no se pudiera abrir"""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            entries = data["entries"]
            return {int(k): int(v) for k, v in entries.items()}
        except FileNotFoundError as exc:
            raise FileAccessError(f"No existe el índice {self.path}.") from exc
        except PermissionError as exc:
            raise FileAccessError(f"Sin permisos sobre {self.path}.") from exc
        except (json.JSONDecodeError, KeyError, TypeError, ValueError,
                AttributeError, UnicodeDecodeError) as exc:
            raise CorruptFileError(f"El índice está corrupto: {exc}") from exc

    def save(self, mapping, record_size):
        """Guarda el índice temporal"""
        data = {
            "version": 1,
            "record_size": record_size,
            "entries": {str(k): v for k, v in sorted(mapping.items())},
        }
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except PermissionError as exc:
            raise FileAccessError(f"Sin permisos para escribir {self.path}.") from exc
        except OSError as exc:
            raise FileAccessError(f"No se pudo guardar el indice: {exc}") from exc