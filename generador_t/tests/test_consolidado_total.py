import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from core import paths, split_stock_nuevo
from core.params import Params
from core.runner import partir_consolidado

HEADERS = ["NMPOLIZA", "FEVIGENCIA_INICIAL", "Asegurado", "VALOR", "NOMBRE"]
ROWS = [
    ("P1", "2024/03/01", "7", 1.5, "Peña"),
    ("P2", "2024/09/01", "8", 2.0, "Muñoz"),
    ("P3", "2025/01/15", "9", 0.0, ""),
]


def _params(tipo: str) -> Params:
    return Params(
        fecha_valoracion=date(2026, 10, 31),
        tipo_ramo=tipo,
        ramo="087" if tipo == "LEY100" else "094",
        compania="02" if tipo == "LEY100" else "22",
        fecha_corte_vigencia=date(2024, 8, 1),
    )


class ConsolidadoTotalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patcher = patch.object(paths, "BASE_DIR", Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def _leer(self, ruta, params):
        return pd.read_csv(ruta, sep=";", dtype=str, keep_default_na=False, encoding=params.encoding_consolidada)

    def test_total_manifest_and_split_for_both_ramos(self):
        for tipo, sufijo in (("LEY100", "Ley100"), ("ARL", "RM")):
            with self.subTest(tipo=tipo):
                params = _params(tipo)
                stock, nuevo = split_stock_nuevo.generar_ts_consolidadas(
                    HEADERS, ROWS, params, log=lambda _m: None
                )
                total = paths.consolidada_total_path(params.clave_periodo)
                self.assertEqual(total.name, f"202610_t_consolidada_{sufijo}.csv")
                self.assertEqual(len(self._leer(total, params)), 3)
                self.assertEqual(len(self._leer(stock, params)), 1)
                self.assertEqual(len(self._leer(nuevo, params)), 2)

                manifest = json.loads(paths.manifest_path(params.clave_periodo).read_text(encoding="utf-8"))
                self.assertEqual(manifest["estado"], "completo")
                self.assertEqual(manifest["filas_total"], 3)
                self.assertEqual(manifest["filas_stock"], 1)
                self.assertEqual(manifest["filas_nuevo"], 2)
                self.assertEqual(manifest["filas_stock_completo"], 1)
                self.assertEqual(manifest["fecha_valoracion_t"], "2026-10-31")
                self.assertEqual(manifest["fecha_valoracion_t_1"], "2026-09-30")
                self.assertEqual(manifest["smmlv"], params.smmlv)

    def test_empty_operational_stock_also_saves_full_stock_for_evidence(self):
        params = _params("LEY100")
        params.stock_vacia = True

        stock, nuevo = split_stock_nuevo.generar_ts_consolidadas(
            HEADERS, ROWS, params, log=lambda _m: None
        )
        full_stock = paths.consolidada_stock_completo_path(params.clave_periodo)

        self.assertEqual(len(self._leer(stock, params)), 0)
        self.assertEqual(len(self._leer(full_stock, params)), 1)
        self.assertEqual(self._leer(full_stock, params)["NMPOLIZA"].tolist(), ["P1"])
        self.assertEqual(len(self._leer(nuevo, params)), 2)
        manifest = json.loads(paths.manifest_path(params.clave_periodo).read_text(encoding="utf-8"))
        self.assertEqual(manifest["filas_stock"], 0)
        self.assertEqual(manifest["filas_stock_completo"], 1)
        self.assertEqual(manifest["archivo_stock_completo"], full_stock.name)

    def test_split_from_disk_matches_in_memory_split(self):
        for tipo in ("LEY100", "ARL"):
            with self.subTest(tipo=tipo):
                params = _params(tipo)
                stock, nuevo = split_stock_nuevo.generar_ts_consolidadas(
                    HEADERS, ROWS, params, log=lambda _m: None
                )
                memoria = (stock.read_bytes(), nuevo.read_bytes())

                result = partir_consolidado(params)
                self.assertEqual((result.stock.read_bytes(), result.nuevo.read_bytes()), memoria)

    def test_stage_a_only_leaves_total_and_removes_stale_split(self):
        params = _params("LEY100")
        split_stock_nuevo.generar_ts_consolidadas(HEADERS, ROWS, params, log=lambda _m: None)
        manifest_path = paths.manifest_path(params.clave_periodo)
        previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        previous_reviewed = paths.consolidada_revisada_path(
            params.clave_periodo, previous_manifest["run_id"]
        )
        previous_reviewed.write_text("older correction", encoding="latin-1")
        previous_manifest["archivo_revisado"] = previous_reviewed.name
        previous_manifest["cantidad_correcciones"] = 1
        manifest_path.write_text(json.dumps(previous_manifest), encoding="utf-8")

        split_stock_nuevo.generar_consolidado_total(HEADERS, ROWS[:2], params, log=lambda _m: None)

        self.assertTrue(paths.consolidada_total_path(params.clave_periodo).exists())
        self.assertFalse(paths.consolidada_csv_path(params.clave_periodo, "Stock").exists())
        self.assertFalse(paths.consolidada_csv_path(params.clave_periodo, "Nuevo").exists())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["estado"], "consolidado_total")
        self.assertEqual(manifest["filas_total"], 2)
        self.assertIsNone(manifest["filas_stock"])
        self.assertNotEqual(manifest["run_id"], previous_manifest["run_id"])
        self.assertIsNone(manifest["archivo_revisado"])
        self.assertEqual(manifest["cantidad_correcciones"], 0)
        self.assertTrue(previous_reviewed.is_file())

    def test_partition_uses_reviewed_total_for_active_run(self):
        params = _params("LEY100")
        split_stock_nuevo.generar_ts_consolidadas(
            HEADERS, ROWS, params, log=lambda _m: None
        )
        manifest_path = paths.manifest_path(params.clave_periodo)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        reviewed_path = paths.consolidada_revisada_path(
            params.clave_periodo, manifest["run_id"]
        )
        reviewed = self._leer(paths.consolidada_total_path(params.clave_periodo), params)
        reviewed.loc[reviewed["NMPOLIZA"] == "P2", "VALOR"] = "2.5"
        reviewed.to_csv(
            reviewed_path,
            sep=";",
            index=False,
            encoding=params.encoding_consolidada,
        )
        manifest["archivo_revisado"] = reviewed_path.name
        manifest["cantidad_correcciones"] = 1
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        stock, nuevo = split_stock_nuevo.partir_desde_total(
            params, log=lambda _message: None
        )

        self.assertEqual(self._leer(stock, params)["NMPOLIZA"].tolist(), ["P1"])
        nuevo_df = self._leer(nuevo, params)
        self.assertEqual(nuevo_df.loc[nuevo_df["NMPOLIZA"] == "P2", "VALOR"].iloc[0], "2.5")

    def test_split_without_total_fails_clearly(self):
        with self.assertRaises(Exception) as raised:
            partir_consolidado(_params("ARL"))
        self.assertIn("consolidado total", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
