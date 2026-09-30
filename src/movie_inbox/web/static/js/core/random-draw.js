// Pure draw rules shared by the header command and the Home random VHS (U8.3).
// No DOM, no module state: callers own the candidates and the previous result.

export function drawRandomItem(candidates, { excludeId = "", random = Math.random } = {}) {
  const pool = Array.isArray(candidates) ? candidates.filter((item) => item?.id) : [];
  if (!pool.length) return null;
  // With more than one candidate, never repeat the result that is on screen.
  const eligible = pool.length > 1 && excludeId
    ? pool.filter((item) => String(item.id) !== String(excludeId))
    : pool;
  const index = Math.min(eligible.length - 1, Math.floor(random() * eligible.length));
  return eligible[index] || null;
}

// "unavailable" describes the work itself; "out-of-scope" means the owner narrowed
// the preference after the draw and this result no longer qualifies for it.
export function randomResultState(item, { available, catalogOnly }) {
  if (!item) return "error";
  if (catalogOnly && !available) return "out-of-scope";
  return available ? "available" : "unavailable";
}
