"""Excepciones de la aplicación de agendaa

Todas heredan de AgendaError para que se capturen de forma genérica y de un solo....
"""


class AgendaError(Exception):
    """Error base de la aplicación."""


class ValidationError(AgendaError):
    """Datos de contacto inválidos (campo vacío, demasiado largo, OTROSSS)."""


class DuplicateIdError(AgendaError):
    """Se intentó agregar un id que ya existiaaa"""


class NotFoundError(AgendaError):
    """El id buscado no existe en este indice"""


class CorruptFileError(AgendaError):
    """El archivo de contactos o el índice están dañados....."""


class FileAccessError(AgendaError):
    """El archivo no se puede abrir"""