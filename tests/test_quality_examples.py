"""Examples execute through public APIs; independent import does not load a simulator."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_imported_quality_example_without_simulator():
    script = """
import runpy
import sys
class RefuseSimulator:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('taqsim', 'incidence'):
            raise ImportError('simulator deliberately unavailable')
sys.meta_path.insert(0, RefuseSimulator())
runpy.run_path('examples/imported_quality.py', run_name='__main__')
assert 'taqsim' not in sys.modules
"""
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "finding: fail" in result.stdout
    assert "minimum: 15/2 m3/s" in result.stdout
    assert "total: 20 m3/s" in result.stdout


def test_live_saved_quality_example(tmp_path):
    pytest.importorskip("taqsim")
    destination = tmp_path / "quality.taqsim"
    result = subprocess.run(
        [sys.executable, "examples/taqsim_quality.py", "--save", str(destination)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    for label in ("live", "saved"):
        assert f"{label}: water=15 m3; mass=9 kg; concentration=600 mg/l" in result.stdout
        assert f"{label}: duration=3600 s; mean flow=1/240 m3/s; 500 mg/l upper: fail" in result.stdout
    assert destination.is_file()
    preserved = destination.read_bytes()
    again = subprocess.run(
        [sys.executable, "examples/taqsim_quality.py", "--save", str(destination)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert again.returncode != 0
    assert "refusing to overwrite" in again.stderr
    assert destination.read_bytes() == preserved
