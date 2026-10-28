// Paiement PayPal (bouton PayPal + carte bancaire) directement sur la page du livre.
// Les clés ne sont JAMAIS dans le code : PAYPAL_CLIENT_ID et PAYPAL_SECRET sont dans les réglages Vercel.
const crypto = require('crypto');

const BASE = 'https://api-m.paypal.com';
// Prix réellement encaissés (TVA allemande comprise) : les mêmes que ceux affichés sur la page.
// Prix normal 19,99 € ; avec le code MAGNIIZZ (visiteurs TikTok, ou code tapé) : 9,99 €.
const PRIX = { normal: '19.99', promo: '9.99', code: 'MAGNIIZZ' };
const TEST = '0.90';   // TEMPORAIRE : prix de test (achat réel de 1 €), à retirer juste après le test
const PRODUIT = 'gesetzbuch';
const LIEN_JOURS = 30;   // durée de validité du lien de téléchargement

function configure() { return !!(process.env.PAYPAL_CLIENT_ID && process.env.PAYPAL_SECRET); }
function prix(code) { if (TEST) return TEST; return String(code || '').trim().toUpperCase() === PRIX.code ? PRIX.promo : PRIX.normal; }
function prixMin() { return TEST || PRIX.promo; }

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

// Cookie posé chez l'acheteur après le paiement : « ce navigateur a acheté la commande X » (signé, infalsifiable).
const COOKIE = 'gz_achat';
function cookieAchat(commande) {
  const v = commande + '.' + crypto.createHmac('sha256', 'ck:' + process.env.PAYPAL_SECRET).update(commande).digest('hex').slice(0, 24);
  return COOKIE + '=' + encodeURIComponent(v) + '; Path=/; Max-Age=34560000; HttpOnly; Secure; SameSite=Lax';
}
function lireCookieAchat(req) {
  const m = String(req.headers.cookie || '').match(new RegExp('(?:^|; )' + COOKIE + '=([^;]+)'));
  if (!m) return null;
  const v = decodeURIComponent(m[1]); const i = v.lastIndexOf('.'); if (i < 1) return null;
  const commande = v.slice(0, i), s = v.slice(i + 1);
  const attendu = crypto.createHmac('sha256', 'ck:' + process.env.PAYPAL_SECRET).update(commande).digest('hex').slice(0, 24);
  return s.length === attendu.length && crypto.timingSafeEqual(Buffer.from(s), Buffer.from(attendu)) ? commande : null;
}

function lireCorps(req) {
  if (req.body && typeof req.body === 'object') return Promise.resolve(req.body);
  if (typeof req.body === 'string') { try { return Promise.resolve(JSON.parse(req.body)); } catch (e) { return Promise.resolve({}); } }
  return new Promise((ok) => { let d = ''; req.on('data', (c) => { d += c; }); req.on('end', () => { try { ok(JSON.parse(d || '{}')); } catch (e) { ok({}); } }); });
}

module.exports = { configure, prix, prixMin, paypal, lien, lienValide, lireCorps, cookieAchat, lireCookieAchat, PRODUIT };
