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