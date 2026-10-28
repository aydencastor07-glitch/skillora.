// Crée la commande PayPal au prix fixé par le serveur (la page ne peut pas choisir le prix).
const { configure, prix, paypal, lireCorps, PRODUIT } = require('./_paypal');

// Retour après PayPal (mode « redirection », utilisé dans TikTok / Instagram où les fenêtres PayPal ne reviennent pas)
const RETOUR = 'https://gesetze.skillora.me/gesetze/';

module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ erreur: 'POST' });
  if (!configure()) return res.status(503).json({ erreur: 'PayPal non configuré' });
  try {
    const { mode, carte, code } = await lireCorps(req);
    const unite = { amount: { currency_code: 'EUR', value: prix(code) }, description: 'Das Gesetzbuch des Geistes – E-Book (PDF)', custom_id: PRODUIT };
    const corps = { intent: 'CAPTURE', purchase_units: [unite] };
    if (mode === 'redirect') {
      corps.payment_source = { paypal: { experience_context: {
        brand_name: 'magniizz', locale: 'de-DE', shipping_preference: 'NO_SHIPPING', user_action: 'PAY_NOW',
        landing_page: carte ? 'GUEST_CHECKOUT' : 'LOGIN',
        return_url: RETOUR + '?pp=ok', cancel_url: RETOUR + '?pp=cancel',
      } } };
    } else {
      corps.application_context = { brand_name: 'magniizz', shipping_preference: 'NO_SHIPPING', user_action: 'PAY_NOW', locale: 'de-DE' };
    }
    const r = await paypal('/v2/checkout/orders', corps);
    if (!r.ok) { console.error('order', r.status, JSON.stringify(r.j).slice(0, 500)); return res.status(502).json({ erreur: 'commande' }); }
    const approuver = (r.j.links || []).find((l) => l.rel === 'payer-action' || l.rel === 'approve');
    console.log('COMMANDE', r.j.id, mode || 'sdk', carte ? 'carte' : 'paypal');
    res.status(200).json({ id: r.j.id, approuver: approuver ? approuver.href : null });
  } catch (e) { console.error(e); res.status(500).json({ erreur: 'serveur' }); }
};
