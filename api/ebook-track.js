// Suivi de la page du livre (vue, clic « Acheter », temps passe), servi par
// Vercel : le pays et la ville viennent des en-tetes de Vercel, l'appareil de
// la signature du navigateur. Aucun email, aucune adresse IP.
const { requete, corps, empreinte } = require('./_db');  // visiteur = empreinte IP + appareil (IP jamais stockée)

const ROBOTS = /bot|crawl|spider|slurp|preview|facebookexternalhit|whatsapp|telegram|discord|headless|lighthouse/i;

function appareil(ua) {
  const u = (ua || '').toLowerCase();
  const tablette = /ipad|tablet|playbook|silk|(android(?!.*mobi))/.test(u);
  const mobile = /iphone|ipod|android.*mobi|windows phone|blackberry|opera mini/.test(u);
  return {
    device: tablette ? 'tablette' : mobile ? 'mobile' : 'desktop',
    os: /iphone|ipad|ipod|ios/.test(u) ? 'iOS' : /android/.test(u) ? 'Android' : /windows/.test(u) ? 'Windows'
      : /mac os|macintosh/.test(u) ? 'macOS' : /linux/.test(u) ? 'Linux' : null,
    browser: /edg\//.test(u) ? 'Edge' : /opr\/|opera/.test(u) ? 'Opera' : /chrome|crios/.test(u) ? 'Chrome'
      : /firefox|fxios/.test(u) ? 'Firefox' : /safari/.test(u) ? 'Safari' : null,
  };
}

/* Les navigateurs integres de TikTok / Instagram n'envoient souvent aucun
   referent : leur signature les trahit quand meme. */
function source(ua, ref, utm) {
  const NOMS = ['TikTok', 'Instagram', 'YouTube', 'Facebook', 'Google', 'Snapchat'];
  if (utm) { const k = utm.toLowerCase(); return NOMS.find((n) => k.includes(n.toLowerCase())) || utm.slice(0, 40); }
  const u = ua.toLowerCase();
  if (/musical_ly|bytedance|tiktok/.test(u)) return 'TikTok';
  if (/instagram/.test(u)) return 'Instagram';
  if (/fban|fbav|fb_iab/.test(u)) return 'Facebook';
  if (/snapchat/.test(u)) return 'Snapchat';
  try {
    const h = new URL(ref).hostname.replace(/^www\./, '').replace(/^(l|m|lm)\./, '');
    if (!h || h.endsWith('skillora.me')) return 'direct';
    const n = NOMS.find((x) => h.includes(x.toLowerCase())) || (h === 'youtu.be' ? 'YouTube' : null);
    return n || h.slice(0, 40);
  } catch { return 'direct'; }
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') return res.status(405).end();
  try {
    const b = await corps(req);
    const ua = String(req.headers['user-agent'] || '');
    if (ROBOTS.test(ua)) return res.status(200).json({ success: true, bot: true });
    const { device, os, browser } = appareil(ua);
    const pays = String(req.headers['x-vercel-ip-country'] || '').toUpperCase();
    let ville = String(req.headers['x-vercel-ip-city'] || '');
    try { ville = decodeURIComponent(ville); } catch {}
    const ref = String(b.referrer || '');
    await requete('select public.ebook_enregistrer($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)', [
      String(b.type || ''), String(b.product || ''), String(b.session || ''), empreinte(req) || String(b.visitor || ''),
      /^[A-Z]{2}$/.test(pays) ? pays : null, ville || null, device, os, browser, ref || null,
      b.type === 'view' ? source(ua, ref, String(b.utm || '')) : null, String(b.lang || '') || null,
      b.type === 'leave' ? Math.round(Number(b.seconds) || 0) : null,
    ]);
    return res.status(200).json({ success: true });
  } catch (e) {
    console.log('ebook-track:', String(e.message || e));
    return res.status(200).json({ success: false });   // un suivi perdu ne doit jamais gener la page
  }
};
