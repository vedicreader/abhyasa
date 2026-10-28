"""Open in Leela: code with a library and tools are learned in Leela. abhyasa reads the address file that a running Leela writes and makes a link.
It never calls Leela. The learner's browser opens the link."""
import json, os
from pathlib import Path
from urllib.parse import urlparse
from fasthtml.common import *
from abhyasa.journey import handoff
from .cfg import cfg

__all__ = ['LEELA_INSTALL', 'leela_address', 'leela_base', 'leela_link', 'leela_line']
LEELA_INSTALL = 'https://github.com/vedicreader/leela#install'
LOCAL = ('127.0.0.1', 'localhost', '::1')

def leela_address() -> Path:
    "The file that a running Leela writes: `$ABHYASA_LEELA_FILE` (a test or a trial sets it), else `$XDG_CONFIG_HOME/leela/serving.json`, else `~/.config/leela/serving.json`."
    if f := os.getenv('ABHYASA_LEELA_FILE'): return Path(f)
    return Path(os.getenv('XDG_CONFIG_HOME') or Path.home()/'.config')/'leela'/'serving.json'

def _local(url) -> bool:
    "True when `url` is `http://` on this computer, with a port."
    try: u = urlparse(url); return u.scheme == 'http' and u.hostname in LOCAL and u.port is not None
    except (ValueError, TypeError, AttributeError): return False

def _alive(pid) -> bool:
    try: os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError): return False
    return True

def leela_base() -> str|None:
    "The address of a running Leela: from its address file when its pid is alive, else `cfg.leela`; None when neither is local."
    try: d = json.loads(leela_address().read_text())
    except (OSError, ValueError): d = None
    if isinstance(d, dict) and _alive(d.get('pid') or 0) and _local(d.get('url')): return d['url']
    return cfg.leela if _local(cfg.leela) else None

def leela_link(j, i:int|None=None, topic:str='') -> str|None:
    "The link that opens walk `j`, its step `i` or `topic` in Leela; None when Leela does not run."
    return (b := leela_base()) and b.rstrip('/') + handoff(j.id if j else '', i, topic)

def leela_line(j, i:int|None=None, topic:str='', say:str='Open in Leela for code and tools', quiet:bool=False):
    "One muted line with the link to Leela, or how to get Leela; nothing when `quiet` and Leela does not run."
    if href := leela_link(j, i, topic): return P(A(f'{say} ↗', href=href, target='_blank', rel='noopener'), cls='leela-line')
    return '' if quiet else P('Open this in Leela for code and tools. ', A('Get Leela', href=LEELA_INSTALL, target='_blank', rel='noopener'), cls='leela-line muted')
