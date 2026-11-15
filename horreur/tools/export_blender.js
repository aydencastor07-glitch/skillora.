const { chromium } = require('playwright'); const fs = require('fs');
(async () => { const [,, out, n0, n1, qs] = process.argv;
 const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
 const p = await b.newPage({ viewport: { width: 270, height: 480 } }); p.on('pageerror', e => console.log('ERR', e.message));
 await p.goto('http://localhost:8765/jeu2/dino.html?manual' + (qs || '')); await p.waitForFunction(() => window.READY, null, { timeout: 180000 });
 fs.writeFileSync(out + '/scene.glb', Buffer.from(await p.evaluate(() => window.exportScene()), 'base64'));
 fs.writeFileSync(out + '/blocky.glb', Buffer.from(await p.evaluate(() => window.exportBlocky()), 'base64'));
 fs.writeFileSync(out + '/phone.glb', Buffer.from(await p.evaluate(() => window.exportPhone()), 'base64'));
 for (const k of ['neutral', 'smile', 'shock', 'strain']) { const d = await p.evaluate(k => window.__BKface(k), k); fs.writeFileSync(`${out}/face_${k}.png`, Buffer.from(d.split(',')[1], 'base64')); }
 const anim = await p.evaluate(([a, z]) => window.bake(+a, +z), [n0, n1]); fs.writeFileSync(out + '/anim.json', JSON.stringify(anim));
 console.log('ok', anim.length); await b.close(); })();
