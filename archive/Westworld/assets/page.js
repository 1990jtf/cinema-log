const { groups, types, characters, relations, seasons } = westworld;
const charactersById = new Map(characters.map(character => [character.id, character]));
const graph = document.getElementById('network');
const map = document.getElementById('map');
const detail = document.getElementById('character-detail');
const roster = document.getElementById('roster');
const search = document.getElementById('character-search');
const groupFilter = document.getElementById('group-filter');
const seasonFilters = document.getElementById('season-filters');
const svgNamespace = 'http://www.w3.org/2000/svg';
let season = 0;
let selected = 'dolores';
let compact = false;

function element(tag, className, value) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== undefined) node.textContent = value;
  return node;
}

function svgElement(tag, attributes) {
  const node = document.createElementNS(svgNamespace, tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
  return node;
}

function avatarUrl(id) {
  return `assets/avatars/${id}.webp`;
}

function avatar(character, size, lazy = false) {
  const image = element('img');
  image.src = avatarUrl(character.id);
  image.alt = '';
  image.width = size;
  image.height = size;
  image.decoding = 'async';
  if (lazy) image.loading = 'lazy';
  return image;
}

function symbol(color) {
  const dot = element('span', 'symbol');
  dot.style.setProperty('--symbol-color', color);
  dot.setAttribute('aria-hidden', 'true');
  return dot;
}

function inSeason(entry) {
  return season === 0 || entry.seasons.includes(season);
}

function neighbors() {
  return relations.filter(inSeason)
    .filter(edge => edge.from === selected || edge.to === selected)
    .map(edge => ({
      ...edge,
      character: charactersById.get(edge.from === selected ? edge.to : edge.from),
    }));
}

function makeGraphNode(character, x, y, active) {
  const radius = active ? 41 : 29;
  const group = svgElement('g', {
    class: active ? 'graph-character selected' : 'graph-character',
    transform: `translate(${x} ${y})`,
    role: 'button',
    tabindex: '0',
    'aria-label': `查看${character.name}的关系`,
    'aria-pressed': active,
    'data-id': character.id,
  });
  group.append(svgElement('circle', {
    r: radius + 2,
    class: 'ring',
    stroke: groups[character.group].color,
  }));
  group.append(svgElement('image', {
    href: avatarUrl(character.id),
    x: -radius, y: -radius,
    width: radius * 2, height: radius * 2,
    'clip-path': active ? 'url(#selected-portrait)' : 'url(#map-portrait)',
  }));
  const name = svgElement('text', {y: radius + 20, 'aria-hidden': 'true'});
  name.textContent = character.short;
  group.append(name);
  group.addEventListener('click', () => selectCharacter(character.id, 'map'));
  group.addEventListener('keydown', event => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    selectCharacter(character.id, 'map');
  });
  return group;
}

function renderGraph(character, edges) {
  const x = compact ? 195 : 380;
  const y = compact ? 211 : 236;
  const rx = compact ? 130 : 292;
  const ry = compact ? 144 : 165;
  graph.setAttribute('viewBox', `0 0 ${x * 2} ${y * 2}`);

  const defs = svgElement('defs', {});
  for (const [id, r] of [['map-portrait', 29], ['selected-portrait', 41]]) {
    const clip = svgElement('clipPath', {id});
    clip.append(svgElement('circle', {r}));
    defs.append(clip);
  }
  const orbit = svgElement('ellipse', {cx: x, cy: y, rx, ry, class: 'orbit', 'aria-hidden': 'true'});
  const lines = svgElement('g', {'aria-hidden': 'true'});
  const nodes = svgElement('g', {});
  const initialAngle = edges.length < 3 ? 0 : -Math.PI / 2;
  edges.forEach((edge, index) => {
    const angle = initialAngle + index * 2 * Math.PI / edges.length;
    const nx = Math.round(x + rx * Math.cos(angle));
    const ny = Math.round(y + ry * Math.sin(angle));
    lines.append(svgElement('line', {
      x1: x, y1: y, x2: nx, y2: ny,
      class: 'edge', stroke: types[edge.type].color,
    }));
    nodes.append(makeGraphNode(edge.character, nx, ny, false));
  });
  graph.replaceChildren(defs, orbit, lines, makeGraphNode(character, x, y, true), nodes);
}

function renderDetail(character, edges) {
  const identity = element('div', 'identity');
  identity.style.setProperty('--group-color', groups[character.group].color);
  const copy = element('div');
  const name = element('h3', '', character.name);
  name.tabIndex = -1;
  const english = element('p', '', `${character.en} · ${character.actor}`);
  english.lang = 'en';
  copy.append(name, english, element('p', 'role', character.role));
  identity.append(avatar(character, 66), copy);
  document.getElementById('identity').replaceChildren(identity);
  document.getElementById('bio').textContent = character.bio;

  const rows = edges.map(edge => {
    const row = element('li');
    const button = element('button');
    button.type = 'button';
    const type = types[edge.type];
    const kind = element('span', 'connection-kind');
    const seasons = edge.seasons.map(number => `S${number}`).join(' / ');
    kind.append(symbol(type.color), `${type.name} · ${seasons}`);
    button.append(
      element('strong', 'connection-name', `${edge.character.name} · ${edge.label}`),
      kind,
      element('span', 'connection-text', edge.text),
    );
    button.addEventListener('click', () => selectCharacter(edge.character.id, 'detail'));
    row.append(button);
    return row;
  });
  document.getElementById('connections').replaceChildren(...rows);
  document.getElementById('no-connections').hidden = rows.length > 0;
  detail.scrollTop = 0;
}

function updateSelection() {
  const character = charactersById.get(selected);
  const edges = neighbors();
  renderGraph(character, edges);
  renderDetail(character, edges);
  document.getElementById('graph-count').textContent = `${character.short} · ${edges.length} 条直接关系`;
  for (const card of roster.children) card.setAttribute('aria-pressed', card.dataset.id === selected);
}

function selectCharacter(id, origin) {
  if (selected !== id) {
    selected = id;
    updateSelection();
  }
  if (origin === 'roster') document.getElementById('relations').scrollIntoView();
  if (origin === 'detail') detail.querySelector('h3').focus();
  if (origin === 'map' || origin === 'roster') {
    graph.querySelector('.selected').focus({preventScroll: true});
  }
}

function filterRoster() {
  const query = search.value.normalize('NFKC').trim().toLocaleLowerCase();
  let visible = 0;
  for (const card of roster.children) {
    const character = charactersById.get(card.dataset.id);
    card.hidden = !inSeason(character)
      || (groupFilter.value !== '' && character.group !== groupFilter.value)
      || !card.dataset.search.includes(query);
    if (!card.hidden) visible++;
  }
  document.getElementById('roster-count').textContent = `显示 ${visible} / ${characters.length} 个角色与身份`;
  document.getElementById('empty-roster').hidden = visible > 0;
}

function changeSeason(number, focus = '') {
  season = number;
  if (focus) {
    selected = focus;
  } else if (!inSeason(charactersById.get(selected)) || neighbors().length === 0) {
    selected = seasons.find(entry => entry.id === season)?.focus ?? 'dolores';
  }
  for (const button of seasonFilters.children) button.setAttribute('aria-pressed', Number(button.dataset.season) === season);
  updateSelection();
  filterRoster();
}

function renderControls() {
  for (const [id, label] of [[0, '全部'], ...seasons.map(entry => [entry.id, `第 ${entry.id} 季`])]) {
    const button = element('button', '', label);
    button.type = 'button';
    button.dataset.season = id;
    button.addEventListener('click', () => changeSeason(id));
    seasonFilters.append(button);
  }
  const legend = document.getElementById('legend');
  for (const type of Object.values(types)) {
    const item = element('li');
    item.append(symbol(type.color), type.name);
    legend.append(item);
  }
  for (const [key, group] of Object.entries(groups)) {
    groupFilter.add(new Option(group.name, key));
  }
}

function renderRoster() {
  for (const character of characters) {
    const card = element('button');
    card.type = 'button';
    card.dataset.id = character.id;
    card.dataset.search = [character.name, character.en, character.actor, character.role]
      .join(' ').normalize('NFKC').toLocaleLowerCase();
    card.style.setProperty('--group-color', groups[character.group].color);
    const copy = element('span');
    const name = element('span', 'card-en', character.en);
    name.lang = 'en';
    copy.append(element('strong', '', character.name), name, element('span', 'card-role', character.role));
    card.append(avatar(character, 55, true), copy);
    card.addEventListener('click', () => selectCharacter(character.id, 'roster'));
    roster.append(card);
  }
}

function renderTimeline() {
  const timeline = document.getElementById('timeline-entries');
  for (const entry of seasons) {
    const item = element('article');
    const heading = element('div');
    heading.append(
      element('h3', '', `${entry.name} · ${entry.en}`),
      element('p', 'season-meta', `${entry.year} · ${entry.episodes} 集 · ${entry.finale}`),
    );
    const button = element('button', 'season-link', `查看第 ${entry.id} 季关系图 ↑`);
    button.type = 'button';
    button.addEventListener('click', () => {
      changeSeason(entry.id, entry.focus);
      document.getElementById('relations').scrollIntoView();
      graph.querySelector('.selected').focus({preventScroll: true});
    });
    item.append(element('span', 'timeline-id', `S${entry.id}`), heading, element('p', 'season-story', entry.body), button);
    timeline.append(item);
  }
}

renderControls();
renderRoster();
renderTimeline();
for (const id of ['interactive-map', 'timeline', 'characters']) document.getElementById(id).hidden = false;
compact = map.clientWidth < 530;
changeSeason(0);
search.addEventListener('input', filterRoster);
groupFilter.addEventListener('change', filterRoster);

if ('ResizeObserver' in window) {
  const observer = new ResizeObserver(() => {
    const nextLayout = map.clientWidth < 530;
    if (nextLayout === compact) return;
    compact = nextLayout;
    const activeElement = document.activeElement;
    const focusedCharacter = graph.contains(activeElement) ? activeElement.dataset.id : null;
    renderGraph(charactersById.get(selected), neighbors());
    if (focusedCharacter) {
      graph.querySelector(`[data-id="${focusedCharacter}"]`)?.focus({preventScroll: true});
    }
  });
  observer.observe(map);
}
