// Paiement PayPal (bouton PayPal + carte bancaire) directement sur la page du livre.
// Les clés ne sont JAMAIS dans le code : PAYPAL_CLIENT_ID et PAYPAL_SECRET sont dans les réglages Vercel.
const crypto = require('crypto');

const BASE = 'https://api-m.paypal.com';
// Prix réellement encaissés (TVA allemande comprise) : les mêmes que ceux affichés sur la page.
const PRIX = { normal: '23.79', promo: '11.89', promoActive: true };
const TEST = '1.00';   // TEMPORAIRE : prix de test (achat réel de 1 €), à retirer juste après le test
const PRODUIT = 'gesetzbuch';
const LIEN_JOURS = 30;   // durée de validité du lien de téléchargement

function configure() { return !!(process.env.PAYPAL_CLIENT_ID && process.env.PAYPAL_SECRET); }
function prix() { if (TEST) return TEST; return PRIX.promoActive ? PRIX.promo : PRIX.normal; }

async function jeton() {
  const r = await fetch(BASE + '/v1/oauth2/token', {
    method: 'POST',
    headers: {
      Authorization: 'Basic ' + Buffer.from(process.env.PAYPAL_CLIENT_ID + ':' + process.env.PAYPAL_SECRET).toString('base64'),
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: 'grant_type=client_credentials',
  });
  const j = await r.json();
  if (!r.ok) throw new Error('PayPal oauth ' + r.status);
  return j.access_token;
}

async function paypal(chemin, corps) {
  const r = await fetch(BASE + chemin, {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + (await jeton()), 'Content-Type': 'application/json' },
    body: JSON.stringify(corps || {}),
  });
  const j = await r.json().catch(() => ({}));
  return { ok: r.ok, status: r.status, j };
}

// Lien de téléchargement signé : seul le serveur (qui connaît le secret) peut en fabriquer un.
function signer(commande, expire) {
  return crypto.createHmac('sha256', 'dl:' + process.env.PAYPAL_SECRET).update(commande + '.' + expire).digest('hex').slice(0, 32);
}
function lien(commande) {
  const e = Math.floor(Date.now() / 1000) + LIEN_JOURS * 86400;
  return '/api/download?o=' + encodeURIComponent(commande) + '&e=' + e + '&s=' + signer(commande, e);
}
function lienValide(commande, e, s) {
  if (!commande || !e || !s || Number(e) < Date.now() / 1000) return false;
  const attendu = signer(commande, e);
  return s.length === attendu.length && crypto.timingSafeEqual(Buffer.from(s), Buffer.from(attendu));
}

function lireCorps(req) {
  if (req.body && typeof req.body === 'object') return Promise.resolve(req.body);
  if (typeof req.body === 'string') { try { return Promise.resolve(JSON.parse(req.body)); } catch (e) { return Promise.resolve({}); } }
  return new Promise((ok) => { let d = ''; req.on('data', (c) => { d += c; }); req.on('end', () => { try { ok(JSON.parse(d || '{}')); } catch (e) { ok({}); } }); });
}

module.exports = { configure, prix, paypal, lien, lienValide, lireCorps, PRODUIT };
