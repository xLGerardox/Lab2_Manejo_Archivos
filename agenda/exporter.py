"""Exportación a JSON y generación del reporte PDF"""

import json
from datetime import datetime

from fpdf import FPDF

from .errors import FileAccessError


def export_json(contacts, json_path):
    """Escribe todos los contactos en un JSON y Devuelve la cantidad con utf-8"""
    payload = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "total": len(contacts),
        "contactos": contacts,
    }
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except PermissionError as exc:
        raise FileAccessError(f"Sin permisos para escribir {json_path}...") from exc
    except OSError as exc:
        raise FileAccessError(f"No se pudo exportar el JSON: {exc}") from exc
    return len(contacts)


def _latin1(text):
    """Las fuentes base de PDF usan Latin-1 (cubre tildes y ñ)."""
    return str(text).encode("latin-1", "replace").decode("latin-1")


def make_pdf(json_path, pdf_path):
    """Lee el JSON exportado y genera un PDF con tabla y fecha de generacion"""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        contacts = data["contactos"]
    except FileNotFoundError as exc:
        raise FileAccessError(f"No existe el JSON {json_path}") from exc
    except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as exc:
        raise FileAccessError(f"El JSON está dañado: {exc}") from exc

    pdf = FPDF(orientation="L", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _latin1("Agenda de Contactos"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0, 6,
        _latin1(f"Fecha de generación: {datetime.now():%d/%m/%Y %H:%M:%S}   |   "
                f"Total de contactos: {len(contacts)}"),
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(4)

    widths = [18, 70, 40, 85, 55]
    headers = ["ID", "Nombre", "Teléfono", "Correo", "Ciudad"]
    keys = ["id", "nombre", "telefono", "correo", "ciudad"]

    def header_row():
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(220, 220, 220)
        for w, h in zip(widths, headers):
            pdf.cell(w, 8, _latin1(h), border=1, fill=True)
        pdf.ln()
        pdf.set_font("Helvetica", "", 10)

    header_row()
    for c in contacts:
        if pdf.get_y() > pdf.h - 25:
            pdf.add_page()
            header_row()
        for w, k in zip(widths, keys):
            pdf.cell(w, 7, _latin1(c.get(k, "")), border=1)
        pdf.ln()

    try:
        pdf.output(pdf_path)
    except PermissionError as exc:
        raise FileAccessError(f"Sin permisos para escribir {pdf_path}...") from exc
    except OSError as exc:
        raise FileAccessError(f"No se pudo guardar el PDF: {exc}") from exc
    return len(contacts)