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

def test_rupaka_floor():
    "rupaka 0.0.5 has `Rupaka.state`, `set`, `settle` with an answer, `options` and `rupaka.poll`, so each extra must ask for it, and the lock must have it."
    pp = tomllib.loads((Path(__file__).parents[1]/'pyproject.toml').read_text())['project']
    deps = pp['dependencies'] + [d for ds in pp['optional-dependencies'].values() for d in ds]
    rs = [d for d in deps if d.startswith('rupaka')]
    assert rs and all(d.endswith('>=0.0.5') for d in rs), rs
    lock = tomllib.loads((Path(__file__).parents[1]/'uv.lock').read_text())
    assert Version(next(p['version'] for p in lock['package'] if p['name'] == 'rupaka')) >= Version('0.0.5')
    assert Version(version('rupaka')) >= Version('0.0.5')
