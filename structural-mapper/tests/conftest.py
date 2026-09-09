from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def load_synthetic_generator():
    path = ROOT / "tools" / "mapping-dataset" / "generate_synthetic.py"
    spec = importlib.util.spec_from_file_location("generate_synthetic", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["generate_synthetic"] = module  # dataclasses resolve string annotations via sys.modules
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def synthetic_case():
    generator = load_synthetic_generator()
    case = generator.generate(180)
    return case, generator.svg(case).encode("utf-8"), 28.0  # px per metre used by the generator
