// Pruebas del buscador de Inicio (IP1/IP2) con adaptadores inertes, sin navegador.
// Run: node --experimental-vm-modules --test tests/js/home-search.test.mjs
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';

const base = new URL('../../src/movie_inbox/web/static/js/', import.meta.url);
const searchSource = await readFile(new URL('surfaces/home-search.js', base), 'utf8');
const recentSource = await readFile(new URL('core/recent-searches.js', base), 'utf8');

async function loadModules(fetchImpl) {
  const context = vm.createContext({ URL, URLSearchParams, AbortController, setTimeout, clearTimeout, console, globalThis: {} });
  const recent = new vm.SourceTextModule(recentSource, { context });
  await recent.link(() => { throw new Error('sin imports'); });
  await recent.evaluate();
  const http = new vm.SyntheticModule(['apiFetch'], function () { this.setExport('apiFetch', fetchImpl); }, { context });
  const search = new vm.SourceTextModule(searchSource, { context });
  await search.link((spec) => (spec.endsWith('http.js') ? http : recent));
  await search.evaluate();
  return { search: search.namespace, recent: recent.namespace };
}
const plain = (list) => [...list];
const { search: S, recent: R } = await loadModules(() => { throw new Error('no se usa'); });

function memoryStorage(fail = false) {
  const data = new Map();
  return { data,
    getItem(k) { if (fail) throw new Error('bloqueado'); return data.has(k) ? data.get(k) : null; },
    setItem(k, v) { if (fail) throw new Error('bloqueado'); data.set(k, v); },
    removeItem(k) { if (fail) throw new Error('bloqueado'); data.delete(k); } };
}

test('recientes: tope 5, sin duplicados (sin mayúsculas ni acentos), la más nueva primero', () => {
  const r = R.createRecentSearches('ana', memoryStorage());
  for (const q of ['uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis']) r.add(q);
  assert.deepEqual(plain(r.list()), ['seis', 'cinco', 'cuatro', 'tres', 'dos']);
  r.add('  DOS ');
  assert.deepEqual(plain(r.list()), ['DOS', 'seis', 'cinco', 'cuatro', 'tres']);
  r.add('Amélie'); r.add('amelie');
  assert.equal(r.list()[0], 'amelie');
  assert.equal(r.list().filter((q) => q.toLowerCase().startsWith('am')).length, 1);
  r.remove('SEIS');
  assert.ok(!r.list().includes('seis'));
  r.add('   ');
  r.clear();
  assert.deepEqual(plain(r.list()), []);
  assert.equal(r.key, 'movie-inbox:recent-searches:ana');
});

test('recientes: si localStorage falla o está corrupto no se rompe', () => {
  const r = R.createRecentSearches('ana', memoryStorage(true));
  r.add('x');
  assert.deepEqual(plain(r.list()), []);
  r.remove('x'); r.clear();
  const bad = memoryStorage();
  bad.setItem('movie-inbox:recent-searches:ana', '{no json');
  assert.deepEqual(plain(R.createRecentSearches('ana', bad).list()), []);
  assert.deepEqual(plain(R.createRecentSearches('ana', null).list()), []);
});

test('estados por fila según C1 y rótulos', () => {
  const m = (state, item_id = null) => ({ _membership: { state, item_id } });
  assert.equal(S.rowStateFor(m('present', 'a')), 'present');
  assert.equal(S.rowStateFor(m('missing')), 'missing');
  assert.equal(S.rowStateFor(m('review')), 'review');
  assert.equal(S.rowStateFor({}), 'review', 'sin dato nunca ofrece agregar');
  assert.equal(S.rowStateFor(m('missing'), 'added'), 'added');
  assert.equal(S.STATE_LABELS.missing, '+ Pendiente');
  assert.equal(S.membershipOf(m('present', 'a')).itemId, 'a');
});

test('orden por score, top 3 y empates estables', () => {
  const r = (t, score) => ({ title: t, _search: { score } });
  const top = S.topExternal([r('a', 1), r('b', 9), r('c', 5), r('d', 5), r('e', 7)]);
  assert.deepEqual(plain(top.map((x) => x.title)), ['b', 'e', 'c']);
  assert.equal(S.topExternal([{ title: 'x' }, { title: 'y' }]).length, 2);
});

test('URL de ampliación y detección de enlaces', () => {
  assert.equal(S.buildExpandPath('la ciénaga & más'), '?view=catalog&mode=add&q=la+ci%C3%A9naga+%26+m%C3%A1s');
  assert.equal(S.detectLinkSource('https://www.imdb.com/title/tt1/'), 'imdb');
  assert.equal(S.detectLinkSource('https://es.wikipedia.org/wiki/X'), 'wikipedia');
  assert.equal(S.detectLinkSource('https://notimdb.com/x'), '');
  assert.equal(S.detectLinkSource('https://letterboxd.com/film/x'), '');
  assert.equal(S.detectLinkSource('matrix'), '');
});

// --- Montaje con DOM falso ---
function fakeDom() {
  const input = { value: '', listeners: {}, attrs: {}, addEventListener(t, f) { this.listeners[t] = f; },
    setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; }, focus() {} };
  const panel = { innerHTML: '', hidden: true, listeners: {}, addEventListener(t, f) { this.listeners[t] = f; }, querySelector() { return null; } };
  const status = { textContent: '' };
  const closeButton = { listeners: {}, addEventListener(t, f) { this.listeners[t] = f; } };
  const root = { dataset: {}, querySelector: (sel) => (sel === '[data-close]' ? closeButton : null) };
  const label = { textContent: '' };
  const container = { _html: '', listeners: {}, addEventListener(t, f) { this.listeners[t] = f; }, contains: () => false,
    set innerHTML(v) { this._html = v; }, get innerHTML() { return this._html; },
    querySelector(sel) { return sel === '.hs-input' ? input : sel === '.hs-panel' ? panel : sel === '.hs-status' ? status : sel === '.hs-root' ? root : sel === '.hs-label' ? label : null; } };
  return { container, input, panel, status, root, label, closeButton };
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const key = (dom, k) => { let prevented = false; dom.input.listeners.keydown({ key: key.k = k, preventDefault() { prevented = true; } }); return prevented; };
function type(dom, text) { dom.input.value = text; dom.input.listeners.input(); }
const clickRow = (dom, index) => dom.panel.listeners.click({ target: { closest: (sel) => (sel === '[data-index]' ? { dataset: { index: String(index) } } : null) } });
const json = (body, ok = true, status = 200) => ({ ok, status, json: async () => body });

function harness(handler, extra = {}) {
  const dom = fakeDom();
  const calls = [];
  const events = { previews: [], expands: [], opened: [], added: [] };
  const fetcher = async (url, opts = {}) => { calls.push({ url, opts }); return handler(url, opts); };
  const handle = S.mountHomeSearch(dom.container, {
    fetcher, recents: R.createRecentSearches('t', memoryStorage()), debounce: { local: 5, external: 15 },
    onPreview: (e) => events.previews.push(e), onExpand: (q) => events.expands.push(q),
    onOpenItem: (id) => events.opened.push(id), onAdded: (p) => events.added.push(p), ...extra });
  return { dom, calls, events, handle };
}
const ext = (title, score, state, id = null, extraFields = {}) => ({ title, year: '2000', source: 'tmdb', tmdb_id: title, _search: { score }, _membership: { state, item_id: id }, ...extraFields });
const defaultHandler = (externals) => (url) => (url.includes('external=true')
  ? json({ results: externals, external: { sources: {} } })
  : json({ catalog: { results: [{ id: 'L1', title: 'Local uno', year: '1999' }] } }));

test('campo vacío: Recientes y Sugerencias; sin pedir nada al servidor', () => {
  const sug = [{ key: 's1', title: 'Sugerida', id: 'S1', year: '2001' }];
  const h = harness(() => { throw new Error('no debe pedir'); }, { suggestions: sug });
  h.dom.input.listeners.focus();
  assert.match(h.dom.panel.innerHTML, /Sugerencias/);
  assert.match(h.dom.panel.innerHTML, /Sugerida/);
  assert.doesNotMatch(h.dom.panel.innerHTML, /Recientes/);
  assert.equal(h.calls.length, 0);
});

test('escribir: grupos local y externo con pausas, top 3 por score, fuente rotulada, pie con N', async () => {
  const externals = [ext('A', 1, 'missing'), ext('B', 9, 'present', 'L9'), ext('C', 5, 'review'), ext('D', 7, 'missing')];
  const h = harness(defaultHandler(externals));
  type(h.dom, 'ab');
  await wait(40);
  assert.ok(h.calls.every((c) => !c.url.includes('external=true')), 'bajo 3 caracteres no hay búsqueda externa');
  type(h.dom, 'abc');
  await wait(80);
  const local = h.calls.find((c) => c.url.includes('external=false&catalog=true'));
  assert.ok(local);
  const external = h.calls.find((c) => c.url.includes('external=true&catalog=false&membership=true'));
  assert.ok(external);
  const html = h.dom.panel.innerHTML;
  assert.match(html, /En tu colección/);
  assert.match(html, /Para agregar/);
  assert.match(html, /TMDb/);
  assert.match(html, /Ampliar en Colección \(5\)/);
  assert.ok(html.indexOf('>B<') < html.indexOf('>D<') && html.indexOf('>D<') < html.indexOf('>C<'));
  assert.doesNotMatch(html, />A</, 'sólo los 3 mejores');
  assert.match(h.dom.status.textContent, /1 en tu colección, 4 para agregar/);
});

test('cada tecla aborta las peticiones anteriores', async () => {
  const signals = [];
  const h = harness((url, opts) => { signals.push(opts.signal); return new Promise(() => {}); }, { debounce: { local: 1, external: 2 } });
  type(h.dom, 'matrix');
  await wait(30);
  assert.equal(signals.length, 2);
  type(h.dom, 'matrix r');
  assert.ok(signals.every((s) => s.aborted), 'las viejas quedaron abortadas');
  await wait(30);
  assert.equal(signals.length, 4);
  assert.ok(!signals[2].aborted && !signals[3].aborted);
});

test('«+ Pendiente» sólo con missing: POST /api/add sin force ni target_id; fila pasa a Agregada', async () => {
  const handler = (url, opts) => (url === '/api/add' ? json({ ok: true, reason: 'added', item: { id: 'N1' } })
    : defaultHandler([ext('Nueva', 5, 'missing'), ext('Dudosa', 4, 'review')])(url, opts));
  const h = harness(handler);
  type(h.dom, 'nuev'); await wait(80);
  // fila 0 = local, 1 = Nueva, 2 = Dudosa
  assert.equal((h.dom.panel.innerHTML.match(/\+ Pendiente/g) || []).length, 1);
  clickRow(h.dom, 1); await wait(10);
  const add = h.calls.find((c) => c.url === '/api/add');
  const body = JSON.parse(add.opts.body);
  assert.equal(add.opts.method, 'POST');
  assert.ok(!('action' in body) && !('target_id' in body) && !('_membership' in body));
  assert.match(h.dom.panel.innerHTML, /Agregada/);
  assert.equal(h.events.added.length, 1);
});

test('«Revisar» y «Ya la tenés» nunca escriben; Revisar amplía y la obra presente se abre', async () => {
  const h = harness(defaultHandler([ext('Rev', 5, 'review'), ext('Pres', 4, 'present', 'L7')]));
  type(h.dom, 'abcd'); await wait(80);
  clickRow(h.dom, 1);
  assert.deepEqual(plain(h.events.expands), ['abcd']);
  type(h.dom, 'abcd'); await wait(80);
  clickRow(h.dom, 2);
  assert.deepEqual(plain(h.events.opened), ['L7']);
  assert.ok(h.calls.every((c) => c.url !== '/api/add'));
});

test('respuestas de /api/add: duplicate, merged, possible_duplicate y error con reintento', async () => {
  for (const [reason, label] of [['duplicate', 'Ya la tenés'], ['merged_into_existing', 'Ya la tenés'], ['possible_duplicate', 'Revisar']]) {
    const h = harness((url, opts) => (url === '/api/add' ? json({ ok: false, reason, candidates: [] }) : defaultHandler([ext('X', 5, 'missing')])(url, opts)));
    type(h.dom, 'xxx'); await wait(80);
    clickRow(h.dom, 1); await wait(10);
    assert.match(h.dom.panel.innerHTML, new RegExp(`hs-state-(existing|review)">${label}`), reason);
    const before = h.calls.length;
    clickRow(h.dom, 1); await wait(10);
    if (reason === 'possible_duplicate') {
      assert.equal(h.events.expands.length, 1, 'revisar amplía y no reintenta');
      assert.equal(h.calls.filter((c) => c.url === '/api/add').length, 1);
    }
    assert.ok(h.calls.length >= before);
  }
  let fail = true;
  const h = harness((url, opts) => (url === '/api/add'
    ? (fail ? json({ ok: false, reason: 'boom' }, false, 500) : json({ ok: true, reason: 'added' }))
    : defaultHandler([ext('X', 5, 'missing')])(url, opts)));
  type(h.dom, 'xxx'); await wait(80);
  clickRow(h.dom, 1); await wait(10);
  assert.match(h.dom.panel.innerHTML, /No pudimos guardarla/);
  fail = false;
  clickRow(h.dom, 1); await wait(10);
  assert.match(h.dom.panel.innerHTML, /Agregada/);
});

test('teclado: flechas previsualizan, Enter sin fila amplía y guarda reciente, Escape cierra y repone el póster', async () => {
  const h = harness(defaultHandler([ext('Z', 5, 'missing')]));
  type(h.dom, 'zeta'); await wait(80);
  h.events.previews.length = 0;
  assert.ok(key(h.dom, 'ArrowDown'));
  assert.equal(h.events.previews.at(-1).title, 'Local uno');
  assert.equal(h.dom.input.attrs['aria-activedescendant'], h.dom.panel.innerHTML.match(/id="([^"]+)" role="option" class="hs-row hs-local"/)[1]);
  key(h.dom, 'ArrowDown');
  assert.equal(h.events.previews.at(-1).title, 'Z');
  key(h.dom, 'Escape');
  assert.equal(h.events.previews.at(-1), null);
  assert.equal(h.dom.input.attrs['aria-expanded'], 'false');
  type(h.dom, 'zeta'); await wait(5);
  key(h.dom, 'Enter');
  assert.deepEqual(plain(h.events.expands), ['zeta']);
  assert.deepEqual(plain(R.createRecentSearches('t', memoryStorage()).list()), []);
});

test('una fuente caída avisa sin bloquear «En tu colección»', async () => {
  const h = harness((url) => (url.includes('external=true') ? json({}, false, 502) : json({ catalog: { results: [{ id: 'L1', title: 'Local uno' }] } })));
  type(h.dom, 'caida'); await wait(80);
  assert.match(h.dom.panel.innerHTML, /Local uno/);
  assert.match(h.dom.panel.innerHTML, /fuente externa no respondió/);
});

test('una consulta que es URL rotula el grupo externo con la fuente', async () => {
  const h = harness(defaultHandler([ext('Unica', 5, 'present', 'L1')]));
  type(h.dom, 'https://www.imdb.com/title/tt0133093/'); await wait(80);
  assert.match(h.dom.panel.innerHTML, /Enlace de IMDb/);
  assert.ok(h.calls.some((c) => c.url.includes('external=true')));
});

test('isTextEntryTarget: `/` no roba el foco a campos de texto pero sí a botones y casillas', () => {
  const el = (tagName, extra = {}) => ({ nodeType: 1, tagName, ...extra });
  assert.equal(S.isTextEntryTarget(el('INPUT', { type: 'text' })), true);
  assert.equal(S.isTextEntryTarget(el('INPUT', { type: 'search' })), true);
  assert.equal(S.isTextEntryTarget(el('TEXTAREA')), true);
  assert.equal(S.isTextEntryTarget(el('SELECT')), true);
  assert.equal(S.isTextEntryTarget(el('DIV', { isContentEditable: true })), true);
  assert.equal(S.isTextEntryTarget(el('INPUT', { type: 'checkbox' })), false);
  assert.equal(S.isTextEntryTarget(el('BUTTON')), false);
  assert.equal(S.isTextEntryTarget({ nodeType: 9 }), false);
  assert.equal(S.isTextEntryTarget(null), false);
});

test('el desplegable marca data-open en la raíz, «Cerrar» lo cierra y setEmptyCatalog cambia la etiqueta', async () => {
  const h = harness(() => json({ catalog: { results: [] } }), { suggestions: [{ title: 'Sugerida', year: '2001', id: 'S1' }] });
  h.dom.input.listeners.focus();
  assert.equal(h.dom.root.dataset.open, 'true');
  h.dom.closeButton.listeners.click();
  assert.equal(h.dom.root.dataset.open, 'false');
  assert.equal(h.events.previews.at(-1), null, 'el póster vuelve a la sugerencia');
  h.handle.setEmptyCatalog(true);
  assert.match(h.dom.label.textContent, /primera película/);
  h.handle.setEmptyCatalog(false);
  assert.match(h.dom.label.textContent, /Buscar una película/);
});
