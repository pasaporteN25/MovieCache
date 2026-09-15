import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';

const source=await readFile(new URL('../../src/movie_inbox/web/static/js/core/card.js',import.meta.url),'utf8');
async function setup() {
  const context=vm.createContext({});
  const module=new vm.SourceTextModule(source,{context});
  await module.link(specifier=>{
    const declaration=[...source.matchAll(/import\s*\{([^}]+)\}\s*from\s*"([^"]+)"/g)].find(match=>match[2]===specifier);
    const names=declaration[1].split(',').map(value=>value.trim());
    return new vm.SyntheticModule(names,function(){for(const name of names)this.setExport(name,()=>{});},{context});
  });
  await module.evaluate();
  const fallback={hidden:false,matches:()=>true};
  const label={textContent:'Cargando imagen…'};
  const frame={dataset:{homeImageState:'loading'},setAttribute(name,value){this[name]=value;},querySelector:()=>label};
  const classes=new Set();
  const image={hidden:false,nextElementSibling:fallback,
    classList:{add:value=>classes.add(value),remove:value=>classes.delete(value)},
    matches:selector=>selector==='[data-home-preview-image]',
    closest:selector=>selector==='[data-spotlight-image]'?null:selector==='[data-home-image-state]'?frame:image};
  return {api:module.namespace,image,frame,label,fallback,classes};
}
test('console image load clears busy and hides its own fallback',async()=>{
  const {api,image,frame,fallback,classes}=await setup();
  api.handlePosterLoad({target:image});
  assert.equal(frame.dataset.homeImageState,'loaded');
  assert.equal(frame['aria-busy'],'false');
  assert.equal(fallback.hidden,true);
  assert.equal(classes.has('is-loaded'),true);
});
test('console image error remains local and clears loading state',async()=>{
  const first=await setup(),current=await setup();
  first.api.handlePosterError({target:first.image});
  assert.equal(first.frame.dataset.homeImageState,'error');
  assert.equal(first.frame['aria-busy'],'false');
  assert.equal(first.image.hidden,true);
  assert.equal(first.fallback.hidden,false);
  assert.equal(first.label.textContent,'No se pudo cargar la imagen');
  assert.equal(current.frame.dataset.homeImageState,'loading');
});
