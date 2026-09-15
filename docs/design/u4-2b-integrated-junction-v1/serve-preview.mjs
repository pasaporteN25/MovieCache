// Loopback-only, read-only specimen. Explicit public-file map; no directory listing,
// catalog, image proxy, external fetches, or application APIs.
import { createServer } from 'node:http';
import { readFile, readdir } from 'node:fs/promises';
import { resolve, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
const base = fileURLToPath(new URL('.', import.meta.url));
const root = resolve(base, '../../..');
const staticRoot = resolve(root, 'src/movie_inbox/web/static');
const mime = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.png':'image/png','.jpg':'image/jpeg','.woff2':'font/woff2','.svg':'image/svg+xml'};
const files = new Map();
for (const file of ['index.html','junction.css','junction.js','fixture.js','metropolis-poster.jpg']) files.set(file === 'index.html' ? '/' : `/${file}`, resolve(base,file));
for (const file of ['material-components.css','surface-petroleum-v2.png','aperture-bezel-v1.png','category-plaque-blank-v1.png']) files.set(`/kit/${file}`,resolve(base,'../u4-2a-material-kit-v1',file));
files.set('/static/index.home.html',resolve(staticRoot,'index.home.html'));
for (const folder of ['js','css','img','fonts']) {
  const dir = resolve(staticRoot,folder);
  for (const file of await readdir(dir,{recursive:true,withFileTypes:true})) {
    if (!file.isFile() || !mime[extname(file.name)]) continue;
    const path = resolve(file.parentPath,file.name);
    const suffix = path.slice(staticRoot.length).replaceAll('\\','/');
    files.set(`/static${suffix}`,path);
  }
}
const server = createServer(async (req,res) => {
  if (!['GET','HEAD'].includes(req.method)) {res.writeHead(405);res.end();return;}
  const url = new URL(req.url,'http://localhost');
  // Existing cachedImageSrc is kept intact. Only the declared specimen image resolves.
  const path = url.pathname === '/image-cache' && url.searchParams.get('url') === 'demo:metropolis'
    ? resolve(base,'metropolis-poster.jpg') : files.get(url.pathname);
  if (!path) {res.writeHead(404);res.end('Not available in the isolated specimen');return;}
  try {
    const bytes = await readFile(path);
    res.writeHead(200,{'content-type':mime[extname(path)],'cache-control':'no-store',
      'content-security-policy':"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"});
    res.end(req.method === 'HEAD' ? undefined : bytes);
  } catch {res.writeHead(404);res.end('Specimen file missing');}
});
server.listen(0,'127.0.0.1',()=>process.stdout.write(`Preview: http://127.0.0.1:${server.address().port}/\n`));
