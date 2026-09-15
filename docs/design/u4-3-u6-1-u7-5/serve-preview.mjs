// Read-only loopback design server with a fixed public-file map. No app API,
// catalog reads, external image proxy, credentials, directory listing or writes.
import { createServer } from 'node:http';
import { readFile, readdir } from 'node:fs/promises';
import { resolve, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
const base = fileURLToPath(new URL('.', import.meta.url));
const staticRoot = resolve(base,'../../../src/movie_inbox/web/static');
const mime = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.png':'image/png','.jpg':'image/jpeg','.woff2':'font/woff2','.svg':'image/svg+xml'};
const files = new Map([
  ['/',resolve(base,'index.html')],['/study.css',resolve(base,'study.css')],['/study.js',resolve(base,'study.js')],
  ['/legacy.js',resolve(base,'../u4-2d-1-composition/composition.js')],
  ['/lab-controls.css',resolve(base,'../u4-2d-1-composition/composition.css')],
  ['/fixture.js',resolve(base,'../u4-2b-integrated-junction-v1/fixture.js')],
  ['/poster.jpg',resolve(base,'../u4-2b-integrated-junction-v1/metropolis-poster.jpg')]
]);
for (const name of ['style.css','index.shell-open.html','index.home.html']) files.set(`/static/${name}`,resolve(staticRoot,name));
for (const folder of ['js','css','img','fonts']) {
  for (const file of await readdir(resolve(staticRoot,folder),{recursive:true,withFileTypes:true})) {
    if (!file.isFile() || !mime[extname(file.name)]) continue;
    const path = resolve(file.parentPath,file.name);
    files.set(`/static${path.slice(staticRoot.length).replaceAll('\\','/')}`,path);
  }
}
const server = createServer(async(req,res) => {
  if (!['GET','HEAD'].includes(req.method)) { res.writeHead(405); res.end(); return; }
  const url = new URL(req.url,'http://localhost');
  const path = url.pathname === '/image-cache' && url.searchParams.get('url') === 'demo:metropolis' ? files.get('/poster.jpg') : files.get(url.pathname);
  if (!path) {res.writeHead(404);res.end('Outside the isolated design study');return;}
  try {
    const content = await readFile(path);
    res.writeHead(200,{'content-type':mime[extname(path)],'cache-control':'no-store','content-security-policy':"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"});
    res.end(req.method === 'HEAD' ? undefined : content);
  } catch {res.writeHead(404);res.end('Missing study asset');}
});
server.listen(0,'127.0.0.1',()=>process.stdout.write(`Design study: http://127.0.0.1:${server.address().port}/\n`));
