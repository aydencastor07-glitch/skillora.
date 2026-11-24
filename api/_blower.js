// Souffleur (truflame.store) : le client saisit son adresse sur NOTRE site, puis paie sur Whop.
// POST { action: 'event', type, qty, referrer, utm } -> suivi des visites
// POST { nom, email, phone, address1, address2, city, state, zip, country, qty }
//   -> enregistre la commande « en attente » (Supabase, blower_orders) et renvoie { url } : la page Whop
//      avec e-mail, nom et adresse pré-remplis (paiement intégré dans la boutique seulement si WHOP_EMBED=1).
// Le webhook Whop (api/whop-webhook.js) marque la commande payée et la crée dans Shopify avec l'adresse.
// Facultatif dans Vercel : WHOP_API_KEY -> session de paiement Whop avec notre numéro de commande (liaison exacte).
// Sans clé : lien de paiement Whop + e-mail pré-rempli, la liaison se fait par l'e-mail.
const crypto = require('crypto');
const { lireCorps } = require('./_paypal');
const { requete, empreinte } = require('./_db');

// Suivi des visites de la boutique (tableau /stats/truflame.html) : mêmes fonctions SQL que l'ancienne torche.
const ROBOTS = /bot|crawl|spider|slurp|preview|facebookexternalhit|whatsapp|telegram|discord|headless|lighthouse/i;
function appareil(ua) {
  const u = ua.toLowerCase();
  const device = /ipad|tablet|(android(?!.*mobi))/.test(u) ? 'tablette' : /iphone|ipod|android.*mobi|windows phone/.test(u) ? 'mobile' : 'desktop';
  const os = /iphone|ipad|ipod/.test(u) ? 'iOS' : /android/.test(u) ? 'Android' : /windows/.test(u) ? 'Windows' : /mac os|macintosh/.test(u) ? 'macOS' : null;
  return { device, os };
}
function source(ua, ref, utm) {
  const NOMS = ['TikTok', 'Instagram', 'YouTube', 'Facebook', 'Google', 'Snapchat', 'Pinterest'];
  if (utm) { const k = utm.toLowerCase(); return NOMS.find((n) => k.includes(n.toLowerCase())) || utm.slice(0, 40); }
  const u = ua.toLowerCase();
  if (/musical_ly|bytedance|tiktok/.test(u)) return 'TikTok';
  if (/instagram/.test(u)) return 'Instagram';
  if (/fban|fbav|fb_iab/.test(u)) return 'Facebook';
  if (/snapchat/.test(u)) return 'Snapchat';
  try {
    const h = new URL(ref).hostname.replace(/^www\./, '').replace(/^(l|m|lm)\./, '');
    if (!h || /myshopify\.com$|truflame/.test(h)) return 'direct';
    return NOMS.find((x) => h.includes(x.toLowerCase())) || h.slice(0, 40);
  } catch (e) { return 'direct'; }
}
async function suivre(req, type, qty, b) {   // un suivi perdu ne doit jamais gêner la page
  try {
    const ua = String(req.headers['user-agent'] || '');
    if (ROBOTS.test(ua)) return;
    const pays = String(req.headers['x-vercel-ip-country'] || '').toUpperCase();
    let ville = String(req.headers['x-vercel-ip-city'] || ''); try { ville = decodeURIComponent(ville); } catch (e) {}
    const { device, os } = appareil(ua);
    await requete('select public.torch_event($1,$2,$3,$4,$5,$6,$7,$8)', [type, empreinte(req) || String((b || {}).visitor || ''), qty || null,
      /^[A-Z]{2}$/.test(pays) ? pays : null, ville || null, device, os, type === 'view' ? source(ua, String((b || {}).referrer || ''), String((b || {}).utm || '')) : null]);
  } catch (e) { console.error('torch_event', String(e.message || e)); }
}



const ORIGINES = /^https:\/\/([a-z0-9-]+\.myshopify\.com|(www\.)?truflame\.[a-z.]+)$/i;
const PLANS_SOUFFLEUR = { 1: 'plan_bRnqMRMjsWz9f' };   // souffleur, 49 $
const PLANS_SOS = { 1: 'plan_SW71FLmli4Bij' };          // spray SOS Tower 28, 49 $ (thème « Truflame SOS » : champ caché produit=sos)
const PLANS = PLANS_SOUFFLEUR;
if (process.env.WHOP_PLAN_BLOWER_2) PLANS[2] = process.env.WHOP_PLAN_BLOWER_2;
if (process.env.WHOP_PLAN_BLOWER_3) PLANS[3] = process.env.WHOP_PLAN_BLOWER_3;
const RETOUR = 'https://truflame.store/?wh=ok';
const EMAIL = /^[^\s@<>"]{1,64}@[^\s@<>"]{1,180}\.[a-z]{2,24}$/i;
const txt = (v, n) => String(v || '').replace(/[<>]/g, '').trim().slice(0, n);

async function sessionWhop(plan, ref, email) {
  const key = process.env.WHOP_API_KEY; if (!key) return null;
  try {
    const r = await fetch('https://api.whop.com/api/v2/checkout_sessions', {
      method: 'POST', headers: { Authorization: 'Bearer ' + key, 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan_id: plan, redirect_url: RETOUR, metadata: { blower_ref: ref, email } }),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) { console.error('whop session', r.status, JSON.stringify(j).slice(0, 200)); return null; }
    const url = j.purchase_url || (j.id ? 'https://whop.com/checkout/' + j.id : '');
    return url ? { url, id: String(j.id || '') } : null;
  } catch (e) { console.error('whop session', String(e.message || e)); return null; }
}

module.exports = async (req, res) => {
  const o = String(req.headers.origin || '');
  if (ORIGINES.test(o)) { res.setHeader('Access-Control-Allow-Origin', o); res.setHeader('Vary', 'Origin'); }
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ erreur: 'POST' });
  const b = await lireCorps(req);
  if (b.action === 'event') {   // view (page ouverte), offer (1/2/3 choisi), pay_click (formulaire envoyé)
    if (['view', 'offer', 'pay_click'].includes(b.type) && !b.moi) await suivre(req, b.type, [1, 2, 3].includes(Number(b.qty)) ? Number(b.qty) : null, b);
    return res.status(200).json({ ok: true });
  }
  const P_ = b.produit === 'sos' ? PLANS_SOS : PLANS_SOUFFLEUR;
  const qty = P_[Number(b.qty)] ? Number(b.qty) : 1;
  const c = {
    nom: txt(b.nom, 120), email: txt(b.email, 200).toLowerCase(), phone: txt(b.phone, 40),
    address1: txt(b.address1, 160), address2: txt(b.address2, 120), city: txt(b.city, 80),
    state: txt(b.state, 60), zip: txt(b.zip, 20), country: txt(b.country, 2).toUpperCase() || 'US',
  };
  const manque = ['nom', 'address1', 'city', 'zip'].filter((k) => c[k].length < 2);
  if (!EMAIL.test(c.email)) manque.push('email');
  if (!/^[A-Z]{2}$/.test(c.country)) manque.push('country');
  if (manque.length) return res.status(400).json({ erreur: 'champs', champs: manque });
  const ref = 'bl_' + crypto.randomBytes(6).toString('hex');
  const adresse = { address_line_1: c.address1, address_line_2: c.address2, admin_area_2: c.city, admin_area_1: c.state,
    postal_code: c.zip, country_code: c.country };   // même forme que PayPal (api/_shopify.js)
  const plan = P_[qty];
  // En parallèle (le client attend devant « Opening secure checkout… ») : commande en attente, session Whop, statistiques.
  const [ok, sess] = await Promise.all([
    requete('select public.blower_attente($1,$2,$3,$4,$5,$6)', [ref, c.email, c.nom, c.phone, JSON.stringify(adresse), qty]).then(() => true)
      .catch((e) => { console.error('blower_attente', String(e.message || e)); return false; }),
    sessionWhop(plan, ref, c.email),
    b.moi ? null : suivre(req, 'pay_click', qty, b),
  ]);
  if (!ok) return res.status(500).json({ erreur: 'serveur' });
  // Page Whop avec e-mail, nom et adresse de facturation déjà remplis : le client n'a plus que sa carte à saisir.
  const u = new URL((sess && sess.url) || ('https://whop.com/checkout/' + plan));
  const pre = { email: c.email, name: c.nom, 'address.line1': c.address1, 'address.line2': c.address2, 'address.city': c.city,
    'address.state': c.state, 'address.postal_code': c.zip, 'address.country': c.country };
  for (const [k, v] of Object.entries(pre)) if (v) u.searchParams.set(k, v);
  const url = u.toString();
  console.log('BLOWER attente', ref, qty, c.country, c.email.replace(/^(.).*@/, '$1***@'));
  // Le paiement intégré dans la boutique (plan/session) est refusé par Whop pour ce lien (« checkout no longer available ») :
  // il ne s'active que si WHOP_EMBED=1 dans Vercel. Sinon la boutique envoie le client sur url (page Whop pré-remplie).
  if (process.env.WHOP_EMBED === '1') return res.status(200).json({ ok: true, ref, url, plan, session: (sess && sess.id) || '' });
  return res.status(200).json({ ok: true, ref, url });
};
