/* Read-only DOM probe shared by connected-browser QA and unittest geometry checks.
   No application state, screenshot mutation, or pixel-perfect legacy carcass coords. */
() => {
  const box = selector => document.querySelector(selector)?.getBoundingClientRect();
  const style = selector => getComputedStyle(document.querySelector(selector));
  const layout = box('.spotlight-layout');
  const consoleBox = box('.spotlight-preview');
  const posters = [...document.querySelectorAll('.spotlight-selector')].map(n => n.getBoundingClientRect());
  const table = document.querySelector('.spotlight-table-wrap');
  const rows = [...document.querySelectorAll('[data-playlist-entry]')];
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
    posterWidthDifference: posters.length === 2 ? Math.abs(posters[0].width - posters[1].width) : null,
    consoleWidthDifference: layout && consoleBox ? Math.abs(consoleBox.width - layout.width + 48) : null,
    rowCount: rows.length,
    localTableScroll: table ? table.scrollHeight - table.clientHeight : 0,
    rowsOverlapConsole: rows.length && consoleBox ? rows.at(-1).getBoundingClientRect().bottom > consoleBox.top : false,
    spineWidth: spine?.width,
    spineHeight: spine?.height,
    spineTransform: spine ? style('.home-shelf-tape').transform : null,
    contactGap: !narrow && spine && well ? well.top + Number.parseFloat(style('#homeFurniture').getPropertyValue('--home-spine-height')) + 78 - spine.bottom : null,
    plateGap: plate && spine ? spine.top - plate.bottom : null,
    plateHeight: plate?.height,
    imageCount: document.querySelectorAll('.home-console-media img').length,
    imageFit: [...document.querySelectorAll('.home-console-media img')].every(n => getComputedStyle(n).objectFit === 'contain'),
    reviewAction: document.querySelector('[data-home-focus="consultation-images"]')?.textContent,
    focus: document.activeElement?.getAttribute('data-home-focus') || document.activeElement?.className,
  };
}
