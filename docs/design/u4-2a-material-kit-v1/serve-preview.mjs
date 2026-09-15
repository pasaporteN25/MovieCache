// Read-only loopback preview. Exposes only this sample's explicit public files.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
const base = fileURLToPath(new URL('.', import.meta.url));
const root = resolve(base, '../../..');
const files = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/material-lab.css', ['material-lab.css', 'text/css; charset=utf-8']],
  ['/material-components.css', ['material-components.css', 'text/css; charset=utf-8']],
  ['/material-lab.js', ['material-lab.js', 'text/javascript; charset=utf-8']],
  ['/surface-petroleum-v1.png', ['surface-petroleum-v1.png', 'image/png']],
  ['/surface-petroleum-v2.png', ['surface-petroleum-v2.png', 'image/png']],
  ['/aperture-bezel-v1.png', ['aperture-bezel-v1.png', 'image/png']],
  ['/category-plaque-blank-v1.png', ['category-plaque-blank-v1.png', 'image/png']],
  ['/reference.png', ['../u4-2-options-v2/owner-reference-inset-library.png', 'image/png']],
]);
for (const font of ['oswald-400-latin.woff2', 'ibm-plex-mono-400-latin.woff2']) {
  files.set(`/fonts/${font}`, [resolve(root, 'src/movie_inbox/web/static/fonts', font), 'font/woff2']);
}
const server = createServer(async (req, res) => {
  if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405); res.end(); return; }
  const route = files.get(new URL(req.url, 'http://localhost').pathname);
  if (!route) { res.writeHead(404); res.end('Not found'); return; }
  try {
    const bytes = await readFile(resolve(base, route[0]));
    res.writeHead(200, { 'content-type': route[1], 'cache-control': 'no-store' });
    res.end(req.method === 'HEAD' ? undefined : bytes);
  } catch { res.writeHead(404); res.end('Asset not available'); }
});
const previewPort = Number(process.argv[2] || 0);
if (!Number.isInteger(previewPort) || previewPort < 0 || previewPort > 65535) throw new Error('Invalid preview port');
server.listen(previewPort, '127.0.0.1', () => process.stdout.write(`Preview: http://127.0.0.1:${server.address().port}/\n`));
