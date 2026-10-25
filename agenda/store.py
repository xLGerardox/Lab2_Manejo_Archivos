"""Fachada que une archivo de registros, índice, hash, respaldo además de exportación"""

import os
import re
from datetime import datetime

from . import backup, integrity
from .errors import (AgendaError, CorruptFileError, DuplicateIdError,
                     FileAccessError, NotFoundError, ValidationError)
from .index import IndexFile
from .records import FIELDS, RECORD_SIZE, RecordFile

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ContactStore:
    def __init__(self, data_dir, log=None):
        self.data_dir = data_dir
        self._log = log or (lambda msg: None)
        self.dat_path = os.path.join(data_dir, "contactos.dat")
        self.index_path = os.path.join(data_dir, "indice.json")
        self.hash_path = os.path.join(data_dir, "contactos.sha256")
        self.records = RecordFile(self.dat_path, log=self._emit)
        self.index = IndexFile(self.index_path)
        self.mapping = {}

    def _emit(self, msg):
        self._log(msg)

    # la validacion
    @staticmethod
    def _validate(contact, check_id=True):
        if check_id:
            try:
                cid = int(str(contact.get("id", "")).strip())
            except ValueError:
                raise ValidationError("El id debe ser un numero entero")
            if cid <= 0:
                raise ValidationError("El id debe ser mayor a cero")
            if len(str(cid)) > dict(FIELDS)["id"]:
                raise ValidationError("El id esmuy grande")
            contact["id"] = cid
        for name in ("nombre", "telefono", "correo", "ciudad"):
            contact[name] = str(contact.get(name, "")).strip()
        if not contact["nombre"]:
            raise ValidationError("El nombre debe ir SI O SI")
        if contact["correo"] and not EMAIL_RE.match(contact["correo"]):
            raise ValidationError("El formato del correo no es valido")
        return contact

    # los contactos
    def add(self, contact):
        contact = self._validate(dict(contact))
        if contact["id"] in self.mapping:
            raise DuplicateIdError(f"Ya existe un contacto con id {contact['id']}")
        number = self.records.append(contact)
        self.mapping[contact["id"]] = number
        self.index.save(self.mapping, RECORD_SIZE)       # actualiza el índice
        self._log(f"Índice actualizado: id {contact['id']} -> registro {number}")
        self._save_hash()
        return number

    def get(self, contact_id):
        """Búsqueda por id: primero el índice, luego un seek() al registro"""
        try:
            contact_id = int(contact_id)
        except (TypeError, ValueError):
            raise ValidationError("El id debe ser un entero")
        if contact_id not in self.mapping:
            raise NotFoundError(f"No existe un contacto con id {contact_id}")
        number = self.mapping[contact_id]
        self._log(f"Índice: id {contact_id} -> registro {number}")
        contact = self.records.read(number)
        if contact["id"] != contact_id:
            raise CorruptFileError(
                "El índice no coincide con el archivo de los contactos"
                f"(se esperaba id {contact_id}, se leyó {contact['id']})."
            )
        return contact

    def next_id(self):
        return max(self.mapping, default=0) + 1

    # para integridad
    def _save_hash(self):
        value = integrity.save_hash(self.dat_path, self.hash_path)
        self._log(f"SHA-256 actualizado: {value}")
        return value

    # ---- arranque: abrir y reparar -------------------------------------
    def open(self):
        """lee archivos y regresa una lista de avisos para el usuario
        Nunca lanza excepciones ya que todo problema se convierte en aviso...
        """
        warnings = []
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            self.records.ensure_exists()
        except (OSError, AgendaError) as exc:
            return [f"No se pudo preparar la carpeta de datos: {exc}"]

        # 1) integridad del archivo de contactos
        try:
            state, saved, current = integrity.verify(self.dat_path, self.hash_path)
            if state == integrity.MISMATCH:
                warnings.append(
                    "¡ATENCIÓN! El archivo contactos.dat fue modificado fuera de "
                    "la aplicación (el hash SHA-256 no coincide)."
                )
            elif state == integrity.NO_HASH and os.path.getsize(self.dat_path) > 0:
                warnings.append(
                    "No existe contactos.sha256: no se puede comprobar la integridad."
                )
            elif state == integrity.NO_HASH:
                integrity.save_hash(self.dat_path, self.hash_path)
        except AgendaError as exc:
            warnings.append(str(exc))

        # 2) índice
        try:
            self.mapping = self.index.load()
            self._check_index_consistency()
        except FileAccessError as exc:
            if not self.index.exists():
                if os.path.getsize(self.dat_path) == 0:
                    # primer arranque: archivo vacío y se crea un índice vacío
                    self.mapping = {}
                    self.index.save(self.mapping, RECORD_SIZE)
                else:
                    warnings.append(
                        "No existe indice.json: se reconstruirá desde contactos.dat"
                    )
                    warnings += self._try_rebuild()
            else:
                warnings.append(str(exc))
        except CorruptFileError as exc:
            warnings.append(f"{exc} Se intentará reconstruir desde contactos.dat.")
            warnings += self._try_rebuild()
        return warnings

    def _check_index_consistency(self):
        total = self.records.count()
        if len(self.mapping) != total:
            raise CorruptFileError(
                f"El índice tiene {len(self.mapping)} entradas pero su archivoo"
                f"tiene {total} registros."
            )

    def _try_rebuild(self):
        try:
            n = self.rebuild_index()
            return [f"Índice reconstruido con {n} contacto/ss"]
        except AgendaError as exc:
            self.mapping = {}
            return [f"No se pudo reconstruir el índice: {exc}"]

    def rebuild_index(self):
        mapping = {}
        for number, contact in enumerate(self.records.scan()):
            if contact["id"] in mapping:
                raise CorruptFileError(f"Id duplicado en el archivo: {contact['id']}.")
            mapping[contact["id"]] = number
        self.mapping = mapping
        self.index.save(mapping, RECORD_SIZE)
        return len(mapping)

    # modificar - listar
    def update(self, contact_id, changes):
        current = self.get(contact_id)
        updated = dict(current)
        updated.update({k: v for k, v in changes.items() if k != "id"})
        updated = self._validate(updated, check_id=False)
        updated["id"] = current["id"]
        self.records.overwrite(self.mapping[current["id"]], updated)
        self._save_hash()
        return updated

    def list_all(self):
        """Todos los contactos ordenados por id..."""
        saved_log, self._log = self._log, (lambda msg: None)
        saved_rec = self.records._log
        self.records._log = lambda msg: None
        try:
            return [self.get(cid) for cid in sorted(self.mapping)]
        finally:
            self._log = saved_log
            self.records._log = saved_rec

    # integridad y respaldoss
    def accept_current_state(self):
        """El usuario acepta el archivo tal como está: se vuelve a firmar..."""
        self.rebuild_index()
        return self._save_hash()

    def verify_integrity(self):
        return integrity.verify(self.dat_path, self.hash_path)

    def create_backup(self, directory=None):
        directory = directory or os.path.join(self.data_dir, "respaldos")
        os.makedirs(directory, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = os.path.join(directory, f"respaldo_{stamp}.zip")
        original, compressed = backup.create_backup(
            [self.dat_path, self.index_path], zip_path
        )
        return zip_path, original, compressed

    def file_info(self):
        return backup.file_info(self.dat_path)