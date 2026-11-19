// Crée la commande PayPal au prix fixé par le serveur (la page ne peut pas choisir le prix).
// produit : 'gesetzbuch' (édition allemande, EUR) ou 'laws' (édition anglaise, USD).
const { configure, prix, paypal, lireCorps, PRODUITS, produit } = require('./_paypal');
const { noterEssai } = require('./_essai');

// Retour après PayPal (mode « redirection », utilisé dans TikTok / Instagram où les fenêtres PayPal ne reviennent pas)
const HOTES = /^(gesetze\.)?skillora\.me$/;

module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ erreur: 'POST' });
  if (!configure()) return res.status(503).json({ erreur: 'PayPal non configuré' });
  try {
    const b = await lireCorps(req);
    const { mode, carte, code } = b; const p = produit(b.produit); const P = PRODUITS[p];
    const hote = HOTES.test(String(req.headers.host || '')) ? req.headers.host : 'gesetze.skillora.me';
    const RETOUR = 'https://' + hote + P.page;
    const unite = { amount: { currency_code: P.devise, value: prix(code, p) }, description: P.desc, custom_id: p, soft_descriptor: 'MAGNIIZZ' };
    const corps = { intent: 'CAPTURE', purchase_units: [unite] };
    if (mode === 'redirect') {
      corps.payment_source = { paypal: { experience_context: {
        brand_name: 'magniizz', locale: P.locale, shipping_preference: 'NO_SHIPPING', user_action: 'PAY_NOW',
        landing_page: carte ? 'GUEST_CHECKOUT' : 'LOGIN',
        return_url: RETOUR + '?pp=ok', cancel_url: RETOUR + '?pp=cancel',
      } } };
    } else {
      corps.application_context = { brand_name: 'magniizz', shipping_preference: 'NO_SHIPPING', user_action: 'PAY_NOW', locale: P.locale };
    }
    const r = await paypal('/v2/checkout/orders', corps);
    if (!r.ok) { console.error('order', r.status, JSON.stringify(r.j).slice(0, 500)); await noterEssai(req, p, 'erreur', '', 'commande ' + r.status, b.moi); return res.status(502).json({ erreur: 'commande' }); }
    await noterEssai(req, p, 'debut', r.j.id, mode === 'redirect' ? (carte ? 'carte (redirection)' : 'paypal (redirection)') : 'boutons', b.moi);
    const approuver = (r.j.links || []).find((l) => l.rel === 'payer-action' || l.rel === 'approve');
    console.log('COMMANDE', r.j.id, p, mode || 'sdk', carte ? 'carte' : 'paypal');
    res.status(200).json({ id: r.j.id, approuver: approuver ? approuver.href : null });
  } catch (e) { console.error(e); res.status(500).json({ erreur: 'serveur' }); }
};
