// Exercise the real Home module with inert DOM/dependency adapters, not a browser.
// Run: node --experimental-vm-modules --test tests/js/home-selection.test.mjs
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
import { sourceFixture } from './fixtures/home-sources.mjs';

const source = await readFile(new URL('../../src/movie_inbox/web/static/js/surfaces/home.js', import.meta.url), 'utf8');
function element() {
  return { innerHTML:'', hidden:false, dataset:{}, scrollLeft:0, scrollTop:0,
    clientWidth:1000, scrollWidth:1000, classList:{toggle(){}},
    append(){}, showModal(){}, focus(){}, setAttribute(){}, removeAttribute(){}, querySelector(){return null;},
    querySelectorAll(){return [];}, contains(){return false;} };
}
async function setup(overrides = {}) {
  const fields = new Proxy({}, {get(target,key){return target[key] ||= element();}});
  const document = {activeElement:null,visibilityState:'visible',querySelectorAll:()=>[]};
  const window = {matchMedia:()=>({matches:false}),setInterval:()=>1,clearInterval(){}};
  const context = vm.createContext({document,window,requestAnimationFrame(){},CSS:{escape:String},console});
  const home = new vm.SourceTextModule(source,{context});
  const values = {
    fields, displayTitle:item=>item?.title || '', escapeHtml:String, escapeAttr:String,
    firstListValue:value=>Array.isArray(value) ? value[0] : value || '',
    listText:value=>Array.isArray(value) ? value.join(', ') : value || '',
    availabilityState:item=>({effective:!!item?.en_catalogo}),
    todayLocalDate:()=> '2026-09-10',localDateOffset:()=> '2026-09-09',
    cachedImageSrc:String,posterVariant:()=>0,
    ...overrides,
  };
  await home.link(specifier=>{
    const declaration = [...source.matchAll(/import\s*\{([^}]+)\}\s*from\s*"([^"]+)"/g)].find(match=>match[2]===specifier);
    const names = declaration[1].split(',').map(name=>name.trim());
    return new vm.SyntheticModule(names,function(){
      for (const name of names) this.setExport(name,values[name] ?? (()=>{}));
    },{context});
  });
  await home.evaluate();
  const api = home.namespace;
  const entry = (key,title,origin='catalog',id=key)=>({key,item:{id,title,year:'2000',status:'pending'},origin:{kind:origin}});
  const data = {generated_for:'2026-09-10',featured:[entry('daily-a','Diaria A'),entry('daily-b','Diaria B')],
    sections:[{id:'memory',title:'Memoria',items:[entry('memory-a','Recuerdo A'),entry('memory-b','Recuerdo B')]},
      {id:'club',title:'Club',items:[entry('daily-a','Obra del Club','collection','daily-a')]}],warnings:[]};
  api.setEditorialHome(data);
  api.renderEditorialHero();
  return {api,fields,data,document,window};
}

test('U5 deliberate VHS selection consults its work; the daily suggestion stays independent',async()=>{
  const {api,fields} = await setup();
  assert.match(fields.spotlightStage.innerHTML,/<h3 id="spotlight-selected-title">Diaria A<\/h3>/);
  assert.match(fields.spotlightStage.innerHTML,/<span>Sugerencia<\/span>/);
  api.selectHomeShelfEntry('memory','memory-b');
  let state = api.getHomePlaybackState();
  assert.equal(state.selectionSource,'shelf:memory');
  assert.equal(state.selectedEntryKey,'memory-b');
  assert.equal(state.playlistSource,'shelf:memory');
  assert.match(fields.spotlightStage.innerHTML,/<h3 id="spotlight-selected-title">Recuerdo B<\/h3>/);
  assert.match(fields.spotlightStage.innerHTML,/<span>Tu selección<\/span>/);
  assert.doesNotMatch(fields.spotlightStage.innerHTML,/data-playlist-entry|spotlight-playlist|spotlight-table-wrap/);
  api.returnHomeProgramming();
  assert.equal(api.getHomePlaybackState().selectionSource,'daily');
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'daily-a');
  assert.match(fields.spotlightStage.innerHTML,/<h3 id="spotlight-selected-title">Diaria A<\/h3>/);
});

test('IP1 carousel, autoplay and day tabs are gone from the module and the markup',async()=>{
  const {api,fields} = await setup();
  assert.doesNotMatch(source,/HOME_AUTOPLAY_INTERVAL_MS|setInterval|syncHomeAutoplay|ensureCarousel|homeDateControlMarkup/);
  assert.doesNotMatch(fields.spotlightStage.innerHTML,/data-click="spotlight-select"|home-date-|spotlight-date|spotlight-playlist|home-programming-return/);
  // bootstrap.js todavía los importa hasta T5: siguen exportados, pero inertes.
  for (const name of ['tickHomeAutoplay','selectSpotlight','selectPlaylistEntry','moveSpotlightSelector','movePlaylistSelection']) assert.equal(api[name](),name === 'tickHomeAutoplay' ? false : undefined,name);
  assert.deepEqual(Array.from(Object.keys(api.getHomePlaybackState())).sort(),['activeShelfId','playlistSource','selectedEntryKey','selectedItemId','selectionSource']);
  const html=await readFile(new URL('../../src/movie_inbox/web/static/index.home.html',import.meta.url),'utf8');
  assert.match(html,/<div id="homeSearchSlot" class="home-search-slot"><\/div>/);
  assert.match(html,/id="homeConsultation"/);
  assert.doesNotMatch(html,/homeDate|home-date|spotlight-date|spotlight-viewport|home-loading-rows/);
});

test('source-qualified keys preserve Club provenance and omit personal edit action',async()=>{
  const {api,fields} = await setup();
  api.selectHomeShelfEntry('club','daily-a');
  assert.match(fields.spotlightStage.innerHTML,/>Obra del Club<\/h3>/);
  assert.match(fields.spotlightStage.innerHTML,/data-click="open-home-collection-detail" data-key="daily-a"/);
  assert.doesNotMatch(fields.spotlightStage.innerHTML,/data-click="edit-home-shelf-entry"/);
  api.openHomeCollectionDetail('daily-a','shelf:club');
  assert.match(fields.sharedDetailBody.innerHTML,/>Obra del Club<\/h2>/);
  api.returnHomeProgramming();
  assert.match(fields.spotlightStage.innerHTML,/>Diaria A<\/h3>/);
  assert.match(fields.spotlightStage.innerHTML,/data-click="edit-home-shelf-entry"/);
});

test('explicit shelf and day changes retain their intentional reset semantics',async()=>{
  const {api,data} = await setup();
  api.selectHomeShelfEntry('memory','memory-b');
  api.activateHomeShelf('memory');
  assert.equal(api.getHomePlaybackState().playlistSource,'shelf:memory');
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'memory-b');
  api.selectHomeShelfEntry('memory','memory-a');
  assert.equal(api.homeShelfSelections.get('memory'),0);
  api.returnHomeProgramming();
  assert.equal(api.getHomePlaybackState().playlistSource,'daily');
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'daily-a');
  api.selectHomeShelfEntry('memory','memory-b');
  api.applyEditorialFeaturedDate('2026-09-09',{featured:[data.featured[1]]});
  assert.equal(api.getHomePlaybackState().selectionSource,'daily');
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'daily-b');
});

test('invalid or removed selection and empty daily list do not produce stale detail actions',async()=>{
  const {api,data,fields} = await setup();
  api.selectHomeShelfEntry('missing','unknown');
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'daily-a');
  api.selectHomeShelfEntry('memory','memory-b');
  data.sections[0].items.pop();
  api.renderEditorialHero();
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'memory-a');
  data.featured=[];
  api.selectHomeShelfEntry('memory','memory-a');
  assert.match(fields.spotlightStage.innerHTML,/>Recuerdo A<\/h3>/);
  api.setEditorialHome({...data,sections:[]});
  api.renderEditorialHero();
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'');
  assert.doesNotMatch(fields.spotlightStage.innerHTML,/data-click="edit-home-shelf-entry"/);
  assert.match(fields.spotlightStage.innerHTML,/home-desk-note/);
});

test('keyboard handles fallback entry keys on the shelf',async()=>{
  const {api,data} = await setup();
  delete data.sections[0].items[1].key;
  let prevented = false;
  api.moveHomeShelf({key:'ArrowRight',preventDefault(){prevented=true;},
    target:{closest:()=>({dataset:{sectionId:'memory',entryIndex:'0'}})}});
  assert.equal(prevented,true);
  assert.equal(api.getHomePlaybackState().selectedItemId,'memory-b');
});

test('a rerender restores the focused console action without changing the consulted entry',async()=>{
  const {api,fields,document} = await setup();
  api.selectHomeShelfEntry('memory','memory-b');
  const oldAction = {dataset:{click:'edit-home-shelf-entry',homeFocus:'consultation-edit'}};
  document.activeElement=oldAction;
  let replaced=false;
  let markup=fields.spotlightStage.innerHTML;
  Object.defineProperty(fields.spotlightStage,'innerHTML',{
    get:()=>markup,set:value=>{markup=value;replaced=true;}
  });
  fields.spotlightStage.contains=element=>element===oldAction && !replaced;
  let restored=false;
  fields.spotlightStage.querySelector=selector=>selector==='[data-home-focus="consultation-edit"]'
    ? {focus:()=>{restored=true;}} : null;
  api.renderEditorialHero();
  assert.equal(restored,true);
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'memory-b');
});

test('the render never rewrites the search slot: it writes inside #homeConsultation only',async()=>{
  const {api,fields} = await setup();
  const host=Object.assign({},fields.spotlightStage,{innerHTML:'',contains:()=>false,querySelector:()=>null});
  fields.spotlightStage.querySelector=selector=>selector==='#homeConsultation'?host:null;
  const stageBefore=fields.spotlightStage.innerHTML;
  api.selectHomeShelfEntry('memory','memory-b');
  assert.match(host.innerHTML,/>Recuerdo B<\/h3>/);
  assert.equal(fields.spotlightStage.innerHTML,stageBefore);
  assert.doesNotMatch(host.innerHTML,/homeSearchSlot/);
});

test('the single console carries summary, credits, facts and category navigation without duplicate images',async()=>{
  const {api,data,fields} = await setup();
  data.sections[0].action={kind:'catalog',label:'Ver colección'};
  Object.assign(data.sections[0].items[1].item,{
    description:'Una sinopsis de muestra',directors:['Dirección'],writers:['Guion'],
    cast:['Reparto'],duration_minutes:104,backdrop_image:'/panorama.jpg',page_image:'/portada.jpg'
  });
  api.selectHomeShelfEntry('memory','memory-b');
  const html=fields.spotlightStage.innerHTML;
  assert.equal((html.match(/class="spotlight-preview"/g)||[]).length,1);
  for(const text of ['Una sinopsis de muestra','Dirección','Guion','Reparto','104 min','/portada.jpg']) assert.ok(html.includes(text),text);
  assert.doesNotMatch(api.homeSelectionPreview(data.sections[0].items[1]),/<img|panorama.jpg|portada.jpg/);
  assert.match(html,/data-click="home-section-action" data-section-id="memory"/);
  assert.doesNotMatch(html,/home-shelf-preview|spotlight-signal|spotlight-preview-cover/);
  assert.equal(fields.homeSelectionAnnouncement.textContent,'Consulta: Recuerdo B');
  api.activateHomeShelf('memory');
  assert.equal(fields.homeSelectionAnnouncement.textContent,'Consulta: Recuerdo B');
  api.applyEditorialFeaturedDate('2026-09-09',{featured:[data.featured[0]]});
  assert.equal(fields.homeSelectionAnnouncement.textContent,'Consulta: Diaria A');
  api.setEditorialHome({...data,featured:[],sections:[]});
  assert.equal(fields.homeSelectionAnnouncement.textContent,'');
});

test('missing information stays honest and the retired host is absent from production HTML',async()=>{
  const {api,fields} = await setup();
  assert.match(fields.spotlightStage.innerHTML,/Todavía no hay una sinopsis/);
  assert.match(fields.spotlightStage.innerHTML,/Sin portada/);
  assert.doesNotMatch(fields.spotlightStage.innerHTML,/Créditos por completar|data-image-count/);
  assert.equal(api.homeSelectionPreview(null),'');
  const html=await readFile(new URL('../../src/movie_inbox/web/static/index.home.html',import.meta.url),'utf8');
  assert.doesNotMatch(html,/id="homeShelfPreview"/);
  assert.match(html,/id="homeSelectionAnnouncement"[^>]*aria-live="polite"/);
});

test('consulted poster follows source-qualified selection',async()=>{
  const {api,fields,data} = await setup();
  data.sections[0].items[1].item.page_image='/memory.jpg';
  api.selectHomeShelfEntry('memory','memory-b');
  let poster = api.homeConsultedPoster(data.sections[0].items[1]);
  assert.match(poster,/data-consulted-source="shelf:memory"/);
  assert.match(poster,/src="\/memory.jpg"/);
  api.selectHomeShelfEntry('club','daily-a');
  poster = api.homeConsultedPoster(data.sections[1].items[0]);
  assert.match(poster,/data-click="open-home-collection-detail" data-key="daily-a" data-source="shelf:club"/);
  assert.doesNotMatch(poster,/memory.jpg|data-id=/);
  assert.match(poster,/Obra del Club/);
  assert.match(poster,/Sin portada/);
  assert.equal(api.homeConsultedPoster(null),'');
  assert.equal((fields.spotlightStage.innerHTML.match(/class="spotlight-preview"/g)||[]).length,1);
});

test('summary remains open across selection and day changes; a new catalog starts collapsed',async()=>{
  const {api,fields,data} = await setup();
  const toggle = {setAttribute(name,value){this[name]=value;}};
  const body = {setAttribute(name,value){this[name]=value;},inert:true};
  const preview = {dataset:{},querySelector:selector=>selector==='#homeSelectionSummary' ? body : toggle};
  fields.spotlightStage.querySelector=selector=>selector==='.spotlight-preview' ? preview : null;
  assert.match(fields.spotlightStage.innerHTML,/aria-expanded="false"/);
  api.toggleHomeSummary();
  assert.equal(toggle['aria-expanded'],'true');
  assert.equal(body.inert,false);
  api.selectHomeShelfEntry('memory','memory-b');
  api.previewHomeEntry({id:'x',title:'Resultado X'});
  assert.match(fields.spotlightStage.innerHTML,/data-summary-open="true"/);
  assert.match(fields.spotlightStage.innerHTML,/aria-hidden="false">\s*<div class="home-console-disclosure-clip"/);
  api.applyEditorialFeaturedDate('2026-09-09',{featured:[data.featured[0]]});
  assert.match(fields.spotlightStage.innerHTML,/data-summary-open="true"/);
  api.toggleHomeSummary();
  assert.equal(body.inert,true);
  assert.equal(body['aria-hidden'],'true');
  api.returnHomeProgramming();
  assert.match(fields.spotlightStage.innerHTML,/aria-hidden="true" inert/);
  api.toggleHomeSummary();
  api.setEditorialHome(data);
  api.renderEditorialHero();
  assert.match(fields.spotlightStage.innerHTML,/data-summary-open="false"/);
});

test('rerender restores the originating home surface when poster and console share an action',async()=>{
  for (const surface of ['consultation-poster','consultation-view','consultation-summary','consultation-edit']) {
    const {api,fields,document}=await setup();
    const oldAction={dataset:{click:'open-detail-with-case-transition',homeFocus:surface}};
    document.activeElement=oldAction;
    let replaced=false,restored=false,markup=fields.spotlightStage.innerHTML;
    Object.defineProperty(fields.spotlightStage,'innerHTML',{get:()=>markup,set:value=>{markup=value;replaced=true;}});
    fields.spotlightStage.contains=element=>element===oldAction&&!replaced;
    fields.spotlightStage.querySelector=selector=>selector===`[data-home-focus="${surface}"]` ? {focus:()=>{restored=true;}} : null;
    api.renderEditorialHero();
    assert.equal(restored,true,surface);
  }
});

test('quick consultation uses source-qualified detail and never mistakes editorial reasons for synopsis',async()=>{
  const {api,fields,data}=await setup();
  data.sections[0].items[1].reason={detail:'Disponible por tu biblioteca'};
  api.selectHomeShelfEntry('memory','memory-b');
  assert.match(fields.spotlightStage.innerHTML,/data-home-focus="consultation-view" data-click="open-detail-with-case-transition"/);
  assert.match(fields.spotlightStage.innerHTML,/Todavía no hay una sinopsis/);
  assert.doesNotMatch(api.homeSelectionPreview(data.sections[0].items[1]),/Disponible por tu biblioteca/);
  api.selectHomeShelfEntry('club','daily-a');
  const html=fields.spotlightStage.innerHTML;
  assert.match(html,/data-home-focus="consultation-view" data-click="open-home-collection-detail" data-key="daily-a" data-source="shelf:club"/);
  assert.doesNotMatch(html,/data-click="edit-home-shelf-entry"/);
});

test('C3 previewHomeEntry shows a local work in the poster and null returns to the daily suggestion',async()=>{
  const {api,fields,data}=await setup();
  data.featured[0].item.page_image='/dia.jpg';
  api.previewHomeEntry({key:'memory-b',item:{id:'memory-b',title:'Recuerdo B',year:'2000',page_image:'/b.jpg'},origin:{kind:'catalog'}});
  let state=api.getHomePlaybackState();
  assert.equal(state.selectionSource,'preview');
  assert.equal(state.selectedEntryKey,'memory-b');
  assert.equal(state.selectedItemId,'memory-b');
  let html=fields.spotlightStage.innerHTML;
  assert.match(html,/<span>Resultado<\/span>/);
  assert.match(html,/>Recuerdo B<\/h3>/);
  assert.match(html,/src="\/b.jpg"/);
  assert.match(html,/data-click="open-detail-with-case-transition" data-id="memory-b"/);
  assert.equal(fields.homeSelectionAnnouncement.textContent,'Consulta: Recuerdo B');
  api.previewHomeEntry(null);
  state=api.getHomePlaybackState();
  assert.equal(state.selectionSource,'daily');
  assert.equal(state.selectedEntryKey,'daily-a');
  assert.match(fields.spotlightStage.innerHTML,/>Diaria A<\/h3>/);
  assert.match(fields.spotlightStage.innerHTML,/src="\/dia.jpg"/);
});

test('C3 a flat external result has no local record: static poster, no detail, no personal state',async()=>{
  const {api,fields}=await setup();
  api.previewHomeEntry({title:'Película externa',year:'1999',page_image:'/ext.jpg',_membership:{state:'missing',item_id:null}});
  const html=fields.spotlightStage.innerHTML;
  assert.match(html,/>Película externa<\/h3>/);
  assert.match(html,/src="\/ext.jpg"/);
  assert.match(html,/spotlight-poster-trigger is-static/);
  assert.doesNotMatch(html,/open-detail-with-case-transition|open-home-collection-detail|edit-home-shelf-entry|consultation-view/);
  assert.doesNotMatch(html,/Disponible|Pendiente|Vista|Estado resumido/);
  assert.match(html,/Resultado de búsqueda/);
  // Una flat con item_id local sí es una obra del archivo.
  api.previewHomeEntry({title:'Ya la tengo',item_id:'memory-a'});
  assert.match(fields.spotlightStage.innerHTML,/data-click="open-detail-with-case-transition" data-id="memory-a"/);
  assert.equal(api.getHomePlaybackState().selectedItemId,'memory-a');
  api.previewHomeEntry({});
  assert.equal(api.getHomePlaybackState().selectionSource,'daily');
});

test('C3 previewHomeEntry(null) without an active preview keeps a VHS chosen by hand; a preview clears the VHS mark',async()=>{
  const {api,fields}=await setup();
  api.selectHomeShelfEntry('memory','memory-b');
  api.previewHomeEntry(null);
  assert.equal(api.getHomePlaybackState().selectionSource,'shelf:memory');
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'memory-b');
  api.previewHomeEntry({id:'zzz',title:'Otra'});
  assert.equal(api.getHomePlaybackState().selectionSource,'preview');
  assert.doesNotMatch(fields.homeSections.innerHTML,/data-vhs-state="selected"/);
  api.previewHomeEntry(null);
  assert.equal(api.getHomePlaybackState().playlistSource,'daily');
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'daily-a');
});

test('C3 a preview survives day refresh only until the programming is replaced',async()=>{
  const {api,data}=await setup();
  api.previewHomeEntry({id:'zzz',title:'Otra'});
  api.setEditorialHome(data);
  assert.equal(api.getHomePlaybackState().selectionSource,'daily');
  api.renderEditorialHero();
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'daily-a');
});

test('homeSuggestions orders available daily first, then followed-collection gaps, without repeats',async()=>{
  const {api,data}=await setup();
  const entry=(key,title,origin='catalog',en_catalogo=false,id=key)=>({key,item:{id,title,year:'2001',en_catalogo},origin:{kind:origin}});
  api.setEditorialHome({...data,
    featured:[entry('f1','No disponible'),entry('f2','Disponible 1','catalog',true),entry('f3','Disponible 2','catalog',true)],
    sections:[
      {id:'a',title:'A',items:[entry('c1','Falta 1','collection'),entry('f2','Disponible 1','catalog',true),entry('s1','Estante 1')]},
      {id:'b',title:'B',items:[entry('c2','Falta 2','collection'),entry('c1','Falta 1','collection')]}]});
  assert.deepEqual(Array.from(api.homeSuggestions(),e=>e.item.title),['Disponible 1','Disponible 2','Falta 1','Falta 2','No disponible']);
  assert.deepEqual(Array.from(api.homeSuggestions(3),e=>e.item.title),['Disponible 1','Disponible 2','Falta 1']);
  assert.equal(api.homeSuggestions(99).length,5);
  assert.equal(api.homeSuggestions(0).length,0);
  // Una obra de catálogo y otra del Club con el mismo id no se confunden.
  api.setEditorialHome({...data,featured:[entry('x','Local','catalog',true,'7')],sections:[{id:'a',title:'A',items:[entry('y','Del Club','collection',false,'7')]}]});
  assert.deepEqual(Array.from(api.homeSuggestions(),e=>e.item.title),['Local','Del Club']);
  api.setEditorialHome({...data,featured:[],sections:[]});
  assert.equal(api.homeSuggestions().length,0);
});

test('homeSuggestions fills from the whole program when too little is available',async()=>{
  const {api}=await setup();
  assert.deepEqual(Array.from(api.homeSuggestions(),e=>e.item.title),['Obra del Club','Diaria A','Diaria B','Recuerdo A','Recuerdo B']);
});

test('U5 shelf selection is honest for 0, 1, 6, 20 and 100 editorial entries',async()=>{
  for (const count of [0,1,6,20,100]) {
    const {api,fields}=await setup();
    const data=sourceFixture(count);
    api.setEditorialHome(data);
    api.renderEditorialHero();
    assert.equal(api.activateHomeShelf('sample'),count>0);
    if (count>0) {
      api.selectHomeShelfEntry('sample',`shared-${count-1}`);
      assert.doesNotMatch(fields.spotlightStage.innerHTML,/data-playlist-entry=|spotlight-playlist/);
      assert.match(fields.homeSections.innerHTML,new RegExp(`${count} ${count===1?'título':'títulos'}`));
      assert.equal(api.getHomePlaybackState().selectedEntryKey,`shared-${count-1}`);
    }
    api.returnHomeProgramming();
    assert.match(fields.spotlightStage.innerHTML,/<span>Sugerencia<\/span>/);
    api.selectHomeShelfEntry('club','shared-0');
    assert.equal(api.getHomePlaybackState().selectionSource,'shelf:club');
    assert.match(fields.spotlightStage.innerHTML,/>Club 1<\/h3>/);
    assert.doesNotMatch(fields.spotlightStage.innerHTML,/data-click="edit-home-shelf-entry"/);
  }
});

test('U5 returning to programming focuses the poster only when asked and keeps the daily suggestion',async()=>{
  const {api,fields}=await setup();
  api.selectHomeShelfEntry('memory','memory-b');
  let focused=false;
  fields.spotlightStage.querySelector=selector=>selector==='[data-home-focus="consultation-poster"]' ? {focus(){focused=true;}} : null;
  api.returnHomeProgramming();
  assert.equal(focused,false);
  api.selectHomeShelfEntry('memory','memory-b');
  api.returnHomeProgramming(true);
  assert.equal(focused,true);
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'daily-a');
  api.activateHomeShelf('memory');
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'memory-b');
  await api.loadEditorialFeaturedDate('2026-09-10');
  assert.equal(api.getHomePlaybackState().playlistSource,'daily');
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'daily-a');
});

test('U5 passive Tab does not select, and each shelf has a semantic plaque and roving stop',async()=>{
  const {api,fields}=await setup();
  api.renderEditorialSections();
  const before=JSON.stringify(api.getHomePlaybackState());
  api.moveHomeShelf({key:'Tab',target:{closest:()=>({dataset:{sectionId:'memory',entryIndex:'0'}})},preventDefault(){assert.fail('Tab is native');}});
  assert.equal(JSON.stringify(api.getHomePlaybackState()),before);
  const html=fields.homeSections.innerHTML;
  assert.match(html,/<h2[^>]+><button[^>]+data-click="home-shelf-activate"/);
  assert.doesNotMatch(html,/<section[^>]+data-click=/);
  assert.equal((html.match(/tabindex="0"/g)||[]).length,2);
  api.activateHomeShelf('memory');
  assert.match(fields.homeSections.innerHTML,/data-click="home-shelf-activate" data-section-id="memory" aria-pressed="true"/);
});

test('U5 removed source recovers to the daily suggestion; an emptied source shows the empty desk',async()=>{
  const {api,data,fields}=await setup();
  api.selectHomeShelfEntry('memory','memory-b');
  data.sections[0].items=[];
  api.renderEditorialHero();
  assert.equal(api.getHomePlaybackState().playlistSource,'shelf:memory');
  assert.doesNotMatch(fields.spotlightStage.innerHTML,/data-click="edit-home-shelf-entry"/);
  assert.match(fields.spotlightStage.innerHTML,/home-desk-note/);
  data.sections.splice(0,1);
  api.renderEditorialHero();
  assert.equal(api.getHomePlaybackState().playlistSource,'daily');
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'daily-a');
  assert.match(fields.homeSelectionAnnouncement.textContent,/Volvimos a la sugerencia del día/);
});

test('U5 shelf memory survives reordering and falls back after removal',async()=>{
  const {api,data}=await setup();
  api.selectHomeShelfEntry('memory','memory-b');
  api.returnHomeProgramming();
  data.sections[0].items.reverse();
  api.activateHomeShelf('memory');
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'memory-b');
  assert.equal(api.homeShelfSelections.get('memory'),0);
  api.returnHomeProgramming();
  data.sections[0].items.shift();
  api.activateHomeShelf('memory');
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'memory-a');
});

test('U5 local alignment never calls scrollIntoView or crosses a source boundary',async()=>{
  const {api,fields}=await setup();
  const spine={getBoundingClientRect:()=>({left:150,right:200}),closest:()=>null,scrollIntoView(){assert.fail('document scroll');}};
  fields.homeSections.getBoundingClientRect=()=>({left:0,right:100});
  fields.homeSections.querySelector=selector=>{
    assert.match(selector,/data-section-id="club"/);
    return spine;
  };
  api.selectHomeShelfEntry('club','daily-a');
  assert.equal(fields.homeSections.scrollLeft,100);
});

test('U5 resizing keeps a focused spine visible without changing selection or moving focus',async()=>{
  const {api,fields,document}=await setup();
  api.selectHomeShelfEntry('memory','memory-b');
  const spine={getBoundingClientRect:()=>({left:-30,right:20}),closest:()=>null,focus(){assert.fail('resize should not refocus');}};
  fields.homeSections.getBoundingClientRect=()=>({left:0,right:100});
  fields.homeSections.querySelector=()=>spine;
  fields.homeSections.scrollLeft=50;
  document.activeElement={matches:()=>true};
  api.handleHomeResize();
  assert.equal(fields.homeSections.scrollLeft,20);
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'memory-b');
  document.activeElement={matches:()=>false};
  api.handleHomeResize();
  assert.equal(fields.homeSections.scrollLeft,20);
});

test('U5 a delayed day response cannot replace a newer deliberate shelf selection',async()=>{
  let resolve;
  const response=new Promise(done=>{resolve=done;});
  const {api,data,fields}=await setup({apiFetch:()=>response});
  const pending=api.loadEditorialFeaturedDate('2026-09-09');
  api.selectHomeShelfEntry('memory','memory-b');
  resolve({ok:true,json:async()=>({...data,generated_for:'2026-09-09'})});
  await pending;
  assert.equal(api.getHomePlaybackState().playlistSource,'shelf:memory');
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'memory-b');
  assert.equal(api.editorialHome.generated_for,'2026-09-10');
  assert.equal(fields.homeFeedback.hidden,true);
});

test('U5 returning to the current day cancels an older request and ignores its failure',async()=>{
  let reject;
  const {api,fields}=await setup({apiFetch:()=>new Promise((_resolve,fail)=>{reject=fail;})});
  const pending=api.loadEditorialFeaturedDate('2026-09-09');
  await api.loadEditorialFeaturedDate('2026-09-10');
  reject(new Error('offline'));
  await pending;
  assert.equal(api.editorialHome.generated_for,'2026-09-10');
  assert.equal(fields.homeFeedback.hidden,true);
});

test('U5 failed day request preserves consultation and retry can succeed',async()=>{
  let fail=true, payload;
  const {api,data,fields}=await setup({apiFetch:async()=>{
    if(fail) throw new Error('offline');
    return {ok:true,json:async()=>payload};
  }});
  payload={...data,generated_for:'2026-09-09'};
  api.selectHomeShelfEntry('memory','memory-b');
  await api.loadEditorialFeaturedDate('2026-09-09');
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'memory-b');
  assert.match(fields.homeFeedback.innerHTML,/Reintentar/);
  fail=false;
  await api.loadEditorialFeaturedDate('2026-09-09');
  assert.equal(api.editorialHome.generated_for,'2026-09-09');
  assert.equal(api.getHomePlaybackState().playlistSource,'daily');
  assert.equal(fields.homeFeedback.hidden,true);
});
