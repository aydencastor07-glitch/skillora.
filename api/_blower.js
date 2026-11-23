// Souffleur (truflame.store) : le client saisit son adresse sur NOTRE site, puis paie sur Whop.
// POST { nom, email, phone, address1, address2, city, state, zip, country, qty }
//   -> enregistre la commande « en attente » (Supabase, blower_orders) et renvoie { url } : la page de paiement Whop.
// Le webhook Whop (api/whop-webhook.js) marque la commande payée et la crée dans Shopify avec l'adresse.
// Facultatif dans Vercel : WHOP_API_KEY -> session de paiement Whop avec notre numéro de commande (liaison exacte).
// Sans clé : lien de paiement Whop + e-mail pré-rempli, la liaison se fait par l'e-mail.
const crypto = require('crypto');
const { lireCorps } = require('./_paypal');
const { requete } = require('./_db');

const ORIGINES = /^https:\/\/([a-z0-9-]+\.myshopify\.com|(www\.)?truflame\.[a-z.]+)$/i;
const PLANS = { 1: 'plan_bRnqMRMjsWz9f' };   // 49 $ ; offres 2 et 3 : à ajouter quand leurs liens Whop existent
if (process.env.WHOP_PLAN_BLOWER_2) PLANS[2] = process.env.WHOP_PLAN_BLOWER_2;
if (process.env.WHOP_PLAN_BLOWER_3) PLANS[3] = process.env.WHOP_PLAN_BLOWER_3;
const RETOUR = 'https://truflame.store/?wh=ok';
const EMAIL = /^[^\s@<>"]{1,64}@[^\s@<>"]{1,180}\.[a-z]{2,24}$/i;
const txt = (v, n) => String(v || '').replace(/[<>]/g, '').trim().slice(0, n);

async function sessionWhop(plan, ref, email) {
  const key = process.env.WHOP_API_KEY; if (!key) return '';
  try {
    const r = await fetch('https://api.whop.com/api/v2/checkout_sessions', {
      method: 'POST', headers: { Authorization: 'Bearer ' + key, 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan_id: plan, redirect_url: RETOUR, metadata: { blower_ref: ref, email } }),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) { console.error('whop session', r.status, JSON.stringify(j).slice(0, 200)); return ''; }
    return j.purchase_url || (j.id ? 'https://whop.com/checkout/' + j.id : '');
  } catch (e) { console.error('whop session', String(e.message || e)); return ''; }
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
  const qty = PLANS[Number(b.qty)] ? Number(b.qty) : 1;
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
  try { await requete('select public.blower_attente($1,$2,$3,$4,$5,$6)', [ref, c.email, c.nom, c.phone, JSON.stringify(adresse), qty]); }
  catch (e) { console.error('blower_attente', String(e.message || e)); return res.status(500).json({ erreur: 'serveur' }); }
  const plan = PLANS[qty];
  const url = (await sessionWhop(plan, ref, c.email)) || ('https://whop.com/checkout/' + plan + '?email=' + encodeURIComponent(c.email));
  console.log('BLOWER attente', ref, qty, c.country, c.email.replace(/^(.).*@/, '$1***@'));
  return res.status(200).json({ ok: true, ref, url });
};
