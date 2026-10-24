import json
import tempfile
import unittest
from pathlib import Path

from core import macro_correcciones as mc


class CorreccionesTest(unittest.TestCase):
    def test_ultima_correccion_por_celda_y_solo_la_corrida(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "c.jsonl"
            lineas = [
                {"run_id": "A", "fila_csv": 5, "columna": "X", "NMPOLIZA": "1", "valor_anterior": "1", "valor_nuevo": "2"},
                {"run_id": "A", "fila_csv": 5, "columna": "X", "NMPOLIZA": "1", "valor_anterior": "2", "valor_nuevo": "3"},
                {"run_id": "B", "fila_csv": 6, "columna": "X", "NMPOLIZA": "2", "valor_anterior": "1", "valor_nuevo": "9"},
            ]
            ruta.write_text("\n".join(json.dumps(x) for x in lineas), encoding="utf-8")
            res = mc.leer_correcciones(ruta, "A")
            self.assertEqual(len(res), 1)
            self.assertEqual(res[0]["valor_anterior"], "1")
            self.assertEqual(res[0]["valor_nuevo"], "3")

    def test_valor_para_celda(self):
        self.assertEqual(mc.valor_para_celda("4", 3.0), 4.0)
        self.assertEqual(mc.valor_para_celda("abc", "texto"), "abc")
        self.assertIsNone(mc.valor_para_celda("", 3.0))
        with self.assertRaises(ValueError):
            mc.valor_para_celda("abc", 3.0)
        self.assertGreater(mc.valor_para_celda("2026/09/30", 45000.0), 40000)


if __name__ == "__main__":
    unittest.main()
