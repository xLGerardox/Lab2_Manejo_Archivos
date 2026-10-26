import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agenda import exporter, integrity
from agenda.errors import (CorruptFileError, DuplicateIdError, NotFoundError,
                           ValidationError)
from agenda.records import RECORD_SIZE, decode_record, encode_record
from agenda.store import ContactStore


def sample(i, **kw):
    c = {"id": i, "nombre": f"Persona {i}", "telefono": f"5555-{i:04d}",
         "correo": f"p{i}@correo.com", "ciudad": "Quetzaltenango"}
    c.update(kw)
    return c


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = ContactStore(self.dir)
        self.assertEqual(self.store.open(), [])

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class TestRecords(unittest.TestCase):
    def test_fixed_size(self):
        self.assertEqual(len(encode_record(sample(1))), RECORD_SIZE)
        self.assertEqual(len(encode_record({"id": 1, "nombre": "A"})), RECORD_SIZE)

    def test_utf8_roundtrip_keeps_size(self):
        c = sample(7, nombre="José Peña Ñandú", ciudad="Xelajú")
        raw = encode_record(c)
        self.assertEqual(len(raw), RECORD_SIZE)
        self.assertEqual(decode_record(raw)["nombre"], "José Peña Ñandú")

    def test_field_too_long(self):
        with self.assertRaises(ValidationError):
            encode_record(sample(1, nombre="x" * 31))


class TestStore(Base):
    def test_add_and_get_by_index(self):
        for i in (1, 2, 3):
            self.store.add(sample(i))
        self.assertEqual(self.store.get(2)["nombre"], "Persona 2")
        self.assertEqual(os.path.getsize(self.store.dat_path), 3 * RECORD_SIZE)
        with open(self.store.index_path, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["entries"], {"1": 0, "2": 1, "3": 2})

    def test_duplicate_and_missing_id(self):
        self.store.add(sample(1))
        with self.assertRaises(DuplicateIdError):
            self.store.add(sample(1))
        with self.assertRaises(NotFoundError):
            self.store.get(99)
        with self.assertRaises(ValidationError):
            self.store.get("abc")

    def test_update_in_place_only_touches_its_record(self):
        for i in (1, 2, 3):
            self.store.add(sample(i))
        with open(self.store.dat_path, "rb") as f:
            before = f.read()
        self.store.update(2, {"telefono": "9999-9999", "ciudad": "Antigua"})
        with open(self.store.dat_path, "rb") as f:
            after = f.read()
        self.assertEqual(len(before), len(after))
        r = RECORD_SIZE
        self.assertEqual(before[:r], after[:r])
        self.assertEqual(before[2 * r:], after[2 * r:])
        self.assertNotEqual(before[r:2 * r], after[r:2 * r])
        self.assertEqual(self.store.get(2)["ciudad"], "Antigua")

    def test_seek_tell_logged(self):
        logs = []
        store = ContactStore(self.dir, log=logs.append)
        store.open()
        for i in (1, 2, 3):
            store.add(sample(i))
        logs.clear()
        store.get(3)
        self.assertTrue(any("tell() = 200" in m for m in logs), logs)

    def test_validation(self):
        with self.assertRaises(ValidationError):
            self.store.add(sample(1, nombre=""))
        with self.assertRaises(ValidationError):
            self.store.add(sample(1, correo="sin-arroba"))
        with self.assertRaises(ValidationError):
            self.store.add({"id": "x", "nombre": "Ana"})


class TestIntegrity(Base):
    def test_hash_updates_and_detects_tampering(self):
        self.store.add(sample(1))
        self.assertEqual(self.store.verify_integrity()[0], integrity.OK)
        with open(self.store.dat_path, "r+b") as f:
            f.seek(10)
            f.write(b"X")
        self.assertEqual(self.store.verify_integrity()[0], integrity.MISMATCH)
        again = ContactStore(self.dir)
        warnings = again.open()
        self.assertTrue(any("modificado fuera" in w for w in warnings))

    def test_hash_updates_after_update(self):
        self.store.add(sample(1))
        h1 = integrity.read_saved_hash(self.store.hash_path)
        self.store.update(1, {"ciudad": "Mazate"})
        h2 = integrity.read_saved_hash(self.store.hash_path)
        self.assertNotEqual(h1, h2)
        self.assertEqual(self.store.verify_integrity()[0], integrity.OK)


class TestErrors(Base):
    def test_missing_files_do_not_crash(self):
        os.remove(self.store.dat_path)
        os.remove(self.store.index_path) if os.path.exists(self.store.index_path) else None
        s = ContactStore(self.dir)
        s.open()                       # no debe lanzar excepción
        s.add(sample(1))
        self.assertEqual(s.get(1)["id"], 1)

    def test_missing_index_is_rebuilt(self):
        for i in (1, 2):
            self.store.add(sample(i))
        os.remove(self.store.index_path)
        s = ContactStore(self.dir)
        warnings = s.open()
        self.assertTrue(any("reconstru" in w for w in warnings))
        self.assertEqual(s.get(2)["nombre"], "Persona 2")

    def test_corrupt_index_is_rebuilt(self):
        self.store.add(sample(1))
        with open(self.store.index_path, "w", encoding="utf-8") as f:
            f.write("{esto no es json")
        s = ContactStore(self.dir)
        warnings = s.open()
        self.assertTrue(any("corrupto" in w for w in warnings))
        self.assertEqual(s.get(1)["id"], 1)

    def test_corrupt_dat_size(self):
        self.store.add(sample(1))
        with open(self.store.dat_path, "ab") as f:
            f.write(b"basura")
        s = ContactStore(self.dir)
        s.open()                       # no se cae
        with self.assertRaises(CorruptFileError):
            s.records.count()


class TestBackupAndExport(Base):
    def test_zip_contains_both_files(self):
        for i in range(1, 6):
            self.store.add(sample(i))
        zip_path, original, compressed = self.store.create_backup()
        with zipfile.ZipFile(zip_path) as zf:
            self.assertEqual(sorted(zf.namelist()), ["contactos.dat", "indice.json"])
        self.assertGreater(original, compressed)

    def test_file_info(self):
        self.store.add(sample(1))
        info = self.store.file_info()
        self.assertEqual(info["tamano"], RECORD_SIZE)
        self.assertTrue(info["lectura"] and info["escritura"])

    def test_export_json_and_pdf(self):
        self.store.add(sample(1, nombre="José Ñ"))
        jp = os.path.join(self.dir, "c.json")
        pp = os.path.join(self.dir, "c.pdf")
        self.assertEqual(exporter.export_json(self.store.list_all(), jp), 1)
        self.assertEqual(exporter.make_pdf(jp, pp), 1)
        with open(pp, "rb") as f:
            self.assertEqual(f.read(4), b"%PDF")


if __name__ == "__main__":
    unittest.main()