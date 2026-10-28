// Crée la commande PayPal au prix fixé par le serveur (la page ne peut pas choisir le prix).
const { configure, prix, paypal, PRODUIT } = require('./_paypal');

module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ erreur: 'POST' });
  if (!configure()) return res.status(503).json({ erreur: 'PayPal non configuré' });
  try {
    const r = await paypal('/v2/checkout/orders', {
      intent: 'CAPTURE',
      purchase_units: [{
        amount: { currency_code: 'EUR', value: prix() },
        description: 'Das Gesetzbuch des Geistes – E-Book (PDF)',
        custom_id: PRODUIT,
      }],
      application_context: { brand_name: 'magniizz', shipping_preference: 'NO_SHIPPING', user_action: 'PAY_NOW', locale: 'de-DE' },
    });
    if (!r.ok) { console.error('order', r.status, JSON.stringify(r.j).slice(0, 500)); return res.status(502).json({ erreur: 'commande' }); }
    res.status(200).json({ id: r.j.id });
  } catch (e) { console.error(e); res.status(500).json({ erreur: 'serveur' }); }
};
