"""Open in Leela: code with a library and tools are learned in Leela. abhyasa reads the address file that a running Leela writes and makes a link.
It never calls Leela. The learner's browser opens the link. abhyasa writes its own address file, so Leela can link back to the walk."""
import json, os, re
from pathlib import Path
from urllib.parse import urlparse
from fasthtml.common import *
from fastcore.xtras import atomic_save
from abhyasa.contract import handoff, vault_key
from .cfg import cfg

__all__ = ['LEELA_INSTALL', 'LOCAL_HOSTS', 'loopback', 'leela_address', 'leela_base', 'leela_link', 'leela_line', 'abhyasa_address',
           'write_address', 'drop_address']
LEELA_INSTALL = 'https://github.com/vedicreader/leela#install'
LOCAL_HOSTS = ('127.0.0.1', 'localhost', '::1')

def leela_address() -> Path:
    "The file that a running Leela writes: `$ABHYASA_LEELA_FILE` (a test or a trial sets it), else `$XDG_CONFIG_HOME/leela/serving.json`, else `~/.config/leela/serving.json`."
    if f := os.getenv('ABHYASA_LEELA_FILE'): return Path(f)
    return Path(os.getenv('XDG_CONFIG_HOME') or Path.home()/'.config')/'leela'/'serving.json'

def loopback(url) -> str|None:
    """`url` rebuilt as `http://<host>:<port>` from its parsed parts, when it is `http://` on this computer with a port; else None.
    A browser reads `\\` and `@` in another way than Python does (`http://evil.com\\@127.0.0.1:5010` goes to evil.com), so an address
    with either, with a user name, or with a space or a control character is refused. Never put the raw string in a link."""
    if not isinstance(url, str) or re.search(r'[\\@\s\x00-\x1f\x7f]', url): return None
    try: u = urlparse(url); host, port = u.hostname, u.port
    except ValueError: return None
    if u.scheme != 'http' or u.username is not None or u.password is not None or host not in LOCAL_HOSTS or type(port) is not int or not 0 < port < 65536: return None
    return f"http://{'[::1]' if host == '::1' else host}:{port}"

def _alive(pid) -> bool:
    "True when `pid` is a process that runs. A pid of 0 or less names a process group, so it is not one."
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0: return False
    try: os.kill(pid, 0)
    except (OSError, ValueError, TypeError): return False
    return True

def _served(f:Path, fallback:str='') -> str|None:
    "The loopback address in the address file `f` when its pid is alive, else `fallback`; None when neither is local."
    try: d = json.loads(f.read_text()) if f.stat().st_size < 4096 else None
    except (OSError, ValueError): d = None
    if isinstance(d, dict) and _alive(d.get('pid') or 0) and (u := loopback(d.get('url'))): return u
    return loopback(fallback)

def leela_base() -> str|None:
    "The address of a running Leela: from its address file when its pid is alive, else `cfg.leela`; None when neither is local."
    return _served(leela_address(), cfg.leela)

def leela_link(j, i:int|None=None, topic:str='', vault=None) -> str|None:
    """The link that opens walk `j`, its step `i` or `topic` in Leela; None when Leela does not run. `vault` is the vault file of the app,
    so the link has its key `v` and Leela can tell when it uses another vault. With no `vault` the link has no `v`, as in 0.0.12."""
    if not (b := leela_base()): return None
    return b.rstrip('/') + handoff(j.id if j else '', i, topic, v=vault_key(vault) if vault else '')

def leela_line(j, i:int|None=None, topic:str='', say:str='Open in Leela for code and tools', quiet:bool=False, vault=None):
    "One muted line with the link to Leela (with the key of `vault`), or how to get Leela; nothing when `quiet` and Leela does not run."
    if href := leela_link(j, i, topic, vault): return P(A(f'{say} ↗', href=href, target='_blank', rel='noopener'), cls='leela-line')
    return '' if quiet else P('Open this in Leela for code and tools. ', A('Get Leela', href=LEELA_INSTALL, target='_blank', rel='noopener'), cls='leela-line muted')

def abhyasa_address() -> Path:
    "The file where abhyasa writes its own address: `$ABHYASA_ADDRESS_FILE` (a test sets it), else `$XDG_CONFIG_HOME/abhyasa/serving.json`, else `~/.config/abhyasa/serving.json`."
    if f := os.getenv('ABHYASA_ADDRESS_FILE'): return Path(f)
    return Path(os.getenv('XDG_CONFIG_HOME') or Path.home()/'.config')/'abhyasa'/'serving.json'

def write_address(url:str, vault) -> Path:
    """Write `{url, pid, vault}` to `abhyasa_address()`, so Leela can link back to a walk. `url` must be a loopback URL with a port.
    The write is atomic (a temp file, then a rename), and only the owner can read the file (0600)."""
    if not (url := loopback(url) or ''): raise ValueError('abhyasa writes only a loopback address with a port')
    f = abhyasa_address()
    f.parent.mkdir(parents=True, exist_ok=True)
    with atomic_save(f, 'w') as o: json.dump(dict(url=url, pid=os.getpid(), vault=str(vault)), o)   # a temp file made with mode 0600, then a rename
    return f

def drop_address():
    "Remove abhyasa's address file, only when it still has the pid of this process. Another abhyasa that started later keeps its file."
    f = abhyasa_address()
    try: d = json.loads(f.read_text())
    except (OSError, ValueError): return
    if isinstance(d, dict) and d.get('pid') == os.getpid(): f.unlink(missing_ok=True)
