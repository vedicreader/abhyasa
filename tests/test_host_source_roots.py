"A host gives the source folders of one call through `use_settings`; Abhyasa keeps its own rules for each, and filing and un-filing leave the files alone."
import os, tempfile
from pathlib import Path

import pytest
from abhyasa.learner import dropped_roots, roots, temp_learning, use_settings
from abhyasa.sources import file_file, file_folder, path_docs, root_docs, unfile


@pytest.fixture
def home(monkeypatch):
    h = Path(tempfile.mkdtemp()).resolve()
    monkeypatch.setenv('HOME', str(h))
    return h


def test_a_host_names_the_source_folders_and_the_rules_still_refuse(home):
    ok, out, hid = home/'proj', Path(tempfile.mkdtemp()).resolve(), home/'.hid'
    for d in (ok, hid): d.mkdir()
    with use_settings({'sources.roots': '\n'.join(map(str, (ok, out, hid, home)))}):
        assert roots() == [str(ok)]
        why = dict(dropped_roots())
        assert why[str(out)] == 'abhyasa reads only folders in your home folder.'
        assert why[str(hid)] == 'abhyasa does not read a hidden folder or a link.'
        assert why[str(home)] == 'Name a folder in your home folder, not the home folder itself.'


def test_filing_a_file_or_folder_and_unfiling_leave_the_user_files_alone(home):
    lr, d, f = temp_learning(), home/'notes', home/'one.md'
    d.mkdir(); (d/'n.md').write_text('folder text'); f.write_text('file text')
    docs, one = file_folder(lr, d), file_file(lr, f)
    assert [x.title for x in root_docs(lr, 'notes')] == ['notes/n'] and path_docs(lr, f)
    assert unfile(lr, docs.added) == 1 and unfile(lr, one.added) == 1
    assert root_docs(lr, 'notes') == [] and path_docs(lr, f) == []
    assert (d/'n.md').read_text() == 'folder text' and f.read_text() == 'file text' and [p.name for p in d.iterdir()] == ['n.md']
