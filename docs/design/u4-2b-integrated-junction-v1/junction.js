import { buildFixture } from './fixture.js';
window.addEventListener('error', event => {
  if (event.message) document.querySelector('#labFeedback').textContent = `Error de muestra: ${event.message}`;
});
window.addEventListener('unhandledrejection', event => {
  document.querySelector('#labFeedback').textContent = `Error de muestra: ${event.reason?.stack || event.reason}`;
});
// Only render exports are invoked. Never import bootstrap or the application's
// delegated click dispatcher: this server has no API or write endpoints.
const mount = document.querySelector('#mount');
mount.innerHTML = await (await fetch('/static/index.home.html')).text();
const home = await import('/static/js/surfaces/home.js');
const { todayLocalDate, localDateOffset } = await import('/static/js/core/format.js');
const mode = document.querySelector('#fixtureMode');
const feedback = document.querySelector('#labFeedback');
const root = document.querySelector('#homeView');
function applyMaterial() {
  root.querySelector('.spotlight-layout')?.classList.add('u4-aperture');
  root.querySelectorAll('.home-shelf-bay-plaque').forEach(plaque => plaque.classList.add('u4-plate'));
  root.querySelector('.home-shelf-preview')?.classList.add('u4-aperture');
}
function renderFixture() {
  home.setEditorialHome(home.normalizeEditorialHome(buildFixture(mode.value, todayLocalDate())));
  // No autoplay in this inspection specimen, to keep joins and screenshots stable.
  home.renderEditorialHero();
  home.renderEditorialSections();
  const empty = mode.value === 'empty';
  document.querySelector('#homeFurniture').hidden = empty;
  document.querySelector('.home-videotheque-heading').hidden = empty;
  document.querySelector('#homeEmpty').hidden = !empty;
  root.setAttribute('aria-busy', 'false');
  applyMaterial();
}
mode.addEventListener('change', renderFixture);
root.addEventListener('click', event => {
  const control = event.target.closest('[data-click]');
  if (!control) return;
  const d = control.dataset;
  if (d.click === 'playlist-select') home.selectPlaylistEntry(d.entryKey, true);
  else if (d.click === 'spotlight-select') home.selectSpotlight(Number(d.index), true);
  else if (d.click === 'home-shelf-select') home.selectHomeShelfEntry(d.sectionId, d.entryKey, true);
  else if (d.click === 'home-shelf-activate') home.activateHomeShelf(d.sectionId, true);
  else if (d.click === 'home-shelf-scroll') home.scrollHomeFurniture(d.direction);
  else if (d.click === 'home-date-today' || d.click === 'home-date-yesterday') {
    const date = d.click === 'home-date-today' ? todayLocalDate() : localDateOffset(-1);
    const fixture = buildFixture(mode.value, date);
    home.applyEditorialFeaturedDate(date, {featured: d.click.endsWith('yesterday') ? [...fixture.featured].reverse() : fixture.featured});
    root.querySelector(`[data-click="${d.click}"]`)?.focus({preventScroll:true});
  } else {
    feedback.textContent = `«${control.textContent.trim()}»: acción de la aplicación, fuera de esta muestra. No se abrió ni modificó ningún dato.`;
    feedback.scrollIntoView({block:'nearest'});
  }
  applyMaterial();
});
root.addEventListener('keydown', event => {
  home.moveSpotlightSelector(event);
  home.movePlaylistSelection(event);
  home.moveHomeShelf(event);
  home.moveHomeShelfBay(event);
  applyMaterial();
});
root.addEventListener('load', event => {
  if (event.target.matches('img')) event.target.classList.add('is-loaded');
}, true);
root.addEventListener('error', event => {
  if (!event.target.matches('img')) return;
  event.target.hidden = true;
  const fallback = event.target.nextElementSibling;
  if (fallback) fallback.hidden = false;
}, true);
document.querySelector('#homeSections').addEventListener('scroll', home.syncHomeFurnitureControls, {passive:true});
window.addEventListener('resize', home.syncHomeFurnitureControls);
renderFixture();
