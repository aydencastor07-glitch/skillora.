// Webhook Stripe (filet de sécurité) : si le client ferme la page avant de revenir sur la boutique,
// la commande est quand même enregistrée et copiée dans Shopify. Événement : checkout.session.completed.
const { signatureValide, finaliser, lireSession } = require('./_stripe');

function brut(req) {
  return new Promise((ok) => { let d = ''; req.setEncoding('utf8'); req.on('data', (c) => { d += c; }); req.on('end', () => ok(d)); req.on('error', () => ok(d)); });
}

module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).end();
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!secret) return res.status(503).json({ erreur: 'STRIPE_WEBHOOK_SECRET manquant' });
  const corps = await brut(req);
  if (!signatureValide(corps, req.headers['stripe-signature'], secret)) return res.status(400).json({ erreur: 'signature' });
  let ev = {}; try { ev = JSON.parse(corps); } catch (e) { return res.status(400).end(); }
  try {
    if (['checkout.session.completed', 'checkout.session.async_payment_succeeded'].includes(ev.type)) {
      const s = (ev.data || {}).object || {};
      if ((s.metadata || {}).boutique === 'truflame') {
        const r = await lireSession(s.id);   // on relit la session chez Stripe (adresse de livraison complète)
        const f = await finaliser(r.ok ? r.j : s);
        console.log('stripe webhook', ev.type, s.id, f.ok ? (f.nouvelle ? 'nouvelle' : 'déjà là') : 'non payée');
      }
    }
    return res.status(200).json({ recu: true });
  } catch (e) { console.error('stripe webhook', String(e.message || e)); return res.status(500).json({ erreur: 'serveur' }); }
};
