// Read-only probe: geometría del mostrador de Inicio (buscador + póster único; sin consola inferior desde IP3).
// Sustituye al antiguo probe de la tabla de programación, que ya no existe (IP1).
() => {
  const box = selector => document.querySelector(selector)?.getBoundingClientRect();
  const search = box('#homeSearchSlot');
  const poster = box('.spotlight-selector');
  const well = box('#homeFurniture');
  const panel = document.querySelector('#homeSectionPanel');
  const layout = box('.spotlight-layout');
  const active = document.activeElement;
  return {
    width: innerWidth, height: innerHeight, pixelRatio: devicePixelRatio,
    overflow: document.documentElement.scrollWidth - innerWidth,
    documentHeight: document.documentElement.scrollHeight, scrollY,
    posterCount: document.querySelectorAll('.spotlight-selector').length,
    consoleCount: document.querySelectorAll('.spotlight-preview').length,
    searchFieldCount: document.querySelectorAll('#homeSearchSlot input[role="combobox"]').length,
    searchExpanded: document.querySelector('#homeSearchSlot input[role="combobox"]')?.getAttribute('aria-expanded'),
    panelOpen: document.querySelector('#homeSearchSlot .hs-panel:not([hidden])') !== null,
    deskInsideLayout: !!(layout && search && poster && search.left >= layout.left - 1 && poster.right <= layout.right + 1),
    searchOverlapsPoster: !!(search && poster && search.left < poster.right && search.right > poster.left && search.top < poster.bottom && search.bottom > poster.top),
    deskOverlapsShelves: !!(well && poster && poster.bottom > well.top + 1),
    sectionPanelHidden: panel ? panel.hidden : null,
    sectionPanelSource: panel?.dataset.source || '',
    posterHeading: document.querySelector('.spotlight-selector-heading span')?.textContent.trim(),
    consultedKey: document.querySelector('.spotlight-selector')?.dataset.consultedKey,
    focusAction: active?.getAttribute('data-click'),
    focusSurface: active?.getAttribute('data-home-focus'),
    focusId: active?.id,
  };
}
