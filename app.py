"""Agenda de Contactos con Acceso Aleatorio hecha con Tkinter"""

import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, simpledialog, ttk

from agenda import exporter, integrity
from agenda.errors import AgendaError
from agenda.records import FIELDS, RECORD_SIZE
from agenda.store import ContactStore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "datos")
EXPORT_DIR = os.path.join(DATA_DIR, "exportaciones")

LABELS = {"id": "ID", "nombre": "Nombre", "telefono": "Teléfono",
          "correo": "Correo", "ciudad": "Ciudad"}


def human_size(n):
    return f"{n:,} bytes ({n / 1024:.2f} KB)"


class ContactForm(tk.Toplevel):
    """Formulario para agregar o modificar un algun contacto"""

    def __init__(self, parent, title, initial=None, id_editable=True):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.result = None
        self.vars = {}
        initial = initial or {}
        for row, (name, width) in enumerate(FIELDS):
            ttk.Label(self, text=f"{LABELS[name]} (máx. {width}):").grid(
                row=row, column=0, sticky="e", padx=8, pady=4)
            var = tk.StringVar(value=str(initial.get(name, "")))
            entry = ttk.Entry(self, textvariable=var, width=34)
            entry.grid(row=row, column=1, padx=8, pady=4)
            if name == "id" and not id_editable:
                entry.state(["disabled"])
            self.vars[name] = var
        buttons = ttk.Frame(self)
        buttons.grid(row=len(FIELDS), column=0, columnspan=2, pady=10)
        ttk.Button(buttons, text="Guardar", command=self._ok).pack(side="left", padx=6)
        ttk.Button(buttons, text="Cancelar", command=self.destroy).pack(side="left", padx=6)
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.wait_window(self)

    def _ok(self):
        self.result = {k: v.get() for k, v in self.vars.items()}
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Agenda de Contactos")
        self.geometry("900x560")
        self.store = ContactStore(DATA_DIR, log=self.log)
        self._build_menu()
        self._build_body()
        self.after(100, self._startup)

    def _build_menu(self):
        bar = tk.Menu(self)
        m = tk.Menu(bar, tearoff=0)
        m.add_command(label="Agregar contacto...", command=self.add_contact)
        m.add_command(label="Buscar por ID...", command=self.search_contact)
        m.add_command(label="Modificar contacto...", command=self.modify_contact)
        m.add_separator()
        m.add_command(label="Actualizar lista", command=self.refresh)
        m.add_command(label="Salir", command=self.destroy)
        bar.add_cascade(label="Contactos", menu=m)

        m = tk.Menu(bar, tearoff=0)  # Ayuda
        m.add_command(label="Contenido de la ayuda",
                      command=lambda: messagebox.showinfo(
                          "Ayuda", "La ayuda en línea no esta disponible..."))
        m.add_command(label="Acerca de",
                      command=lambda: messagebox.showinfo(
                          "Acerca de",
                          "Agenda de Contactos con Acceso Aleatorio\n"
                          "LaboratorioN2-Manejo e implentacion de archivos"))
        bar.add_cascade(label="Ayuda", menu=m)
        self.config(menu=bar)

    def _build_body(self):
        self.status = tk.StringVar(value="Listo.")
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w").pack(
            fill="x", side="bottom")
            
        paned = ttk.PanedWindow(self, orient="vertical")
        paned.pack(fill="both", expand=True, padx=8, pady=8)

        top = ttk.LabelFrame(paned, text="Contactos")
        cols = [n for n, _ in FIELDS]
        self.tree = ttk.Treeview(top, columns=cols, show="headings", height=10)
        for name in cols:
            self.tree.heading(name, text=LABELS[name])
            self.tree.column(name, width=60 if name == "id" else 160, anchor="w")
        scroll = ttk.Scrollbar(top, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        paned.add(top, weight=3)

        bottom = ttk.LabelFrame(
            paned, text=f"Operaciones de archivo registro de {RECORD_SIZE} bytes")
        self.log_text = tk.Text(bottom, height=9, state="disabled", wrap="none",
                                font=("Courier", 9))
        lscroll = ttk.Scrollbar(bottom, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=lscroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        lscroll.pack(side="right", fill="y")
        paned.add(bottom, weight=2)


    def log(self, msg):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{stamp}] {msg}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def fail(self, exc):
        """Muestra el error sin tirar la applicacion"""
        self.log(f"ERROR: {exc}")
        self.status.set(f"Error: {exc}")
        messagebox.showerror("Error", str(exc), parent=self)

    def refresh(self):
        try:
            contacts = self.store.list_all()
        except AgendaError as exc:
            self.fail(exc)
            return
        self.tree.delete(*self.tree.get_children())
        for c in contacts:
            self.tree.insert("", "end", values=[c[n] for n, _ in FIELDS])
        self.status.set(f"{len(contacts)} contacto(s).")

    def _startup(self):
        warnings = self.store.open()
        for w in warnings:
            self.log(f"AVISO: {w}")
        try:
            state = self.store.verify_integrity()[0]
        except AgendaError:
            state = None
        if warnings:
            messagebox.showwarning("Avisos al iniciar", "\n\n".join(warnings), parent=self)
        if state == integrity.MISMATCH:
            if messagebox.askyesno(
                    "Archivo modificado",
                    "El archivo de contactos fue modificado fuera de la aplicación\n\n"
                    "¿Desea aceptar su estado actual y generar un nuevo hash?\n"
                    "(Si elige 'No' el aviso se repetirá en el próximo inicio.)",
                    parent=self):
                try:
                    self.store.accept_current_state()
                    self.log("El usuario aceptó el estado actual (hash generado)")
                except AgendaError as exc:
                    self.fail(exc)
        self.refresh()

    def add_contact(self):
        form = ContactForm(self, "Agregar contacto",
                           initial={"id": self.store.next_id()})
        if form.result is None:
            return
        try:
            number = self.store.add(form.result)
            self.status.set(f"Contacto agregado en el registro {number}.")
            self.refresh()
        except AgendaError as exc:
            self.fail(exc)

    def _ask_id(self, title):
        value = simpledialog.askstring(title, "Ingrese el ID del contacto:", parent=self)
        return None if value is None else value.strip()

    def search_contact(self):
        cid = self._ask_id("Buscar por ID")
        if cid is None:
            return
        try:
            c = self.store.get(cid)
        except AgendaError as exc:
            self.fail(exc)
            return
        self.status.set(f"Contacto {c['id']} encontrado...")
        messagebox.showinfo(
            "Contacto encontrado",
            "\n".join(f"{LABELS[n]}: {c[n]}" for n, _ in FIELDS), parent=self)

    def modify_contact(self):
        cid = self._ask_id("Modificar contacto")
        if cid is None:
            return
        try:
            current = self.store.get(cid)
        except AgendaError as exc:
            self.fail(exc)
            return
        form = ContactForm(self, f"Modificar contacto {current['id']}",
                           initial=current, id_editable=False)
        if form.result is None:
            return
        try:
            self.store.update(current["id"], form.result)
            self.status.set(f"Contacto {current['id']} modificado en el lugar.")
            self.refresh()
        except AgendaError as exc:
            self.fail(exc)


if __name__ == "__main__":
    App().mainloop()