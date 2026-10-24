"""Archivo de registros de tamaño fijo con acceso aleatorio.

Estructura del registro

    campo      largo   posición
    ---------  ------  --------
    id            6      0 -  5
    nombre       30      6 - 35
    telefono     15     36 - 50
    correo       30     51 - 80
    ciudad       18     81 - 98
    fin de línea  1     99
    ---------  ------
    TOTAL       100 bytes por registro

Cada campo se rellena con espacios a la derecha ya que siempre cae
al inicio del registro ``n``. Los largos se miden en bytes, no en
caracteres.
"""

import os

from .errors import CorruptFileError, FileAccessError, ValidationError

# (nombre del campoooo
FIELDS = [
    ("id", 6),
    ("nombre", 30),
    ("telefono", 15),
    ("correo", 30),
    ("ciudad", 18),
]
NEWLINE = b"\n"
RECORD_SIZE = sum(width for _, width in FIELDS) + len(NEWLINE)  # 100
ENCODING = "utf-8"

assert RECORD_SIZE == 100


def encode_record(contact):
    parts = []
    for name, width in FIELDS:
        value = str(contact.get(name, "")).strip()
        if "\n" in value or "\r" in value:
            raise ValidationError(f"El campo '{name}' no puede tener saltos de linea")
        raw = value.encode(ENCODING)
        if len(raw) > width:
            raise ValidationError(
                f"El campo '{name}' es muy largoooo "
                f"({len(raw)} bytes; máximo {width})."
            )
        parts.append(raw.ljust(width))  # relleno con los epsacios a la derecha
    record = b"".join(parts) + NEWLINE
    assert len(record) == RECORD_SIZE
    return record


def decode_record(raw):
    """Convierte RECORD_SIZE bytes en un dict de contacto..."""
    if len(raw) != RECORD_SIZE or not raw.endswith(NEWLINE):
        raise CorruptFileError("FORMATO INVALIDOOO")
    contact = {}
    offset = 0
    try:
        for name, width in FIELDS:
            contact[name] = raw[offset:offset + width].decode(ENCODING).strip()
            offset += width
        contact["id"] = int(contact["id"])
    except (UnicodeDecodeError, ValueError) as exc:
        raise CorruptFileError(f"Registro dañado: {exc}") from exc
    return contact


class RecordFile:
    """Lee y escribe registros usando seek() y tell()."""

    def __init__(self, path, log=None):
        self.path = path
        self._log = log or (lambda msg: None)

    # ---- utilidades -------------------------------------------------
    def ensure_exists(self):
        """Crea el archivo vacío si no existe."""
        try:
            if not os.path.exists(self.path):
                with open(self.path, "ab"):
                    pass
        except PermissionError as exc:
            raise FileAccessError(f"Sin permisos para crear {self.path}.") from exc
        except OSError as exc:
            raise FileAccessError(f"No se pudo crear {self.path}: {exc}") from exc

    def count(self):
        """Cantidad de registros (tamaño del archivo / tamaño del registro)."""
        try:
            size = os.path.getsize(self.path)
        except FileNotFoundError as exc:
            raise FileAccessError(f"No existe {self.path}.") from exc
        except OSError as exc:
            raise FileAccessError(f"No se pudo leer {self.path}: {exc}") from exc
        if size % RECORD_SIZE != 0:
            raise CorruptFileError(
                f"El tamaño del archivo ({size} bytes) no es múltiplo de "
                f"{RECORD_SIZE}: el archivo está corrupto."
            )
        return size // RECORD_SIZE

    def _open(self, mode):
        try:
            return open(self.path, mode)
        except FileNotFoundError as exc:
            raise FileAccessError(f"No existe el archivo {self.path}.") from exc
        except PermissionError as exc:
            raise FileAccessError(f"Sin permisos sobre {self.path}.") from exc
        except OSError as exc:
            raise FileAccessError(f"No se pudo abrir {self.path}: {exc}") from exc

    # ---- operaciones ------------------------------------------------
    def append(self, contact):
        """Agrega un registro al final. Devuelve su número de registro."""
        record = encode_record(contact)
        number = self.count()
        with self._open("r+b") as f:
            f.seek(0, os.SEEK_END)                      # ir al final
            self._log(f"seek(0, SEEK_END) -> tell() = {f.tell()}")
            f.write(record)
            f.flush()
            os.fsync(f.fileno())
            self._log(f"write({RECORD_SIZE} bytes) -> tell() = {f.tell()}")
        return number

    def read(self, number):
        """Lee el registro ``number`` sin recorrer el archivo."""
        total = self.count()
        if not 0 <= number < total:
            raise CorruptFileError(f"Registro {number} fuera de rango (0-{total - 1}).")
        with self._open("rb") as f:
            f.seek(number * RECORD_SIZE)                # salto directo
            self._log(
                f"seek({number} x {RECORD_SIZE}) -> tell() = {f.tell()}"
            )
            raw = f.read(RECORD_SIZE)
            self._log(f"read({RECORD_SIZE} bytes) -> tell() = {f.tell()}")
        return decode_record(raw)

    def overwrite(self, number, contact):
        """Sobrescribe SOLO el registro ``number`` (modificación en el lugar)."""
        record = encode_record(contact)
        total = self.count()
        if not 0 <= number < total:
            raise CorruptFileError(f"Registro {number} fuera de rango (0-{total - 1}).")
        with self._open("r+b") as f:
            f.seek(number * RECORD_SIZE)
            self._log(
                f"seek({number} x {RECORD_SIZE}) -> tell() = {f.tell()}"
            )
            f.write(record)
            f.flush()
            os.fsync(f.fileno())
            self._log(f"write({RECORD_SIZE} bytes) -> tell() = {f.tell()}")

    def scan(self):
        """Lectura secuencial completa (solo para reconstruir el índice)."""
        self.count()  # valida el tamaño
        with self._open("rb") as f:
            while True:
                raw = f.read(RECORD_SIZE)
                if not raw:
                    break
                yield decode_record(raw)