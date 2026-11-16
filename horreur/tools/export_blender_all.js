// Export de la scène three.js (jeu2/dino.html?blocky) vers Blender : décor sans statue, statue.json, personnages en blocs, objets, animation complète.
const { chromium } = require('playwright'); const fs = require('fs');
(async () => { const [,, out, n0, n1] = process.argv;
 const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
 const p = await b.newPage({ viewport: { width: 270, height: 480 } }); p.on('pageerror', e => console.log('ERR', e.message));
 await p.goto('http://localhost:8765/jeu2/dino.html?manual&blocky'); await p.waitForFunction(() => window.READY, null, { timeout: 180000 });
 const W = (f, b64) => fs.writeFileSync(`${out}/${f}`, Buffer.from(b64, 'base64'));
 W('scene.glb', await p.evaluate(() => window.exportScene(true)));
 fs.writeFileSync(`${out}/statue.json`, JSON.stringify(await p.evaluate(() => window.statueSpec())));
 fs.writeFileSync(`${out}/lamps.json`, JSON.stringify(await p.evaluate(() => window.LAMPS_POS())));
 W('phone.glb', await p.evaluate(() => window.exportPhone()));
 const ex = await p.evaluate(() => window.exportExtras()); for (const k in ex) W(`${k}.glb`, ex[k]);
 const chars = await p.evaluate(() => window.CHARS());
 for (const c of chars) { W(`char_${c}.glb`, await p.evaluate(c => window.exportChar(c), c));
   for (const k of ['neutral', 'smile', 'shock', 'strain', 'disgust', 'dead']) { const d = await p.evaluate(([c, k]) => window.charFace(c, k), [c, k]); W(`face_${c}_${k}.png`, d.split(',')[1]); } }
 fs.writeFileSync(`${out}/chars.json`, JSON.stringify(chars));
 const A = []; for (let a = +n0; a < +n1; a += 100) A.push(...await p.evaluate(([a, z]) => window.bakeAll(a, z), [a, Math.min(+n1, a + 100)]));
 fs.writeFileSync(`${out}/anim.json`, JSON.stringify(A)); console.log('ok', A.length); await b.close(); })();
