// livre.html → Das_Gesetzbuch_des_Geistes.pdf (A5). Une page qui déborde est réduite automatiquement (police un peu plus petite).
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('file://' + path.join(__dirname, 'livre.html')); await p.evaluate(() => document.fonts.ready);
  const fixed = await p.evaluate(() => {
    const out = [];
    document.querySelectorAll('.page').forEach((el, i) => {
      let fs = 11.6;
      while (el.scrollHeight > el.clientHeight + 1 && fs > 8.6) { fs -= 0.2; el.style.fontSize = fs + 'pt'; }
      if (fs < 11.6) out.push([i + 1, fs.toFixed(1), el.scrollHeight > el.clientHeight + 1]);
    });
    return out;
  });
  console.log('pages réduites (n°, taille, déborde encore) :', JSON.stringify(fixed));
  await p.pdf({ path: path.join(__dirname, 'Das_Gesetzbuch_des_Geistes.pdf'), preferCSSPageSize: true, printBackground: true });
  if (process.env.SHOTS) {
    await p.setViewportSize({ width: 560, height: 794 });
    const n = await p.evaluate(() => document.querySelectorAll('.page').length);
    for (const i of process.env.SHOTS.split(',').map(Number)) {
      const el = (await p.$$('.page'))[i - 1]; await el.screenshot({ path: `/tmp/claude-0/-home-user-skillora-/fec401e9-70df-57ee-af23-f64816928711/scratchpad/page_${i}.png` });
    }
  }
  await b.close();
})();
