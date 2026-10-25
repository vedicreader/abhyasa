// A d3 force layout of the concept graph. Click a node to open the concept.
(async () => {
  const svg = d3.select('#graph'), el = svg.node(), focus = el.dataset.focus;
  const g = await (await fetch(el.dataset.url)).json();
  const W = el.clientWidth, H = el.clientHeight, now = Date.now() / 1000;
  const probe = document.body.appendChild(document.createElement('i'));   // a theme colour as rgb(), which d3 can mix
  const v = n => { probe.style.color = `var(${n})`; return getComputedStyle(probe).color; };
  const col = d3.scaleLinear().domain([0, 5]).range([v('--bg'), v('--acc')]);   // unseen is hollow paper, a full floor is umber
  const due = d => d.seen && d.due && d.due <= now;
  svg.append('defs').append('marker').attr('id', 'ar').attr('viewBox', '0 -4 8 8').attr('refX', 16).attr('markerWidth', 6)
     .attr('markerHeight', 6).attr('orient', 'auto').append('path').attr('d', 'M0,-4L8,0L0,4').attr('fill', v('--mute'));
  const root = svg.append('g');
  svg.call(d3.zoom().scaleExtent([.2, 4]).on('zoom', e => root.attr('transform', e.transform)));
  const sim = d3.forceSimulation(g.nodes).force('link', d3.forceLink(g.links).id(d => d.id).distance(60))
    .force('charge', d3.forceManyBody().strength(-120)).force('center', d3.forceCenter(W / 2, H / 2))
    .force('x', d3.forceX(W / 2).strength(.03)).force('y', d3.forceY(H / 2).strength(.03));
  const link = root.append('g').selectAll('line').data(g.links).join('line').attr('stroke', v('--rule'))
    .attr('stroke-dasharray', d => d.kind === 'related' ? '3,3' : null).attr('marker-end', d => d.kind === 'prereq' ? 'url(#ar)' : null);
  const node = root.append('g').selectAll('circle').data(g.nodes).join('circle')
    .attr('r', d => (d.id === focus ? 9 : 5) + Math.min(d.seen, 8)).attr('fill', d => col(d.floor))
    .attr('stroke', d => due(d) ? v('--no') : v('--mute')).attr('stroke-width', d => due(d) ? 2.5 : 1)
    .style('cursor', 'pointer').on('click', (e, d) => location = '/c/' + d.id)
    .call(d3.drag().on('start', (e, d) => { if (!e.active) sim.alphaTarget(.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; }).on('end', (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = d.fy = null; }));
  node.append('title').text(d => `${d.name} (${d.subject}) floor ${d.floor}`);
  const label = root.append('g').selectAll('text').data(g.nodes).join('text').text(d => d.name).attr('dx', 9).attr('dy', 4)
    .attr('class', d => d.id === focus ? 'focus' : null);
  sim.on('tick', () => {
    link.attr('x1', d => d.source.x).attr('y1', d => d.source.y).attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    node.attr('cx', d => d.x).attr('cy', d => d.y); label.attr('x', d => d.x).attr('y', d => d.y);
  });
})();
