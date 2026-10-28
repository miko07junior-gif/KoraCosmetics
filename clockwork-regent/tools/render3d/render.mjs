// node render.mjs jobs.json  -- jobs: [{glb, view, out, size, extent, centre, night, bloom, bg}]
// Serves this folder, three.js (THREE_DIR) and the GLBs (GLB_DIR) on localhost and renders in headless Chromium.
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)(process.env.NODE_PATH ? require_path() : 'playwright');
function require_path() { return process.env.NODE_PATH.split(':')[0] + '/playwright'; }
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const THREE_DIR = process.env.THREE_DIR;
const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const types = { '.html': 'text/html', '.js': 'text/javascript', '.glb': 'model/gltf-binary' };
const server = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url.split('?')[0]);
  let f;
  if (u.startsWith('/three/')) f = path.join(THREE_DIR, u.slice(7));
  else if (u.startsWith('/glb/')) f = u.slice(4);
  else f = path.join(here, u);
  fs.readFile(f, (err, data) => {
    if (err) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': types[path.extname(f)] || 'application/octet-stream' });
    res.end(data);
  });
}).listen(0);
const port = server.address().port;
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage();
page.on('pageerror', e => console.error('page error:', e.message));
await page.goto(`http://localhost:${port}/render.html`);
await page.waitForFunction(() => window.ready === true);
for (const j of jobs) {
  const url = await page.evaluate(o => window.renderView(o), { ...j, glb: `/glb${path.resolve(j.glb)}` });
  fs.writeFileSync(j.out, Buffer.from(url.split(',')[1], 'base64'));
  console.log('wrote', j.out);
}
await browser.close();
server.close();
