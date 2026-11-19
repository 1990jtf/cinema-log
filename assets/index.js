const grid = document.getElementById('grid');
const filters = document.getElementById('filters');
const [search, platform, genre, status] = ['q', 'platform', 'genre', 'status']
  .map(name => filters.elements.namedItem(name));
const controls = [search, platform, genre, status];
const columns = document.getElementById('columns');
const results = document.getElementById('results');
const empty = document.getElementById('empty');
const panels = document.getElementById('spotlight-panels');
const picker = document.getElementById('spotlight-picker');
const spotlightButtons = [...picker.querySelectorAll('[data-spotlight]')];
let activeSpotlight = spotlightButtons[0];

for (const button of spotlightButtons) {
  button.addEventListener('click', () => {
    if (button === activeSpotlight) return;

    const id = button.dataset.spotlight;
    const template = panels.querySelector(`template[data-panel="${id}"]`);
    if (template) template.replaceWith(template.content);

    document.getElementById(activeSpotlight.dataset.spotlight).hidden = true;
    document.getElementById(id).hidden = false;
    activeSpotlight.setAttribute('aria-pressed', 'false');
    button.setAttribute('aria-pressed', 'true');
    activeSpotlight = button;
  });
}
picker.hidden = spotlightButtons.length < 2;

function normalize(text) {
  return text.normalize('NFKC').toLowerCase().trim();
}

const cards = [...grid.querySelectorAll('.card')].map(element => ({
  element,
  title: normalize(element.dataset.title),
  platform: element.dataset.platform,
  genres: JSON.parse(element.dataset.genres),
  status: element.dataset.status,
}));

function applyFilters() {
  const words = normalize(search.value).split(/\s+/).filter(Boolean);
  let shown = 0;

  for (const card of cards) {
    const matches = (!platform.value || card.platform === platform.value)
      && (!genre.value || card.genres.includes(genre.value))
      && (!status.value || card.status === status.value)
      && words.every(word => card.title.includes(word));
    card.element.hidden = !matches;
    if (matches) shown++;
  }

  const message = shown === cards.length ? `共 ${shown} 部剧集` : `显示 ${shown} / ${cards.length} 部剧集`;
  if (results.textContent !== message) results.textContent = message;
  empty.hidden = shown > 0;
}

function restoreFilters() {
  const params = new URLSearchParams(location.search);
  for (const control of controls) {
    control.value = params.get(control.name) ?? '';
    if (control instanceof HTMLSelectElement && control.selectedIndex === -1) control.value = '';
  }
  applyFilters();
}

function updateFilters() {
  applyFilters();
  const url = new URL(location.href);
  for (const control of controls) {
    const value = control.value.trim();
    if (value) {
      url.searchParams.set(control.name, value);
    } else {
      url.searchParams.delete(control.name);
    }
  }
  if (url.href !== location.href) history.replaceState(history.state, '', url);
}

filters.addEventListener('submit', event => {
  event.preventDefault();
  updateFilters();
});
search.addEventListener('input', updateFilters);
for (const select of [platform, genre, status]) select.addEventListener('change', updateFilters);
document.getElementById('reset').addEventListener('click', () => {
  filters.reset();
  updateFilters();
  search.focus();
});
window.addEventListener('popstate', restoreFilters);
restoreFilters();
filters.hidden = false;

document.querySelector('.jump-search').addEventListener('click', event => {
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  document.getElementById('catalog').scrollIntoView();
  search.focus({preventScroll: true});
});

try {
  const saved = localStorage.getItem('cinema-log-cols');
  if ([...columns.options].some(option => option.value === saved)) columns.value = saved;
} catch {
  // The layout control also works when storage is unavailable.
}
grid.dataset.columns = columns.value;
columns.addEventListener('change', () => {
  grid.dataset.columns = columns.value;
  try {
    localStorage.setItem('cinema-log-cols', columns.value);
  } catch {
    // Keep the chosen layout for this visit.
  }
});
document.getElementById('layout').hidden = false;

function observePosters() {
  const posters = grid.querySelectorAll('.poster');
  const reveal = poster => {
    const template = poster.querySelector('template');
    if (template) template.replaceWith(template.content);
  };

  if (!('IntersectionObserver' in window)) {
    posters.forEach(reveal);
    return;
  }

  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      reveal(entry.target);
      observer.unobserve(entry.target);
    }
  }, {rootMargin: '0px 0px 120px'});
  posters.forEach(poster => observer.observe(poster));
}

// Posters can fetch after the hero has decoded, even if the hero failed to load.
document.querySelector('.hero-image').decode().catch(() => {}).then(observePosters);
