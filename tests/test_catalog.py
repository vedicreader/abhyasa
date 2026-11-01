"The model list of Settings: the app gets it after the start, and a new process shows the last list from the disk at once."
import json, subprocess, sys
import ramabana.core as rc
from abhyasa import llm

ROW = dict(value='claude/sonnet', label='sonnet', provider='claude', source='login')

def counted(calls):
    "A stand-in for ramabana's slow look-up (`_model_rows`) that counts its calls. `available_models(ttl=)` keeps what it gives."
    def f(include_legacy=False): calls.append(1); return [rc._facts(ROW)]
    return f

def test_the_app_gets_the_model_list_after_the_start(mk, monkeypatch):
    "`warm_catalog` runs `catalog` on the pool of the app, so the first visit to Settings does not wait."
    from abhyasa.app import warm_catalog
    calls = []
    monkeypatch.setattr(llm, 'catalog', lambda ttl=300.: calls.append(1) or [ROW])
    warm_catalog(mk(['settings']).app).result(timeout=5)
    assert calls == [1]

def test_two_calls_ask_the_providers_once(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(rc, 'PROBE_DIR', tmp_path); monkeypatch.setattr(rc, '_model_rows', counted(calls)); rc.forget_probes()
    assert [r['name'] for r in llm.catalog()] == ['Claude Sonnet'] and llm.catalog() and calls == [1]
    rc.forget_probes()

NEW = """import json, sys, time
import ramabana.core as rc
rc.PROBE_DIR = sys.argv[1]
def slow(include_legacy=False): time.sleep(5); print('SLOW'); return []
rc._model_rows = slow
from abhyasa.llm import catalog
t = time.time(); rows = catalog()
print(json.dumps(dict(s=time.time() - t, names=[r['name'] for r in rows])))"""

def test_a_new_process_shows_the_last_list_at_once(monkeypatch, tmp_path):
    "One process keeps the list on the disk. A second process, with a slow look-up, gets that list at once and does not wait for the look-up."
    calls = []
    monkeypatch.setattr(rc, 'PROBE_DIR', tmp_path); monkeypatch.setattr(rc, '_model_rows', counted(calls)); rc.forget_probes()
    llm.catalog(); rc.forget_probes()
    out = subprocess.run([sys.executable, '-c', NEW, str(tmp_path)], capture_output=True, text=True, check=True, timeout=60).stdout
    got = json.loads(out.splitlines()[-1])
    assert got['names'] == ['Claude Sonnet'] and got['s'] < 1 and 'SLOW' not in out and calls == [1]
