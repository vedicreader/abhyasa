"Source metadata: a double-escaped page title shows once-unescaped, and a web source's date says it is the day it was read."
from datetime import datetime
from types import SimpleNamespace
from abhyasa.sources import page_text, source_of

BODY = '<p>' + 'Heat flows from hot to cold. ' * 30 + '</p>'


def _page(title):
    html = f'<html><head><title>{title}</title></head><body><h1>{title}</h1>{BODY}</body></html>'
    return SimpleNamespace(url='https://example.org/t', headers={'Content-Type': 'text/html; charset=utf-8'}, html=html, html_content=html,
                           body=html.encode(), status=200, text=html)


def test_double_escaped_title_is_unescaped_once():
    assert page_text(_page('Definition &amp;amp; Facts')).title == 'Definition &amp; Facts'   # one layer goes: the page's own text is `&amp;`


def test_single_escaped_title_is_unescaped():
    assert page_text(_page('Heat &amp; Work')).title == 'Heat & Work'


def test_stored_entity_title_is_cleaned_for_display():
    assert source_of(dict(src='web', title='Definition &amp; Facts')).title == 'Definition & Facts'


def test_plain_title_is_unchanged():
    assert page_text(_page('Entropy')).title == 'Entropy'


def test_web_source_date_says_it_was_read():
    at = datetime(2026, 11, 18, 12).timestamp()
    s = source_of(dict(src='web', url='https://example.org/t', title='T', text='x', at=at))
    assert s.date == 'read on 18 Nov 2026'


def test_page_text_gives_the_publication_date_or_none():
    html = f'<html><head><title>T</title><meta property="article:published_time" content="2024-03-05T10:00:00Z"></head><body>{BODY}</body></html>'
    r = SimpleNamespace(url='https://example.org/t', headers={'Content-Type': 'text/html'}, html=html, html_content=html, body=html.encode(), status=200, text=html)
    assert page_text(r).date == '2024-03-05'
    assert page_text(_page('Entropy')).date is None


def test_web_source_with_a_publication_date_shows_the_bare_date():
    at = datetime(2026, 11, 18, 12).timestamp()
    s = source_of(dict(src='web', url='https://example.org/t', title='T', text='x', at=at, date='2024-03-05'))
    assert s.date == '5 Mar 2024'


def test_research_read_keeps_the_page_date():
    from abhyasa.path import _read
    from fastcore.all import AttrDict
    r = _read(AttrDict(title='T', url='https://example.org/t', date='2024-03-05'), AttrDict(doc_id='d', shelf='s'), 'p', 1.0)
    assert r['date'] == '2024-03-05'


def test_source_without_a_fetch_time_has_no_date():
    assert source_of(dict(src='web', url='https://example.org/t', title='T', text='x')).date == ''
    assert source_of(dict(src='vault:s', doc_id='d', title='T', text='x', at=1.0)).date == ''