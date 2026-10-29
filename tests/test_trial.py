# tests/test_trial.py: the trial script works on the shared data, with no model, no network and no browser
import os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parents[1]

def dry(tmp_path, *more):
    home = tmp_path/'home'; home.mkdir(exist_ok=True)   # a new home: any use of the real vault or settings would write here
    return subprocess.run([sys.executable, 'tools/walk_trial.py', '--dry', '--no-shots', '--out', str(tmp_path/'out'), *more],
                          capture_output=True, text=True, timeout=180, cwd=ROOT, env={**os.environ, 'HOME': str(home), 'LITESEARCH_USEARCH': '0'}), home

def test_trial_dry_run(tmp_path):
    r, home = dry(tmp_path)
    assert r.returncode == 0, r.stderr
    rep = (tmp_path/'out'/'report.md').read_text()
    for name in ('attention', 'gradient-descent', 'pydantic-ai', 'claude-code'): assert name in rep
    assert 'one ask' in rep and 's/step' in rep and 'naive' in rep and 'Leela' in rep
    rows = [l for l in rep.splitlines() if l.startswith('| ') and l.split(' | ')[0][2:] in ('attention', 'gradient-descent', 'pydantic-ai', 'claude-code')]
    assert '_error' not in rep and 'Error (' not in rep and 'case failed' not in rep
    assert len(rows) == 4 and not any('error' in l for l in rows), rows
    for name in ('pydantic-ai', 'claude-code'): assert '1 links right, 1 pages right, 0 code checks' in rep.split(f'## {name}')[1]   # no code check, and the right link on the step with Leela
    assert not [p for p in home.rglob('*') if '.vishalakshi' in p.parts or 'abhyasa' in p.parts]   # no real vault, no real settings

def test_dry_run_turns_off_usearch():
    "In a new venv, usearch downloads a binary from GitHub on first use, and the no-network guard refuses it. A dry run uses numpy search."
    env = {k: v for k, v in os.environ.items() if k != 'LITESEARCH_USEARCH'}
    code = "import os, sys; sys.argv = ['walk_trial.py', '--dry']; sys.path.insert(0, 'tools'); import walk_trial; print(os.environ.get('LITESEARCH_USEARCH'))"
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=120, cwd=ROOT, env=env)
    assert r.stdout.strip().splitlines()[-1:] == ['0'], r.stderr

def test_dry_run_fails_when_something_connects_out(tmp_path):
    r, _ = dry(tmp_path, '--probe')   # the probe tries one host off this computer; the guard refuses it and the run must still fail
    assert r.returncode == 1 and '192.0.2.1' in r.stderr and 'refused' in r.stderr

def test_dry_run_grades_a_choice_question_with_no_model_answer(tmp_path):
    "With --choice, the first short check is a choice question with no model answer. The grade trip uses the correct option."
    r, _ = dry(tmp_path, '--choice', '--only', 'gradient-descent')
    assert r.returncode == 0, r.stderr
    rep = (tmp_path/'out'/'report.md').read_text()
    assert 'the correct option graded correct: True' in rep and 'g_error' not in rep and 'grade trip is skipped' not in rep, rep
