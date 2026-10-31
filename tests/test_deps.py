"Dependency floors that the docs rely on."
import tomllib
from importlib.metadata import version
from pathlib import Path

from packaging.version import Version

def test_fossick_floor():
    "fossick 0.1.23 checks each redirect, verifies TLS with the macOS keychain, and clones over HTTPS only. 0.1.24 gives the timed cues of a video (`read_yt(cues=True)`) and `yt_link`. So abhyasa must ask for it, and the venv must have it."
    deps = tomllib.loads((Path(__file__).parents[1]/'pyproject.toml').read_text())['project']['dependencies']
    assert 'fossick>=0.1.24' in deps
    assert Version(version('fossick')) >= Version('0.1.24')

def test_rupaka_floor():
    "rupaka 0.0.8 has the 3D scene blocks and the top-level key `mode` (`can_explain`), 0.0.7 has the `field` fn and the `pixels` block, and 0.0.6 has `Rupaka.state`, `set`, `settle` with an answer, `options`, `open` and `rupaka.poll`, so each extra must ask for it, and the lock must have it."
    pp = tomllib.loads((Path(__file__).parents[1]/'pyproject.toml').read_text())['project']
    deps = pp['dependencies'] + [d for ds in pp['optional-dependencies'].values() for d in ds]
    rs = [d for d in deps if d.startswith('rupaka')]
    assert rs and all(d.endswith('>=0.0.8') for d in rs), rs
    lock = tomllib.loads((Path(__file__).parents[1]/'uv.lock').read_text())
    assert Version(next(p['version'] for p in lock['package'] if p['name'] == 'rupaka')) >= Version('0.0.8')
    assert Version(version('rupaka')) >= Version('0.0.8')

def test_ramabana_is_a_core_dependency():
    "The guide and research guard text with `ramabana.guard`, routing uses ramabana, and the gather worker uses `only_tools` (0.2.96), so a plain install must have it. The `models` extra stays, so old installs still resolve."
    pp = tomllib.loads((Path(__file__).parents[1]/'pyproject.toml').read_text())['project']
    assert 'ramabana>=0.2.96' in pp['dependencies']
    assert 'models' in pp['optional-dependencies']
    assert Version(version('ramabana')) >= Version('0.2.96')
