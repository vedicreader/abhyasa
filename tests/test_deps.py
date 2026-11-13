"Dependency floors that the docs rely on."
import tomllib
from importlib.metadata import version
from pathlib import Path

from packaging.version import Version

def test_fossick_floor():
    "fossick 0.1.23 checks each redirect, verifies TLS with the macOS keychain, and clones over HTTPS only. 0.1.24 gives the timed cues of a video (`read_yt(cues=True)`) and `yt_link`. 0.1.28 keeps the 0.1.25 web memory (`fetch(cache=, per_host=, remember_blocks=)`), reads arXiv HTML and gives `arxiv_id`, `local_host`, `gh_repo` and `is_pdf`. So abhyasa must ask for it, and the venv must have it."
    deps = tomllib.loads((Path(__file__).parents[1]/'pyproject.toml').read_text())['project']['dependencies']
    assert 'fossick>=0.1.28' in deps
    assert Version(version('fossick')) >= Version('0.1.28')

def test_store_floors():
    "litesearch 0.1.62 gives `fold_text` and the notebook outputs. vishalakshi 0.1.40 needs rishi 0.1.71. vishalakshi 0.1.38 gives `slug`, `put`, `by_source`, `add_tree`, `crawl(scope=)` and the job `Ledger`."
    deps = tomllib.loads((Path(__file__).parents[1]/'pyproject.toml').read_text())['project']['dependencies']
    for p, v in (('litesearch', '0.1.64'), ('vishalakshi', '0.1.40')):
        assert any(d.startswith(f'{p}>={v}') for d in deps), p
        assert Version(version(p)) >= Version(v), p

def test_rupaka_floor():
    "rupaka 0.0.17 has the drag and tag fixes and the stage; 0.0.16 is the release that the hosted Learn needs for its trace and circuit demos; 0.0.15 draws a 3D scene again when its view comes back; 0.0.14 has the `rk-ask` event, the Ask about this control and `askable`, flow rows that fit their words and axis labels that never meet; 0.0.12 has plain_why, plain and the panel shapes of the board, 0.0.11 moves each row of the board's panel to the step that names it, 0.0.10 has the board of the screen guide (`rupaka.board`), 0.0.9 ships the hand font Patrick Hand (`font_css`), 0.0.8 has the 3D scene blocks and the top-level key `mode` (`can_explain`), 0.0.7 has the `field` fn and the `pixels` block, and 0.0.6 has `Rupaka.state`, `set`, `settle` with an answer, `options`, `open` and `rupaka.poll`, so each extra must ask for it, and the lock must have it."
    pp = tomllib.loads((Path(__file__).parents[1]/'pyproject.toml').read_text())['project']
    deps = pp['dependencies'] + [d for ds in pp['optional-dependencies'].values() for d in ds]
    rs = [d for d in deps if d.startswith('rupaka')]
    assert rs and all(d.endswith('>=0.0.17') for d in rs), rs
    lock = tomllib.loads((Path(__file__).parents[1]/'uv.lock').read_text())
    assert Version(next(p['version'] for p in lock['package'] if p['name'] == 'rupaka')) >= Version('0.0.17')
    assert Version(version('rupaka')) >= Version('0.0.17')

def test_ramabana_is_a_core_dependency():
    "The guide and research guard text with `ramabana.guard`, and routing uses ramabana. 0.2.116 needs `rishi[claude]>=0.1.71` and `shalya>=0.1.34`. 0.2.115 needs `rishi[claude]`. 0.2.109 gives `ready_local`, and falls back to a local model only when its weights are here. 0.2.108 gives `Agent.events`, the typed events of the builder, and `emit`/`emit_state`. 0.2.103 gives `available_models(ttl=)`, `model_label`, `oneshot(wait=, strict=)`, `ask(deadline=, stop=)`, `model_agent` and `read_key`. The `models` extra stays, so old installs still resolve."
    pp = tomllib.loads((Path(__file__).parents[1]/'pyproject.toml').read_text())['project']
    assert any(d.startswith('ramabana>=0.2.116') for d in pp['dependencies'])
    assert pp['optional-dependencies']['models'] == ['ramabana>=0.2.116']
    assert Version(version('ramabana')) >= Version('0.2.116')

def test_rishi_claude_extra():
    "The default model is `claude/sonnet`. rishi 0.1.70 moved the Claude SDK into the `claude` extra, so abhyasa asks for that extra, and the venv has the SDK. rishi 0.1.71 needs aidialog 0.0.42 with the fastllm and llmsurgery that match it."
    deps = tomllib.loads((Path(__file__).parents[1]/'pyproject.toml').read_text())['project']['dependencies']
    assert any(d.startswith('rishi[claude]>=0.1.71') for d in deps)
    assert Version(version('claude-agent-sdk'))

def test_locks_match_aidialog():
    "aidialog 0.0.42 moved `usage_info` and `aidialog.hist` into aihist. With it, fastllm before 0.0.70 and llmsurgery before 0.0.19 fail every model call on import. Neither the dev lock nor the Mac app's pinned lock may pair them."
    root = Path(__file__).parents[1]
    for f in (root/'uv.lock', root/'mac'/'Resources'/'Pin'/'uv.lock'):
        vs = {p['name']: Version(p['version']) for p in tomllib.loads(f.read_text())['package'] if 'version' in p}
        if vs['aidialog'] < Version('0.0.42'): continue
        assert vs['python-fastllm'] >= Version('0.0.70'), f
        assert vs.get('llmsurgery', Version('0.0.19')) >= Version('0.0.19'), f

def test_shalya_gheasy_floors():
    "shalya 0.1.29 gives `Registry.each`, which ramabana 0.2.108 calls on each turn; 0.1.28 gives `LocalHost(url_ok=, on_read=)` and `read_page`. gheasy 0.0.20 gives `gh_repo_info`. abhyasa imports both, so a plain install must have them."
    deps = tomllib.loads((Path(__file__).parents[1]/'pyproject.toml').read_text())['project']['dependencies']
    for p, v in (('shalya', '0.1.34'), ('gheasy', '0.0.21')):
        assert any(d.startswith(f'{p}>={v}') for d in deps), p
        assert Version(version(p)) >= Version(v), p
