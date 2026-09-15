// Demonstration only. No personal catalog read or synthesized factual credits.
export function buildFixture(mode, date) {
  const names = ['Metropolis', 'El faro de niebla', 'Las calles recuerdan', 'Ecos del invierno', 'Bajo la superficie', 'Tren fuera de hora', 'La última función', 'Órbitas de papel', 'La habitación 27', 'Verano en pausa', 'Crónicas del puerto', 'Luces de neón', 'La noche perdida', 'Sombras en la costa', 'Cinta de recuerdos', 'Punto ciego', 'El archivo de las cosas que dejamos para después', 'Más allá del último fotograma'];
  const entries = names.map((title, index) => ({
    key: `demo-${index}`, origin: {kind: 'catalog'}, reason: {label: 'Muestra visual'},
    item: {id: `demo-${index}`, title, year: index === 0 ? '1927' : index === 16 ? '' : String(2010 + index), kind: 'película', status: index > 5 && index < 12 ? 'watched' : 'pending', en_catalogo: index < 6,
      page_image: index === 0 && mode !== 'missing' ? 'demo:metropolis' : '',
      description: index === 0 ? '' : 'Ficha sintética para comprobar la lectura y la integración del display.'}
  }));
  const sections = [
    {id:'available', title:'Disponible esta noche', items:entries.slice(0,6)},
    {id:'memory', title:'Tu archivo pide memoria', items:entries.slice(6,12)},
    {id:'route', title:'Una ruta por cine', items:entries.slice(12,18)}
  ].map(section => ({...section, action:{kind:'catalog',label:'Ver colección',filters:{}}}));
  if (mode === 'sparse') {
    sections.splice(0, sections.length, {...sections[2],title:'Una ruta por historias que esperan una segunda mirada',items:[entries[16],entries[17]]});
  }
  return {generated_for:date, featured:mode === 'empty' ? [] : entries.slice(0,6), sections:mode === 'empty' ? [] : sections, warnings:[], limits:{featured_items:6}};
}
