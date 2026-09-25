// Isolated visual adapter over the incumbent renderer. No production state rules
// or asset contract are changed. Deliberately not a deployable second poster.
await import('/legacy.js');
const home = await import('/static/js/surfaces/home.js');
const root = document.querySelector('#homeView');
const stage = document.querySelector('#spotlightStage');
const composition = document.querySelector('#composition');
const imageMode = document.querySelector('#images');
const singleMode = document.querySelector('#single');
const feedback = document.querySelector('#labFeedback');
const dialog = document.querySelector('#previewDetail');
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function mediaMarkup() {
  const mode = imageMode.value;
  const frame = (src, caption, wide = false) => `<figure class="${wide ? 'study-wide' : ''}"><span class="home-furniture-frame"><img src="${src}" alt="${escape(caption)}" decoding="async"><span class="home-furniture-frame-fallback" hidden>No se pudo cargar la imagen</span></span><figcaption>${caption}</figcaption></figure>`;
  const placeholder = label => `<span class="home-furniture-frame"><span class="home-furniture-frame-fallback">${label}</span></span>`;
  let content;
  if (mode === 'two') content = frame('/static/img/night-cinema-ambient-v1.png','Muestra A · ambiente') + frame('/static/img/night-videotheque-wall-v1.png','Muestra B · ambiente');
  else if (mode === 'one' || mode === 'portrait') {
    content = frame(mode === 'portrait' ? '/poster.jpg' : '/static/img/night-cinema-ambient-v1.png', mode === 'portrait' ? 'Prueba vertical · portada de Metropolis' : 'Prueba horizontal · asset de ambiente', singleMode.value === 'wide');
    if (singleMode.value === 'paired') content += placeholder('Sin segunda imagen');
    if (singleMode.value === 'repeat') content += frame(mode === 'portrait' ? '/poster.jpg' : '/static/img/night-cinema-ambient-v1.png','Misma imagen · no hay una segunda disponible');
  } else {
    const copy = mode === 'loading' ? ['Cargando imágenes…','La ficha y sus acciones siguen disponibles.'] : mode === 'error' ? ['No se pudieron cargar las imágenes','Podés consultar la ficha igualmente.'] : ['Sin imágenes de esta obra','La información de la ficha sigue disponible.'];
    content = `<p class="study-empty"${mode === 'loading' ? ' aria-busy="true"' : ''}><strong>${copy[0]}</strong><span>${copy[1]}</span></p>`;
  }
  return `<div class="home-furniture-frame-strip">${content}</div><a href="#previewDetail" data-study-detail>Imágenes y procedencia en la ficha</a>`;
}

function updateMeasurements() {
  const layout = stage.querySelector('.spotlight-layout');
  if (!layout) { document.querySelector('#measurements').textContent = 'Sin obras'; return; }
  const width = selector => Math.round(layout.querySelector(selector).getBoundingClientRect().width);
  document.querySelector('#measurements').textContent = `${window.innerWidth}px · marcos ${width('.spotlight-selector')}px · lista ${width('.spotlight-viewport')}px`;
}

function decorate() {
  const layout = stage.querySelector('.spotlight-layout');
  const preview = stage.querySelector('.spotlight-preview');
  if (!layout || !preview) { updateMeasurements(); return; }
  const viewport = layout.querySelector('.spotlight-viewport');
  const title = preview.querySelector('h3').textContent;
  const isMetropolis = preview.dataset.selectedItemId === 'demo-0';
  layout.querySelector('.study-consulted')?.remove();
  layout.querySelector('.home-consulted-poster')?.remove();
  const right = document.createElement('aside');
  right.className = 'spotlight-selector study-consulted';
  right.setAttribute('aria-label', 'Cartelera de la obra consultada');
  const poster = isMetropolis && document.querySelector('#fixtureMode').value !== 'missing'
    ? `<img class="spotlight-poster" src="/poster.jpg" alt="Portada de Metropolis">`
    : `<span class="spotlight-poster-fallback"><span>${escape(title)}<small>Sin portada</small></span></span>`;
  right.innerHTML = `<div class="spotlight-selector-heading"><span>En consulta</span></div><div class="spotlight-poster-card"><button type="button" class="spotlight-poster-trigger" data-study-detail aria-label="Ver ficha de ${escape(title)}">${poster}</button></div>`;
  layout.append(right);
  if (composition.value === 'bridge') layout.append(preview);
  else viewport.append(preview);
  document.body.dataset.composition = composition.value;
  let media = preview.querySelector('.study-media');
  if (!media) {
    media = document.createElement('section');
    media.className = 'study-media';
    media.setAttribute('aria-label','Imágenes de consulta · prueba visual');
    (preview.querySelector('.home-console-media') || preview.querySelector('.home-furniture-frame-strip')).replaceWith(media);
  }
  media.innerHTML = mediaMarkup();
  if (document.querySelector('#fixtureMode').value === 'sparse') {
    const values = ['Dirección de muestra con un nombre compuesto extenso','Guionista de muestra A; Guionista de muestra B','Intérprete de muestra A; Intérprete de muestra B; Intérprete de muestra C'];
    preview.querySelectorAll('.home-furniture-credits dd').forEach((dd,i) => { dd.textContent = values[i]; });
  }
  // Simulate the approved U5 design in the fixture only; real state remains U4.2d.
  if (preview.dataset.selectionSource?.startsWith('shelf:')) {
    const source = viewport.querySelector('[data-playlist-source]');
    const label = preview.querySelector('.home-console-heading strong').textContent;
    source.textContent = `Selección de ${label}`;
  }
  updateMeasurements();
}
// Only direct renderer replacements trigger this observer, not our descendants.
new MutationObserver(decorate).observe(stage,{childList:true});
for (const input of [composition,imageMode,singleMode]) input.addEventListener('change',decorate);
window.addEventListener('resize',updateMeasurements);
root.addEventListener('click',event => {
  const details = event.target.closest('[data-study-detail],.spotlight-preview-action');
  if (details) {
    event.preventDefault();
    document.querySelector('#detailWork').textContent = stage.querySelector('#spotlight-selected-title')?.textContent || 'Sin obra';
    dialog.showModal();
    feedback.textContent = 'Recorrido de muestra: las imágenes no bloquean la ficha. No hay escritura de datos.';
  }
  const tape = event.target.closest('[data-click="home-shelf-select"]');
  if (tape) {
    home.activateHomeShelf(tape.dataset.sectionId,false);
    feedback.textContent = 'Simulación U5: lista del estante y consulta coordinadas; programación izquierda independiente.';
  }
});
decorate();
