import { buildFixture as baseFixture } from './fixture.js';
const mount = document.querySelector('#mount');
const parser = new DOMParser();
const [shell, markup] = await Promise.all([
  fetch('/static/index.shell-open.html').then(r => r.text()),
  fetch('/static/index.home.html').then(r => r.text())
]);
const shellDocument = parser.parseFromString(shell, 'text/html');
mount.replaceChildren(shellDocument.querySelector('.app-header'));
mount.insertAdjacentHTML('beforeend', markup);
mount.querySelector('h1').textContent = 'Movie Inbox';
document.querySelector('#currentUserInitial').textContent = 'DE';
document.querySelector('#currentUserLabel').textContent = 'Demo';
document.querySelector('#currentUserName').textContent = 'Muestra visual';
document.querySelector('#currentCatalogName').textContent = 'Archivo de demostración';
const home = await import('/static/js/surfaces/home.js');
const { todayLocalDate, localDateOffset } = await import('/static/js/core/format.js');
const mode = document.querySelector('#fixtureMode');
const feedback = document.querySelector('#labFeedback');
const root = document.querySelector('#homeView');
document.querySelector('#advanceRotation').addEventListener('click',()=>{
  const advanced = home.tickHomeAutoplay();
  const state = home.getHomePlaybackState();
  feedback.textContent = `${advanced ? 'Póster avanzado' : 'Rotación pausada (visibilidad, foco o movimiento reducido)'}. Consulta: ${document.querySelector('#spotlight-selected-title')?.textContent || 'sin obra'} · fuente ${state.selectionSource}.`;
});
function fixture(date) {
  const data = baseFixture(mode.value, date);
  if (mode.value === 'populated' || mode.value === 'missing') {
    const names = ['Un verano en la estación','La casa de las cintas','El mapa del silencio','Después de medianoche','La memoria del agua','Último tren al sur'];
    data.sections.push({id:'anniversary',title:'Estrenadas un día como hoy',action:{kind:'catalog',label:'Ver colección',filters:{}},items:names.map((title,index)=>({key:`extra-${index}`,origin:{kind:'catalog'},reason:{label:'Muestra visual'},item:{id:`extra-${index}`,title,year:String(1990+index),kind:'película',status:'pending',en_catalogo:false,description:'Ficha sintética para comprobar la composición del archivo.'}}))});
  }
  return data;
}
function renderFixture() {
  const data = fixture(todayLocalDate());
  home.setEditorialHome(home.normalizeEditorialHome(data));
  home.renderEditorialHero();
  home.renderEditorialSections();
  const empty = mode.value === 'empty';
  document.querySelector('#homeFurniture').hidden = empty;
  document.querySelector('.home-videotheque-heading').hidden = empty;
  document.querySelector('#homeEmpty').hidden = !empty;
  root.setAttribute('aria-busy','false');
  document.querySelector('#stats').textContent = `${empty ? 0 : mode.value === 'sparse' ? 2 : 24} obras · muestra de diseño`;
}
mode.addEventListener('change',renderFixture);
root.addEventListener('click',event=>{
  const control = event.target.closest('[data-click]');
  if (!control) return;
  const d = control.dataset;
  if (d.click === 'playlist-select') home.selectPlaylistEntry(d.entryKey,true);
  else if (d.click === 'spotlight-select') home.selectSpotlight(Number(d.index),true);
  else if (d.click === 'home-shelf-select') {
    home.selectHomeShelfEntry(d.sectionId,d.entryKey,true);
    feedback.textContent = `Consola superior: ${document.querySelector('#spotlight-selected-title')?.textContent || 'sin obra'}. La programación no cambió.`;
  } else if (d.click === 'home-shelf-activate') home.activateHomeShelf(d.sectionId,true);
  else if (d.click === 'home-shelf-scroll') home.scrollHomeFurniture(d.direction);
  else if (d.click === 'home-date-today' || d.click === 'home-date-yesterday') {
    const date = d.click.endsWith('yesterday') ? localDateOffset(-1) : todayLocalDate();
    const data = fixture(date);
    home.applyEditorialFeaturedDate(date,{featured:d.click.endsWith('yesterday') ? [...data.featured].reverse() : data.featured});
  } else feedback.textContent = `«${control.textContent.trim()}»: fuera de la muestra visual; no se abrió ni modificó ningún dato.`;
});
mount.querySelector('.app-header').addEventListener('click',event=>{
  const control = event.target.closest('button,a');
  if (!control) return;
  event.preventDefault();
  feedback.textContent = 'La navegación exterior se conserva como referencia de escala; esta muestra no accede al catálogo.';
});
root.addEventListener('keydown',event=>{
  home.moveSpotlightSelector(event);
  home.movePlaylistSelection(event);
  home.moveHomeShelf(event);
  home.moveHomeShelfBay(event);
});
root.addEventListener('load',event=>{
  if (event.target.matches('img')) event.target.classList.add('is-loaded');
},true);
root.addEventListener('error',event=>{
  if (!event.target.matches('img')) return;
  event.target.hidden=true;
  if (event.target.nextElementSibling) event.target.nextElementSibling.hidden=false;
},true);
document.querySelector('#homeSections').addEventListener('scroll',home.syncHomeFurnitureControls,{passive:true});
window.addEventListener('resize',home.syncHomeFurnitureControls);
window.addEventListener('error',event=>{ if (event.message) feedback.textContent=`Error de muestra: ${event.message}`; });
window.addEventListener('unhandledrejection',event=>{ feedback.textContent=`Error de muestra: ${event.reason?.message || event.reason}`; });
renderFixture();
