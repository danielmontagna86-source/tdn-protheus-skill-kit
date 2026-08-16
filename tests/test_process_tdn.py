from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "coletando-documentacao-tdn-protheus" / "scripts" / "process_tdn.py"


def load_module():
    spec = importlib.util.spec_from_file_location("process_tdn", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MetadataTests(unittest.TestCase):
    def test_common_protheus_tables_routines_parameters_and_entry_points(self) -> None:
        module = load_module()
        meta = module.extract_metadata("Ponto de Entrada SD1100I - MATA103", "Usa SA1 SA2 SB1 SC5 SD1 SE1 SE2, MV_TESTE e PLRSTPR1 em ADVPL.")
        for table in ("SA1", "SA2", "SB1", "SC5", "SD1", "SE1", "SE2"):
            self.assertIn(table, meta["tables"])
        self.assertIn("MATA103", meta["routines"])
        self.assertIn("PLRSTPR1", meta["routines"])
        self.assertIn("MV_TESTE", meta["parameters"])
        self.assertIn("SD1100I", meta["entry_points"])
        self.assertIn("ADVPL", meta["modules"])


if __name__ == "__main__": unittest.main()
