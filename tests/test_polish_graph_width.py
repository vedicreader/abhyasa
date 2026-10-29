from pathlib import Path
import abhyasa.blocks.graph

def test_graph_page_has_no_width_cap_and_fits_on_resize():
    "The graph page lifts the 1200 px cap of `main.wide`, and graph.js fits the nodes again when the canvas box changes size."
    d = Path(abhyasa.blocks.graph.__file__).parent
    assert 'main.wide:has(#graph)' in (d/'graph.css').read_text() and 'max-width: none' in (d/'graph.css').read_text()
    assert 'ResizeObserver(() =>' in (d/'graph.js').read_text() and 'fit(' in (d/'graph.js').read_text().split('new ResizeObserver')[1][:200]

def test_one_grip_helper_for_the_pane_and_the_graph_tools():
    "grip.js is in core and loads before pane.js; pane.js and graph.js call it, and neither keeps its own drag code."
    from abhyasa.core.ui import HDRS
    core = Path(abhyasa.blocks.graph.__file__).parents[2]/'core'
    h = str(HDRS())
    assert h.index('grip.js') < h.index('pane.js') and 'abhyasaGrip' in (core/'grip.js').read_text()
    pane, graph = (core/'pane.js').read_text(), (Path(abhyasa.blocks.graph.__file__).parent/'graph.js').read_text()
    assert 'abhyasaGrip(' in pane and 'abhyasaGrip(' in graph and 'setPointerCapture' not in pane + graph
    from fasthtml.common import to_xml
    from abhyasa.blocks.graph.ui import Stage
    assert 'class="grip"' in to_xml(Stage('/d', []))

def test_graph_nodes_carry_their_group_and_the_levers_can_group_by_it(lr):
    "Each node of the graph data has the group path of its concept, and Look has a Group by lever with subject and group."
    from fasthtml.common import to_xml
    from abhyasa.blocks.graph.ui import Levers
    lr.put('Ashwini', 'The first star.', 'jyotisha', slug='ashwini'); lr.set_group('ashwini', ['Nakshatras', 'Fire'])
    by = {n['id']: n for n in lr.graph()['nodes']}
    assert by['ashwini']['group'] == ['Nakshatras', 'Fire'] and by['ranking']['group'] == []
    x = to_xml(Levers(['ml']))
    assert 'name="groupBy"' in x and 'value="group"' in x
