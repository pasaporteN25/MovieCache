/* Read-only DOM probe shared by connected-browser QA and unittest geometry checks.
   No application state, screenshot mutation, or pixel-perfect legacy carcass coords. */
() => {
  const box = selector => document.querySelector(selector)?.getBoundingClientRect();
  const style = selector => getComputedStyle(document.querySelector(selector));
  const layout = box('.spotlight-layout');
  const consoleBox = box('.spotlight-preview');
  const posters = [...document.querySelectorAll('.spotlight-selector')].map(n => n.getBoundingClientRect());
  // IP1/IP2: mostrador = buscador (#homeSearchSlot) + un único póster + consola debajo.
  const search = box('#homeSearchSlot');
  const poster = posters[0];
  const well = box('#homeFurniture');
  const spine = box('.home-shelf-tape');
  const plate = box('.home-shelf-bay-plaque');
  const narrow = innerWidth <= 860;
  return {
    width: innerWidth,
    overflow: document.documentElement.scrollWidth - innerWidth,
    consoleCount: document.querySelectorAll('.spotlight-preview').length,
    retiredConsoleCount: document.querySelectorAll('#homeShelfPreview').length,
    posterCount: posters.length,
    consoleWidthDifference: layout && consoleBox ? Math.abs(consoleBox.width - layout.width + 48) : null,
    searchFieldCount: document.querySelectorAll('#homeSearchSlot input[role="combobox"]').length,
    searchWidth: search?.width,
    searchBesidePoster: !narrow && search && poster ? search.right <= poster.left + 1 : null,
    searchOverlapsPoster: search && poster ? search.left < poster.right && search.right > poster.left && search.top < poster.bottom && search.bottom > poster.top : false,
    deskAboveConsole: consoleBox && poster ? consoleBox.top >= poster.bottom - 1 && (!search || consoleBox.top >= search.bottom - 1) : null,
    retiredCount: document.querySelectorAll('.spotlight-table-wrap, [data-playlist-entry], .spotlight-date-control, [data-click="spotlight-select"]').length,
    spineWidth: spine?.width,
    spineHeight: spine?.height,
    spineTransform: spine ? style('.home-shelf-tape').transform : null,
    contactGap: !narrow && spine && well ? well.top + Number.parseFloat(style('#homeFurniture').getPropertyValue('--home-spine-height')) + 78 - spine.bottom : null,
    plateGap: plate && spine ? spine.top - plate.bottom : null,
    plateHeight: plate?.height,
    imageCount: document.querySelectorAll('.spotlight-preview img').length,
    focus: document.activeElement?.getAttribute('data-home-focus') || document.activeElement?.className,
  };
}
