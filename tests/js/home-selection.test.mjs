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

test('U5 deliberate VHS selection programs the shelf; autoplay changes only the daily poster',async()=>{
  const {api,fields} = await setup();
  const before = api.getHomePlaybackState();
  api.selectHomeShelfEntry('memory','memory-b');
  let state = api.getHomePlaybackState();
  assert.equal(state.selectionSource,'shelf:memory');
  assert.equal(state.selectedEntryKey,'memory-b');
  assert.equal(state.playlistSource,'shelf:memory');
  assert.equal(state.carouselItemId,before.carouselItemId);
  assert.match(fields.spotlightStage.innerHTML,/<h3 id="spotlight-selected-title">Recuerdo B<\/h3>/);
  assert.match(fields.spotlightStage.innerHTML,/data-entry-key="memory-b"[^>]+tabindex="0" aria-selected="true"/);
  assert.doesNotMatch(fields.spotlightStage.innerHTML,/data-playlist-entry="daily-a"/);
  for(let index=0;index<3;index++) assert.equal(api.tickHomeAutoplay(),true);
  state = api.getHomePlaybackState();
  assert.notEqual(state.carouselItemId,before.carouselItemId);
  assert.equal(state.selectedEntryKey,'memory-b');
  assert.equal(state.selectionSource,'shelf:memory');
  assert.equal(state.playlistSource,'shelf:memory');
  api.returnHomeProgramming();
  api.selectPlaylistEntry('daily-b');
  assert.equal(api.getHomePlaybackState().selectionSource,'daily');
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'daily-b');
  assert.match(fields.spotlightStage.innerHTML,/<h3 id="spotlight-selected-title">Diaria B<\/h3>/);
});

test('source-qualified keys preserve Club provenance and omit personal edit action',async()=>{
  const {api,fields} = await setup();
  api.selectHomeShelfEntry('club','daily-a');
  api.tickHomeAutoplay();
  assert.match(fields.spotlightStage.innerHTML,/>Obra del Club<\/h3>/);
  assert.match(fields.spotlightStage.innerHTML,/data-click="open-home-collection-detail" data-key="daily-a"/);
  assert.doesNotMatch(fields.spotlightStage.innerHTML,/data-click="edit-home-shelf-entry"/);
  assert.match(fields.spotlightStage.innerHTML,/data-playlist-entry="daily-a"[^>]+aria-selected="true"/);
  api.openHomeCollectionDetail('daily-a','shelf:club');
  assert.match(fields.sharedDetailBody.innerHTML,/>Obra del Club<\/h2>/);
  api.returnHomeProgramming();
  api.selectPlaylistEntry('daily-a');
  assert.match(fields.spotlightStage.innerHTML,/>Diaria A<\/h3>/);
  assert.match(fields.spotlightStage.innerHTML,/data-click="edit-home-shelf-entry"/);
});

test('explicit programming and day/poster selection retain their intentional reset semantics',async()=>{
  const {api,data} = await setup();
  api.selectHomeShelfEntry('memory','memory-b');
  api.activateHomeShelf('memory');
  assert.equal(api.getHomePlaybackState().playlistSource,'shelf:memory');
  api.selectPlaylistEntry('memory-a');
  assert.equal(api.getHomePlaybackState().selectionSource,'shelf:memory');
  assert.equal(api.homeShelfSelections.get('memory'),0);
  api.selectSpotlight(1);
  assert.equal(api.getHomePlaybackState().playlistSource,'daily');
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'daily-b');
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
  assert.doesNotMatch(fields.spotlightStage.innerHTML,/No hay obras en esta fuente/);
  api.setEditorialHome({...data,sections:[]});
  api.renderEditorialHero();
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'');
  assert.doesNotMatch(fields.spotlightStage.innerHTML,/data-click="edit-home-shelf-entry"/);
});

test('keyboard handles fallback entry keys and autoplay still respects visibility/reduced motion',async()=>{
  const {api,data,document,window} = await setup();
  delete data.sections[0].items[1].key;
  let prevented = false;
  api.moveHomeShelf({key:'ArrowRight',preventDefault(){prevented=true;},
    target:{closest:()=>({dataset:{sectionId:'memory',entryIndex:'0'}})}});
  assert.equal(prevented,true);
  assert.equal(api.getHomePlaybackState().selectedItemId,'memory-b');
  document.visibilityState='hidden';
  assert.equal(api.tickHomeAutoplay(),false);
  document.visibilityState='visible';
  document.querySelector=()=>({open:true});
  assert.equal(api.tickHomeAutoplay(),false);
  document.querySelector=()=>null;
  window.matchMedia=()=>({matches:true});
  assert.equal(api.tickHomeAutoplay(),false);
});

test('autoplay restores focused console action after rerender without changing the consulted entry',async()=>{
  const {api,fields,document} = await setup();
  api.selectHomeShelfEntry('memory','memory-b');
  const oldAction = {dataset:{click:'edit-home-shelf-entry'}};
  document.activeElement=oldAction;
  let replaced=false;
  let markup=fields.spotlightStage.innerHTML;
  Object.defineProperty(fields.spotlightStage,'innerHTML',{
    get:()=>markup,set:value=>{markup=value;replaced=true;}
  });
  fields.spotlightStage.contains=element=>element===oldAction && !replaced;
  let restored=false;
  fields.spotlightStage.querySelector=selector=>selector==='[data-click="edit-home-shelf-entry"]'
    ? {focus:()=>{restored=true;}} : null;
  assert.equal(api.tickHomeAutoplay(),true);
  assert.equal(restored,true);
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'memory-b');
});

test('the single console carries images, credits, facts and category navigation',async()=>{
  const {api,data,fields} = await setup();
  data.sections[0].action={kind:'catalog',label:'Ver colección'};
  Object.assign(data.sections[0].items[1].item,{
    description:'Una sinopsis de muestra',directors:['Dirección'],writers:['Guion'],
    cast:['Reparto'],duration_minutes:104,backdrop_image:'/panorama.jpg',page_image:'/portada.jpg'
  });
  api.selectHomeShelfEntry('memory','memory-b');
  const html=fields.spotlightStage.innerHTML;
  assert.equal((html.match(/class="spotlight-preview"/g)||[]).length,1);
  for(const text of ['Una sinopsis de muestra','Dirección','Guion','Reparto','104 min','/panorama.jpg','/portada.jpg']) assert.ok(html.includes(text),text);
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
  assert.match(fields.spotlightStage.innerHTML,/Abrí la ficha para completar/);
  assert.match(fields.spotlightStage.innerHTML,/data-image-count="0"/);
  assert.match(fields.spotlightStage.innerHTML,/Sin imágenes de esta obra/);
  assert.equal(api.homeSelectionPreview(null),'');
  const html=await readFile(new URL('../../src/movie_inbox/web/static/index.home.html',import.meta.url),'utf8');
  assert.doesNotMatch(html,/id="homeShelfPreview"/);
  assert.match(html,/id="homeSelectionAnnouncement"[^>]*aria-live="polite"/);
});

test('consulted poster follows source-qualified selection, not independent autoplay',async()=>{
  const {api,fields,data} = await setup();
  data.sections[0].items[1].item.page_image='/memory.jpg';
  api.selectHomeShelfEntry('memory','memory-b');
  let poster = api.homeConsultedPoster(data.sections[0].items[1]);
  assert.match(poster,/data-consulted-source="shelf:memory"/);
  assert.match(poster,/src="\/memory.jpg"/);
  api.tickHomeAutoplay();
  assert.equal(api.homeConsultedPoster(data.sections[0].items[1]),poster);
  api.selectHomeShelfEntry('club','daily-a');
  poster = api.homeConsultedPoster(data.sections[1].items[0]);
  assert.match(poster,/data-click="open-home-collection-detail" data-key="daily-a" data-source="shelf:club"/);
  assert.doesNotMatch(poster,/memory.jpg|data-id=/);
  assert.match(poster,/Obra del Club/);
  assert.match(poster,/Sin portada/);
  assert.equal(api.homeConsultedPoster(null),'');
  assert.equal((fields.spotlightStage.innerHTML.match(/class="spotlight-preview"/g)||[]).length,1);
});

test('console images reserve explicit zero, one and two states using only current item fields',async()=>{
  const {api} = await setup();
  const render = item => api.homeConsultationImages(item,'Muestra');
  assert.match(render({}),/data-image-count="0"/);
  const one=render({page_image:' /poster.jpg '});
  assert.match(one,/data-image-count="1"/);
  assert.match(one,/aria-busy="true"/);
  assert.match(one,/Cargando imagen/);
  assert.match(render({page_image:'/poster.jpg',backdrop_image:'/wide.jpg'}),/data-image-count="2"/);
  assert.match(render({page_image:'/same.jpg',backdrop_image:'/same.jpg'}),/data-image-count="1"/);
  assert.doesNotMatch(render({}),/data-home-preview-image/);
});

test('rerender restores the originating home surface when poster and console share an action',async()=>{
  for (const surface of ['consultation-poster','consultation-view','consultation-images']) {
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

test('image review uses the existing source-qualified detail without promising Club editing',async()=>{
  const {api,fields}=await setup();
  api.selectHomeShelfEntry('memory','memory-b');
  assert.match(fields.spotlightStage.innerHTML,/data-home-focus="consultation-images"/);
  assert.match(fields.spotlightStage.innerHTML,/data-home-focus="consultation-images" data-click="open-detail"/);
  assert.match(fields.spotlightStage.innerHTML,/Panorámica: Editar metadata/);
  api.selectHomeShelfEntry('club','daily-a');
  const html=fields.spotlightStage.innerHTML;
  assert.match(html,/data-home-focus="consultation-images" data-click="open-home-collection-detail" data-key="daily-a" data-source="shelf:club"/);
  assert.match(html,/sólo consulta/);
  assert.doesNotMatch(html,/Panorámica: Editar metadata/);
});

test('U5 source/count/return are honest for 0, 1, 6, 20 and 100 editorial entries',async()=>{
  for (const count of [0,1,6,20,100]) {
    const {api,fields}=await setup();
    const data=sourceFixture(count);
    api.setEditorialHome(data);
    api.renderEditorialHero();
    assert.equal(api.activateHomeShelf('sample'),count>0);
    if (count>0) {
      api.selectHomeShelfEntry('sample',`shared-${count-1}`);
      const html=fields.spotlightStage.innerHTML;
      assert.equal((html.match(/data-playlist-entry=/g)||[]).length,count);
      assert.match(html,new RegExp(`data-playlist-count>${count} ${count===1?'obra':'obras'}<`));
      assert.match(html,/Selección del estante/);
      assert.match(html,new RegExp(`data-long-list="${count > 6}"`));
      assert.match(html,/Volver a programación/);
      assert.equal(api.getHomePlaybackState().selectedEntryKey,`shared-${count-1}`);
    }
    api.returnHomeProgramming();
    assert.match(fields.spotlightStage.innerHTML,/Cartelera de hoy/);
    assert.doesNotMatch(fields.spotlightStage.innerHTML,/data-click="home-programming-return"/);
    api.selectHomeShelfEntry('club','shared-0');
    assert.equal(api.getHomePlaybackState().selectionSource,'shelf:club');
    assert.match(fields.spotlightStage.innerHTML,/>Club 1<\/h3>/);
    assert.doesNotMatch(fields.spotlightStage.innerHTML,/data-click="edit-home-shelf-entry"/);
  }
});

test('U5 return preserves the daily poster and same-day control returns from a shelf',async()=>{
  const {api,fields}=await setup();
  api.tickHomeAutoplay();
  const poster=api.getHomePlaybackState().carouselItemId;
  api.selectHomeShelfEntry('memory','memory-b');
  let focused=false;
  fields.spotlightStage.querySelector=selector=>selector.includes('aria-pressed="true"') ? {focus(){focused=true;}} : null;
  api.returnHomeProgramming(true);
  assert.equal(focused,true);
  assert.equal(api.getHomePlaybackState().carouselItemId,poster);
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'daily-a');
  api.activateHomeShelf('memory');
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'memory-b');
  await api.loadEditorialFeaturedDate('2026-09-10');
  assert.equal(api.getHomePlaybackState().playlistSource,'daily');
  assert.equal(api.getHomePlaybackState().carouselItemId,poster);
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

test('U5 removed source recovers to daily; emptied source retains honest count and return',async()=>{
  const {api,data,fields}=await setup();
  api.selectHomeShelfEntry('memory','memory-b');
  data.sections[0].items=[];
  api.renderEditorialHero();
  assert.equal(api.getHomePlaybackState().playlistSource,'shelf:memory');
  assert.match(fields.spotlightStage.innerHTML,/data-playlist-count>0 obras/);
  assert.match(fields.spotlightStage.innerHTML,/No hay obras en esta fuente/);
  assert.doesNotMatch(fields.spotlightStage.innerHTML,/data-click="edit-home-shelf-entry"/);
  data.sections.splice(0,1);
  api.renderEditorialHero();
  assert.equal(api.getHomePlaybackState().playlistSource,'daily');
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'daily-a');
  assert.match(fields.homeSelectionAnnouncement.textContent,/Volvimos a programación/);
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
  const table={scrollTop:0,getBoundingClientRect:()=>({top:0,bottom:100})};
  const row={getBoundingClientRect:()=>({top:180,bottom:200}),scrollIntoView(){assert.fail('document scroll');}};
  const spine={getBoundingClientRect:()=>({left:150,right:200}),closest:()=>null,scrollIntoView(){assert.fail('document scroll');}};
  fields.spotlightStage.querySelector=selector=>selector==='.spotlight-table-wrap'?table:selector.startsWith('[data-playlist-entry]')?row:null;
  fields.homeSections.getBoundingClientRect=()=>({left:0,right:100});
  fields.homeSections.querySelector=selector=>{
    assert.match(selector,/data-section-id="club"/);
    return spine;
  };
  api.selectHomeShelfEntry('club','daily-a');
  assert.equal(table.scrollTop,100);
  assert.equal(fields.homeSections.scrollLeft,100);
});

test('U5 long-list alignment keeps the focused row below sticky column headings',async()=>{
  const {api,fields}=await setup();
  const table={scrollTop:150,dataset:{playlistSourceId:'shelf:memory'},
    getBoundingClientRect:()=>({top:20,bottom:286}),
    querySelector:()=>({getBoundingClientRect:()=>({height:38})})};
  const row={getBoundingClientRect:()=>({top:30,bottom:68})};
  fields.spotlightStage.querySelector=selector=>selector==='.spotlight-table-wrap'?table:selector.startsWith('[data-playlist-entry]')?row:null;
  api.selectHomeShelfEntry('memory','memory-b');
  assert.equal(table.scrollTop,122);
});

test('U5 autoplay preserves local scrolling but changing source resets it',async()=>{
  const {api,fields}=await setup();
  api.selectHomeShelfEntry('memory','memory-b');
  const oldTable={scrollTop:240,scrollLeft:12,dataset:{playlistSourceId:'shelf:memory'}};
  const nextTable={scrollTop:0,scrollLeft:0};
  let replaced=false,markup=fields.spotlightStage.innerHTML;
  Object.defineProperty(fields.spotlightStage,'innerHTML',{get:()=>markup,set:value=>{markup=value;replaced=true;}});
  fields.spotlightStage.querySelector=selector=>selector==='.spotlight-table-wrap'?(replaced?nextTable:oldTable):null;
  api.tickHomeAutoplay();
  assert.equal(nextTable.scrollTop,240);
  assert.equal(nextTable.scrollLeft,12);
  replaced=false;
  api.selectHomeShelfEntry('club','daily-a');
  assert.equal(nextTable.scrollTop,0);
  assert.equal(nextTable.scrollLeft,0);
});

test('U5 resizing keeps a focused row visible without changing selection or moving focus',async()=>{
  const {api,fields,document}=await setup();
  api.selectHomeShelfEntry('memory','memory-b');
  const table={scrollTop:100,getBoundingClientRect:()=>({top:0,bottom:100})};
  const row={getBoundingClientRect:()=>({top:140,bottom:178}),focus(){assert.fail('resize should not refocus');}};
  fields.spotlightStage.querySelector=selector=>selector==='.spotlight-table-wrap'?table:selector.startsWith('[data-playlist-entry]')?row:null;
  document.activeElement={matches:()=>true};
  api.handleHomeResize();
  assert.equal(table.scrollTop,178);
  assert.equal(api.getHomePlaybackState().selectedEntryKey,'memory-b');
  document.activeElement={matches:()=>false};
  api.handleHomeResize();
  assert.equal(table.scrollTop,178);
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
