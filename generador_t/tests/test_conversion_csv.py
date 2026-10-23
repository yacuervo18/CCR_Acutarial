import tempfile
import unittest
from pathlib import Path

from core.evidencias import _origen_excel


class OrigenExcelTest(unittest.TestCase):
    def _origen(self, contenido: bytes) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "T.csv"
            ruta.write_bytes(contenido)
            return _origen_excel(ruta)

    def test_ansi_con_tildes(self):
        self.assertEqual(self._origen("GASTO DE ADMINISTRACIÓN".encode("latin-1")), 2)

    def test_utf8_con_tildes(self):
        self.assertEqual(self._origen("GASTO DE ADMINISTRACIÓN".encode("utf-8")), 65001)

    def test_ascii(self):
        self.assertEqual(self._origen(b"A;B\n1;2\n"), 2)


if __name__ == "__main__":
    unittest.main()
