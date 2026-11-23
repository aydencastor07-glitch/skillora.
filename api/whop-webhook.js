// Webhook Whop : après un paiement réussi sur un lien de paiement Whop (ebook), on enregistre la vente
// et on envoie le PDF par e-mail à l'acheteur (api/_mail.js, même e-mail que pour PayPal).
// Réglages Vercel (jamais dans le code) : WHOP_WEBHOOK_SECRET (obligatoire), WHOP_API_KEY (facultatif :
// sert seulement à relire le paiement chez Whop si l'e-mail de l'acheteur n'est pas dans l'événement).
const crypto = require('crypto');
const { lien } = require('./_paypal');
const { requete } = require('./_db');
const { envoyerLivre } = require('./_mail');
const { signatureValide: signatureStripe } = require('./_stripe');

// plan Whop (lien de paiement) -> livre
const PLANS = {
  plan_gyXbE45ZzCVab: { p: 'laws', devise: 'USD', cents: 999 },        // The Laws of the Mind – $9.99
};
if (process.env.WHOP_PLAN_GESETZBUCH) PLANS[process.env.WHOP_PLAN_GESETZBUCH] = { p: 'gesetzbuch', devise: 'EUR', cents: 999 };

const EMAIL = /^[^\s@<>"]{1,64}@[^\s@<>"]{1,180}\.[a-z]{2,24}$/i;

function brut(req) {
  return new Promise((ok) => { let d = ''; req.setEncoding('utf8'); req.on('data', (c) => { d += c; }); req.on('end', () => ok(d)); req.on('error', () => ok(d)); });
}

// Standard Webhooks (webhook-id / webhook-timestamp / webhook-signature « v1,<base64> »).
// La clé est essayée telle quelle et décodée en base64 (selon le format du secret donné par Whop).
function signatureValide(h, corps, secret) {
  try {
    const sig = h['webhook-signature'];
    if (!sig) return signatureStripe(corps, h['x-whop-signature'], secret);   // ancien format « t=…,v1=… »
    const id = h['webhook-id'], ts = h['webhook-timestamp'];
    if (!id || !ts || Math.abs(Date.now() / 1000 - Number(ts)) > 600) return false;
    const brutSecret = secret.replace(/^(whsec_|ws_)/, '');
    const cles = [Buffer.from(secret, 'utf8'), Buffer.from(brutSecret, 'base64')];
    const recues = String(sig).split(' ').map((s) => s.split(',')[1]).filter(Boolean);
    return cles.some((k) => {
      if (!k.length) return false;
      const attendu = crypto.createHmac('sha256', k).update(id + '.' + ts + '.' + corps).digest('base64');
      return recues.some((s) => s.length === attendu.length && crypto.timingSafeEqual(Buffer.from(s), Buffer.from(attendu)));
    });
  } catch (e) { return false; }
}

// cherche dans tout l'objet (le format des événements Whop peut varier selon la version de l'API)
function chercher(o, test, prof = 0) {
  if (!o || typeof o !== 'object' || prof > 6) return null;
  for (const [k, v] of Object.entries(o)) { const r = test(k, v); if (r) return r; }
  for (const v of Object.values(o)) { const r = chercher(v, test, prof + 1); if (r) return r; }
  return null;
}
const emailDe = (o) => chercher(o, (k, v) => (/email/i.test(k) && typeof v === 'string' && EMAIL.test(v.trim()) ? v.trim() : null));
const planDe = (o) => chercher(o, (k, v) => (typeof v === 'string' && PLANS[v] ? v : null));

async function relirePaiement(id) {
  const key = process.env.WHOP_API_KEY; if (!key || !id) return null;
  for (const url of ['https://api.whop.com/api/v1/payments/' + encodeURIComponent(id), 'https://api.whop.com/api/v2/payments/' + encodeURIComponent(id) + '?expand[]=user']) {
    try {
      const r = await fetch(url, { headers: { Authorization: 'Bearer ' + key, Accept: 'application/json' } });
      if (r.ok) return await r.json();
      console.error('whop relire', url.split('/api/')[1].slice(0, 3), r.status);
    } catch (e) { console.error('whop relire', String(e.message || e)); }
  }
  return null;
}

module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).end();
  const secret = process.env.WHOP_WEBHOOK_SECRET;
  if (!secret) return res.status(503).json({ erreur: 'WHOP_WEBHOOK_SECRET manquant' });
  const corps = await brut(req);
  if (!signatureValide(req.headers, corps, secret)) { console.error('whop webhook : signature refusée'); return res.status(400).json({ erreur: 'signature' }); }
  let ev = {}; try { ev = JSON.parse(corps); } catch (e) { return res.status(400).end(); }
  const type = String(ev.type || ev.action || ev.event || '');
  const d = ev.data || {};
  console.log('whop webhook', type, d.id || '', 'champs:', Object.keys(d).join(',').slice(0, 300));
  if (!/payment[._]succeeded/i.test(type)) return res.status(200).json({ recu: true, ignore: type });
  try {
    let plan = planDe(d), email = emailDe(d);
    if (!plan || !email) { const r = await relirePaiement(d.id); if (r) { plan = plan || planDe(r); email = email || emailDe(r); } }
    if (!plan) { console.log('whop : paiement hors ebook', d.id); return res.status(200).json({ recu: true, ignore: 'plan' }); }
    const P = PLANS[plan]; const commande = 'wh' + String(d.id || '').replace(/[^A-Za-z0-9_]/g, '').slice(0, 40);
    if (commande === 'wh') return res.status(400).json({ erreur: 'id' });
    const pays = String(chercher(d, (k, v) => (/country/i.test(k) && typeof v === 'string' && /^[A-Z]{2}$/i.test(v) ? v : null)) || '');
    await requete('select public.ebook_vente($1,$2,$3,$4,$5,$6)', ['pp_' + commande, P.p, P.cents, P.devise, pays, '']);
    console.log('VENTE whop', commande, P.p, email ? email.replace(/^(.).*@/, '$1***@') : 'sans e-mail');
    if (!email) { console.error('whop : e-mail acheteur introuvable', d.id); return res.status(200).json({ recu: true, mail: false }); }
    const c = await requete('select public.ebook_mail_compte($1) as n', ['pp_' + commande]);
    const n = c.rows[0] ? c.rows[0].n : -1;
    if (n < 1 || n > 3) return res.status(200).json({ recu: true, deja: true });   // événement renvoyé : déjà envoyé
    const ok = await envoyerLivre(email, lien(commande, true, P.p), P.p);
    if (ok) await requete('select public.ebook_email($1,$2)', ['pp_' + commande, email]).catch(() => {});
    console.log('MAIL whop', commande, ok ? 'envoyé' : 'échec');
    return res.status(ok ? 200 : 500).json({ recu: true, mail: ok });
  } catch (e) { console.error('whop webhook', String(e.message || e)); return res.status(500).json({ erreur: 'serveur' }); }
};
