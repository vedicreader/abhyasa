"Dependency floors that the docs rely on."
import tomllib
from importlib.metadata import version
from pathlib import Path

from packaging.version import Version

def test_fossick_floor():
    "fossick 0.1.22 checks each redirect and verifies TLS, so abhyasa must ask for it, and the venv must have it."
    deps = tomllib.loads((Path(__file__).parents[1]/'pyproject.toml').read_text())['project']['dependencies']
    assert 'fossick>=0.1.22' in deps
    assert Version(version('fossick')) >= Version('0.1.22')
