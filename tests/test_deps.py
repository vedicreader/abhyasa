"Dependency floors that the docs rely on."
import tomllib
from importlib.metadata import version
from pathlib import Path

from packaging.version import Version

def test_fossick_floor():
    "fossick 0.1.23 checks each redirect, verifies TLS with the macOS keychain, and clones over HTTPS only. 0.1.24 gives the timed cues of a video (`read_yt(cues=True)`) and `yt_link`. 0.1.25 keeps the web memory (`fetch(cache=, per_host=, remember_blocks=)`), reads arXiv HTML and gives `arxiv_id`, `local_host`, `gh_repo` and `is_pdf`. So abhyasa must ask for it, and the venv must have it."
    deps = tomllib.loads((Path(__file__).parents[1]/'pyproject.toml').read_text())['project']['dependencies']
    assert 'fossick>=0.1.25' in deps
    assert Version(version('fossick')) >= Version('0.1.25')

def test_store_floors():
    "litesearch 0.1.62 gives `fold_text` and the notebook outputs. vishalakshi 0.1.38 gives `slug`, `put`, `by_source`, `add_tree`, `crawl(scope=)` and the job `Ledger`."
    deps = tomllib.loads((Path(__file__).parents[1]/'pyproject.toml').read_text())['project']['dependencies']
    for p, v in (('litesearch', '0.1.62'), ('vishalakshi', '0.1.38')):
        assert any(d.startswith(f'{p}>={v}') for d in deps), p
        assert Version(version(p)) >= Version(v), p

def test_rupaka_floor():
    "rupaka 0.0.11 moves each row of the board's panel to the step that names it, 0.0.10 has the board of the screen guide (`rupaka.board`), 0.0.9 ships the hand font Patrick Hand (`font_css`), 0.0.8 has the 3D scene blocks and the top-level key `mode` (`can_explain`), 0.0.7 has the `field` fn and the `pixels` block, and 0.0.6 has `Rupaka.state`, `set`, `settle` with an answer, `options`, `open` and `rupaka.poll`, so each extra must ask for it, and the lock must have it."
    pp = tomllib.loads((Path(__file__).parents[1]/'pyproject.toml').read_text())['project']
    deps = pp['dependencies'] + [d for ds in pp['optional-dependencies'].values() for d in ds]
    rs = [d for d in deps if d.startswith('rupaka')]
    assert rs and all(d.endswith('>=0.0.11') for d in rs), rs
    lock = tomllib.loads((Path(__file__).parents[1]/'uv.lock').read_text())
    assert Version(next(p['version'] for p in lock['package'] if p['name'] == 'rupaka')) >= Version('0.0.11')
    assert Version(version('rupaka')) >= Version('0.0.11')

def test_ramabana_is_a_core_dependency():
    "The guide and research guard text with `ramabana.guard`, and routing uses ramabana. 0.2.103 gives `available_models(ttl=)`, `model_label`, `oneshot(wait=, strict=)`, `ask(deadline=, stop=)`, `model_agent` and `read_key`. The `models` extra stays, so old installs still resolve."
    pp = tomllib.loads((Path(__file__).parents[1]/'pyproject.toml').read_text())['project']
    assert any(d.startswith('ramabana>=0.2.103') for d in pp['dependencies'])
    assert 'models' in pp['optional-dependencies']
    assert Version(version('ramabana')) >= Version('0.2.103')

def test_shalya_gheasy_floors():
    "shalya 0.1.28 gives `LocalHost(url_ok=, on_read=)` and `read_page`. gheasy 0.0.20 gives `gh_repo_info`. abhyasa imports both, so a plain install must have them."
    deps = tomllib.loads((Path(__file__).parents[1]/'pyproject.toml').read_text())['project']['dependencies']
    for p, v in (('shalya', '0.1.28'), ('gheasy', '0.0.20')):
        assert any(d.startswith(f'{p}>={v}') for d in deps), p
        assert Version(version(p)) >= Version(v), p
