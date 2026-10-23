import unittest
from contextlib import redirect_stdout
from datetime import date
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from core.params import Params
from core.runner import GenerationError, generar
from core.worker import _run


def _params(tipo_ramo: str) -> Params:
    return Params(
        fecha_valoracion=date(2026, 8, 31),
        tipo_ramo=tipo_ramo,
        ramo="087" if tipo_ramo == "LEY100" else "094",
        compania="02" if tipo_ramo == "LEY100" else "22",
    )


class RunnerTests(unittest.TestCase):
    @patch("core.runner.split_stock_nuevo.generar_ts_consolidadas")
    @patch("core.runner.consolidacion.consolidar")
    @patch("core.runner.evidencias.generar_integridad_y_exactitud")
    @patch("core.runner.evidencias.convertir_csv_a_xlsx")
    @patch("core.runner.evidencias.capturar_evidencias_sox")
    @patch("core.runner.descargar_ts")
    def test_arl_runs_sox_steps_and_returns_outputs(
        self,
        descargar,
        capturar_sox,
        convertir,
        integridad,
        consolidar,
        generar_csv,
    ):
        consolidar.return_value = (["NMPOLIZA"], [("A1",)], Path("macro.xlsm"))
        generar_csv.return_value = (Path("stock.csv"), Path("nuevo.csv"))
        logs = []
        result = generar(
            _params("ARL"),
            "usuario",
            "clave-osiris",
            "clave-macro",
            log=logs.append,
        )

        self.assertEqual(
            [descargar.call_count, capturar_sox.call_count, convertir.call_count,
             integridad.call_count, consolidar.call_count, generar_csv.call_count],
            [1, 1, 1, 1, 1, 1],
        )
        self.assertEqual(result.stock, Path("stock.csv"))
        self.assertEqual(result.nuevo, Path("nuevo.csv"))
        self.assertEqual(
            [message for message in logs if message.startswith("Iniciando: ")],
            [
                "Iniciando: Descarga de Ts",
                "Iniciando: Evidencias SOX",
                "Iniciando: Conversion de CSV a XLSX",
                "Iniciando: Integridad y Exactitud",
                "Iniciando: Consolidacion en Excel",
                "Iniciando: Generacion de Stock y Nuevo",
            ],
        )
        self.assertTrue(descargar.call_args.args[3])
        self.assertEqual(descargar.call_args.args[0].ramo, "094")
        self.assertEqual(descargar.call_args.args[0].compania, "22")
        self.assertEqual(consolidar.call_args.args[1], "clave-macro")

    @patch("core.runner.split_stock_nuevo.generar_ts_consolidadas")
    @patch("core.runner.consolidacion.consolidar")
    @patch("core.runner.evidencias.generar_integridad_y_exactitud")
    @patch("core.runner.evidencias.capturar_evidencias_sox")
    @patch("core.runner.evidencias.convertir_csv_a_xlsx")
    @patch("core.runner.descargar_ts")
    def test_ley100_skips_sox_and_does_not_save_parameters(
        self,
        descargar,
        convertir,
        capturar_sox,
        integridad,
        consolidar,
        generar_csv,
    ):
        consolidar.return_value = ([], [], None)
        generar_csv.return_value = (Path("stock.csv"), Path("nuevo.csv"))
        with patch.object(Params, "save") as save:
            generar(_params("LEY100"), "u", "o", "m")

        save.assert_not_called()
        self.assertEqual(descargar.call_count, 1)
        self.assertEqual(convertir.call_count, 1)
        self.assertEqual(capturar_sox.call_count, 0)
        self.assertEqual(integridad.call_count, 0)
        self.assertEqual(consolidar.call_count, 1)
        self.assertEqual(generar_csv.call_count, 1)
        self.assertEqual(descargar.call_args.args[0].ramo, "087")
        self.assertEqual(descargar.call_args.args[0].compania, "02")

    @patch("core.runner.descargar_ts")
    def test_error_logs_and_raises_without_credentials(self, descargar):
        lines = []
        descargar.side_effect = RuntimeError("rechazo: usuario clave-osiris clave-macro")

        with self.assertRaises(GenerationError) as raised:
            generar(_params("LEY100"), "usuario", "clave-osiris", "clave-macro", log=lines.append)

        all_messages = "\n".join(lines + [str(raised.exception)])
        self.assertNotIn("usuario", all_messages)
        self.assertNotIn("clave-osiris", all_messages)
        self.assertNotIn("clave-macro", all_messages)
        self.assertIn("[REDACTADO]", all_messages)

    def test_missing_credentials_fail_before_running(self):
        with patch("core.runner.descargar_ts") as descargar:
            with self.assertRaises(ValueError):
                generar(_params("ARL"), "", "pass", "macro")
        descargar.assert_not_called()

    @patch("core.worker.GeneratorLock")
    @patch("core.worker.generar")
    def test_worker_reads_credentials_from_payload_without_logging_them(
        self, run_generation, period_lock
    ):
        run_generation.return_value.stock = Path("ARL/202608/stock.csv")
        run_generation.return_value.nuevo = Path("ARL/202608/nuevo.csv")
        params = _params("ARL")
        payload = {
            "tipo_ramo": "ARL",
            "params": params.to_dict(),
            "credentials": {
                "usuario_osiris": "private-user",
                "contrasena_osiris": "private-osiris-password",
                "contrasena_macro": "private-macro-password",
            },
        }
        output = StringIO()
        with redirect_stdout(output):
            exit_code = _run(payload)

        self.assertEqual(exit_code, 0)
        run_generation.assert_called_once()
        self.assertEqual(
            run_generation.call_args.args[1:],
            ("private-user", "private-osiris-password", "private-macro-password"),
        )
        for credential in payload["credentials"].values():
            self.assertNotIn(credential, output.getvalue())
        self.assertIn('"type": "completed"', output.getvalue())

    @patch("core.worker.GeneratorLock")
    @patch("core.worker.generar")
    def test_worker_rejects_ramo_company_mismatch(
        self, run_generation, period_lock
    ):
        params = _params("LEY100")
        params.ramo = "094"
        payload = {
            "tipo_ramo": "LEY100",
            "params": params.to_dict(),
            "credentials": {
                "usuario_osiris": "user",
                "contrasena_osiris": "osiris",
                "contrasena_macro": "macro",
            },
        }
        output = StringIO()
        with redirect_stdout(output):
            with self.assertRaises(ValueError):
                _run(payload)

        run_generation.assert_not_called()
        period_lock.assert_not_called()

    @patch("core.worker.GeneratorLock")
    @patch("core.worker.partir_consolidado")
    def test_worker_splits_existing_total_without_credentials(
        self, split_total, period_lock
    ):
        split_total.return_value.stock = Path("LEY100/202608/stock.csv")
        split_total.return_value.nuevo = Path("LEY100/202608/nuevo.csv")
        split_total.return_value.total = Path("LEY100/202608/total.csv")
        params = _params("LEY100")
        output = StringIO()
        with redirect_stdout(output):
            exit_code = _run(
                {
                    "action": "split",
                    "tipo_ramo": "LEY100",
                    "params": params.to_dict(),
                }
            )

        self.assertEqual(exit_code, 0)
        period_lock.assert_called_once()
        split_total.assert_called_once()
        self.assertIn('"type": "completed"', output.getvalue())
        self.assertNotIn("credentials", output.getvalue())


if __name__ == "__main__":
    unittest.main()
