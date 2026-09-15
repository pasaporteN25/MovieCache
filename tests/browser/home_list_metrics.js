// Read-only probe: long-list clipping, geometry and keyboard visibility.
() => {
  const table = document.querySelector('.spotlight-table-wrap');
  const box = table?.getBoundingClientRect();
  const rows = [...document.querySelectorAll('[data-playlist-entry]')];
  const selected = document.querySelector('[data-playlist-entry][aria-selected="true"]');
  const selectedBox = selected?.getBoundingClientRect();
  const header = table?.querySelector('th')?.getBoundingClientRect();
  const consoleBox = document.querySelector('.spotlight-preview')?.getBoundingClientRect();
  const posters = [...document.querySelectorAll('.spotlight-selector')].map(n => n.getBoundingClientRect());
  return {
    width: innerWidth, height: innerHeight, pixelRatio: devicePixelRatio,
    overflow: document.documentElement.scrollWidth - innerWidth,
    documentHeight: document.documentElement.scrollHeight, scrollY,
    source: table?.dataset.playlistSourceId,
    count: rows.length, extended: table?.dataset.longList,
    windowHeight: table?.clientHeight, contentHeight: table?.scrollHeight,
    scrollTop: table?.scrollTop,
    selectedKey: selected?.dataset.entryKey,
    selectedVisible: !selectedBox || !!(box && header && selectedBox.top >= header.bottom - 1 && selectedBox.bottom <= box.bottom + 1),
    headerPinned: !header || !!box && Math.abs(header.top - box.top) <= 1,
    windowOverlapsConsole: !!(box && consoleBox && box.bottom > consoleBox.top),
    posterDifference: posters.length === 2 ? Math.abs(posters[0].width - posters[1].width) : null,
    consoleCount: document.querySelectorAll('.spotlight-preview').length,
    focusKey: document.activeElement?.getAttribute('data-entry-key'),
    focusAction: document.activeElement?.getAttribute('data-click'),
  };
}
