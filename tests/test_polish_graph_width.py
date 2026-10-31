def test_graph_nodes_carry_their_group_and_the_levers_can_group_by_it(lr):
    "Each node of the graph data has the group path of its concept, so the graph can group by it."
    lr.put('Ashwini', 'The first star.', 'jyotisha', slug='ashwini'); lr.set_group('ashwini', ['Nakshatras', 'Fire'])
    by = {n['id']: n for n in lr.graph()['nodes']}
    assert by['ashwini']['group'] == ['Nakshatras', 'Fire'] and by['ranking']['group'] == []
