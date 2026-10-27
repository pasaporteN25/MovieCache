/* Read-only DOM probe shared by connected-browser QA and unittest geometry checks.
   No application state, screenshot mutation, or pixel-perfect legacy carcass coords. */
() => {
  const box = selector => document.querySelector(selector)?.getBoundingClientRect();
  const style = selector => getComputedStyle(document.querySelector(selector));
  const layout = box('.spotlight-layout');
  const posters = [...document.querySelectorAll('.spotlight-selector')].map(n => n.getBoundingClientRect());
  // IP3: mostrador = buscador (#homeSearchSlot) con su panel de sección + un único póster;
  // la consola inferior ya no existe y los estantes van debajo.
  const search = box('#homeSearchSlot');
  const poster = posters[0];
  const well = box('#homeFurniture');
  const spine = box('.home-shelf-tape');
  const plate = box('.home-shelf-bay-plaque');
  const narrow = innerWidth <= 860;
  const field = box('#homeSearchSlot .hs-input');
  const panel = document.querySelector('#homeSectionPanel');
  const panelBox = panel && !panel.hidden ? panel.getBoundingClientRect() : null;
  return {
    width: innerWidth,
    overflow: document.documentElement.scrollWidth - innerWidth,
    consoleCount: document.querySelectorAll('.spotlight-preview').length,
    retiredConsoleCount: document.querySelectorAll('#homeShelfPreview').length,
    posterCount: posters.length,
    posterWidth: poster?.width,
    posterHeight: poster?.height,
    posterAboveShelves: poster && well ? poster.bottom <= well.top + 1 : null,
    layoutHeight: layout?.height,
    sectionPanelVisible: !!panelBox,
    sectionPanelBelowField: panelBox && field ? panelBox.top >= field.bottom - 1 : null,
    sectionPanelInsideSlot: panelBox && search ? panelBox.left >= search.left - 1 && panelBox.right <= search.right + 1 : null,
    sectionPanelOverlapsPoster: panelBox && poster ? panelBox.left < poster.right && panelBox.right > poster.left && panelBox.top < poster.bottom && panelBox.bottom > poster.top : false,
    searchFieldCount: document.querySelectorAll('#homeSearchSlot input[role="combobox"]').length,
    searchWidth: search?.width,
    searchBesidePoster: !narrow && search && poster ? search.right <= poster.left + 1 : null,
    searchOverlapsPoster: search && poster ? search.left < poster.right && search.right > poster.left && search.top < poster.bottom && search.bottom > poster.top : false,
    retiredCount: document.querySelectorAll('.spotlight-table-wrap, [data-playlist-entry], .spotlight-date-control, [data-click="spotlight-select"]').length,
    spineWidth: spine?.width,
    spineHeight: spine?.height,
    spineTransform: spine ? style('.home-shelf-tape').transform : null,
    contactGap: !narrow && spine && well ? well.top + Number.parseFloat(style('#homeFurniture').getPropertyValue('--home-spine-height')) + 78 - spine.bottom : null,
    plateGap: plate && spine ? spine.top - plate.bottom : null,
    plateHeight: plate?.height,
    focus: document.activeElement?.getAttribute('data-home-focus') || document.activeElement?.className,
  };
}
