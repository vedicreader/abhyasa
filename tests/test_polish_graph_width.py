from pathlib import Path
import abhyasa.blocks.graph

def test_graph_page_has_no_width_cap_and_fits_on_resize():
    "The graph page lifts the 1200 px cap of `main.wide`, and graph.js fits the nodes again when the canvas box changes size."
    d = Path(abhyasa.blocks.graph.__file__).parent
    assert 'main.wide:has(#graph)' in (d/'graph.css').read_text() and 'max-width: none' in (d/'graph.css').read_text()
    assert 'ResizeObserver(() =>' in (d/'graph.js').read_text() and 'fit(' in (d/'graph.js').read_text().split('new ResizeObserver')[1][:200]
