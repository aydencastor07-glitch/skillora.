// Paiement par carte Truflame avec Stripe Checkout (page de paiement Stripe : carte, Apple Pay, Google Pay).
// Clé : STRIPE_SECRET_KEY (compte Stripe du partenaire). Webhook facultatif : STRIPE_WEBHOOK_SECRET.
const crypto = require('crypto');

const actif = () => /^(sk|rk)_(live|test)_/.test(String(process.env.STRIPE_SECRET_KEY || ''));

// Tous les pays acceptés par Stripe pour l'adresse de livraison (on accepte le monde entier).
const PAYS = ('AC AD AE AF AG AI AL AM AO AQ AR AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CD CF CG CH CI CK CL CM CN CO CR CV CW CY CZ '
  + 'DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HN HR HT HU ID IE IL IM IN IO IQ IS IT JE JM JO JP '
  + 'KE KG KH KI KM KN KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MK ML MM MN MO MQ MR MS MT MU MV MW MX MY MZ NA NC NE NG NI NL NO NP NR NU NZ OM '
  + 'PA PE PF PG PH PK PL PM PN PR PS PT PY QA RE RO RS RU RW SA SB SC SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SZ TA TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ '
  + 'UA UG US UY UZ VA VC VE VG VN VU WF WS XK YE YT ZA ZM ZW').split(' ');
// Liste de secours si Stripe refuse un code de la grande liste.
const PAYS_SURS = 'US CA GB IE AU NZ FR DE BE NL LU CH AT ES PT IT DK SE NO FI PL CZ IS MX BR AR CL CO PE PR JM DO HT TT PH IN SG MY TH JP KR HK TW AE SA IL ZA NG KE GH'.split(' ');

function aplatir(o, prefixe, out) {   // { a: { b: [1] } } -> a[b][0]=1 (format des formulaires Stripe)
  out = out || new URLSearchParams();
  Object.keys(o).forEach((k) => {
    const v = o[k]; const cle = prefixe ? prefixe + '[' + k + ']' : k;
    if (v === undefined || v === null) return;
    if (typeof v === 'object') aplatir(v, cle, out); else out.append(cle, String(v));
  });
  return out;
}

async function stripe(chemin, params, methode) {
  const r = await fetch('https://api.stripe.com/v1' + chemin, {
    method: methode || (params ? 'POST' : 'GET'),
    headers: { Authorization: 'Bearer ' + process.env.STRIPE_SECRET_KEY, 'Content-Type': 'application/x-www-form-urlencoded' },
    body: params ? aplatir(params).toString() : undefined,
  });
  const j = await r.json().catch(() => ({}));
  return { ok: r.ok, status: r.status, j };
}

// Crée la session de paiement. montant en dollars ('59.48'), qty, test.
async function creerSession({ montant, qty, nom, test, base }) {
  const params = (pays) => ({
    mode: 'payment',
    line_items: [{ quantity: 1, price_data: { currency: 'usd', unit_amount: Math.round(Number(montant) * 100),
      product_data: { name: qty > 1 ? nom + ' × ' + qty : nom, description: test ? 'TEST $1 – will be refunded' : 'Free shipping · 30-day guarantee' } } }],
    shipping_address_collection: { allowed_countries: pays },
    shipping_options: [{ shipping_rate_data: { type: 'fixed_amount', display_name: 'Free shipping', fixed_amount: { amount: 0, currency: 'usd' } } }],
    phone_number_collection: { enabled: false },
    metadata: { boutique: 'truflame', qty: String(qty), test: test ? '1' : '0' },
    payment_intent_data: { statement_descriptor_suffix: 'TRUFLAME', metadata: { boutique: 'truflame', qty: String(qty) } },
    success_url: base + '?sc=ok&sid={CHECKOUT_SESSION_ID}',
    cancel_url: base + '?sc=cancel',
    locale: 'en',
  });
  let pays = PAYS, suffixe = true;
  const demande = () => { const o = params(pays); if (!suffixe) delete o.payment_intent_data.statement_descriptor_suffix; return stripe('/checkout/sessions', o); };
  let r = await demande();
  for (let essai = 0; essai < 2 && !r.ok; essai++) {   // options refusées par ce compte : on les retire et on réessaie
    const err = JSON.stringify(r.j);
    if (/allowed_countries/.test(err) && pays !== PAYS_SURS) pays = PAYS_SURS;
    else if (/statement_descriptor/.test(err) && suffixe) suffixe = false;
    else break;
    console.error('stripe réessai', err.slice(0, 300));
    r = await demande();
  }
  if (!r.ok) { const e = r.j.error || {}; throw new Error('stripe ' + r.status + ' ' + (e.code || '') + ' ' + (e.param || '') + ' ' + (e.message || '').slice(0, 160)); }
  return r.j;   // { id, url }
}

const lireSession = (id) => stripe('/checkout/sessions/' + encodeURIComponent(id));

// Vérifie la signature d'un webhook Stripe (en-tête Stripe-Signature : t=…,v1=…).
function signatureValide(brut, entete, secret) {
  try {
    const parts = {}; String(entete || '').split(',').forEach((p) => { const i = p.indexOf('='); if (i > 0) (parts[p.slice(0, i)] = parts[p.slice(0, i)] || []).push(p.slice(i + 1)); });
    const t = (parts.t || [])[0]; if (!t || Math.abs(Date.now() / 1000 - Number(t)) > 600) return false;
    const attendu = crypto.createHmac('sha256', secret).update(t + '.' + brut).digest('hex');
    return (parts.v1 || []).some((s) => s.length === attendu.length && crypto.timingSafeEqual(Buffer.from(s), Buffer.from(attendu)));
  } catch (e) { return false; }
}

module.exports = { actif, creerSession, lireSession, signatureValide, stripe };

// ── Après le paiement : vérifie la session, enregistre la commande (une seule fois), la copie dans Shopify ──
const PRIX = { 1: '34.99', 2: '59.48', 3: '83.97' };   // les mêmes que dans api/torch.js et sur la page

async function finaliser(s) {
  const { requete } = require('./_db');
  const { creerCommande } = require('./_shopify');
  const md = s.metadata || {};
  const test = md.test === '1';
  const qty = Number(md.qty) || 0;
  const attendu = test ? 100 : Math.round(Number(PRIX[qty] || 0) * 100);
  const ok = md.boutique === 'truflame' && !!PRIX[qty] && attendu > 0 && s.payment_status === 'paid'
    && s.currency === 'usd' && Number(s.amount_total) >= attendu - 1;
  if (!ok) return { ok: false, statut: s.payment_status || s.status };
  const liv = s.shipping_details || (s.collected_information || {}).shipping_details || {};
  const a = liv.address || {};
  const adresse = { address_line_1: a.line1 || '', address_line_2: a.line2 || '', admin_area_2: a.city || '', admin_area_1: a.state || '',
    postal_code: a.postal_code || '', country_code: a.country || '' };   // même forme que PayPal pour le tableau
  const cd = s.customer_details || {};
  const nom = liv.name || cd.name || '';
  const email = cd.email || '';
  const pi = typeof s.payment_intent === 'string' ? s.payment_intent : (s.payment_intent || {}).id;
  const id = (test ? 'TEST-' : '') + 'stripe_' + (pi || s.id);
  const montant = (Number(s.amount_total) / 100).toFixed(2);
  let nouvelle = false;
  try { nouvelle = (await requete('select public.torch_commande_nouvelle($1,$2,$3,$4,$5,$6) as n', [id, qty, Number(s.amount_total), email, nom, JSON.stringify(adresse)])).rows[0].n; }
  catch (e) { console.error('torch_commande_nouvelle', String(e.message || e)); }
  if (nouvelle) {
    console.log('TORCH VENTE STRIPE', id, qty, montant, nom, JSON.stringify(adresse));
    try { const cmd = await creerCommande({ orderID: id, captureID: pi, qty, montant, email, nom, adresse, test, passerelle: 'Stripe' }); if (cmd) console.log('TORCH SHOPIFY', id, cmd.name); }
    catch (e) { console.error('torch shopify', String(e.message || e)); }
  }
  return { ok: true, commande: id, nom, email, nouvelle, test, qty };
}

module.exports.finaliser = finaliser;
module.exports.PRIX = PRIX;
