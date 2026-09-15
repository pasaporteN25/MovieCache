// Synthetic editorial subsets: large counts exercise the renderer, not API limits.
export function sourceFixture(count) {
  const entry = (index, origin = 'catalog') => ({
    key:`shared-${index}`, origin:{kind:origin},
    item:{id:`shared-${index}`, title:origin === 'catalog' ? `Obra ${index + 1}` : `Club ${index + 1}`, year:'2000'}
  });
  return {generated_for:'2026-09-10',featured:[entry(0)],warnings:[],sections:[
    {id:'sample',title:'Selección editorial con un nombre largo para comprobar el alcance visible',items:Array.from({length:count},(_,index)=>entry(index))},
    {id:'club',title:'Colección del Club',items:[entry(0,'collection')]}
  ]};
}
