// Encaisse la commande, vérifie montant + produit, puis renvoie le lien de téléchargement signé.
const { configure, prix, paypal, lien, lireCorps, PRODUIT } = require('./_paypal');
const { requete } = require('./_db');

module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ erreur: 'POST' });
  if (!configure()) return res.status(503).json({ erreur: 'PayPal non configuré' });
  try {
    const { orderID } = await lireCorps(req);
    if (!orderID || !/^[A-Z0-9]{8,30}$/.test(orderID)) return res.status(400).json({ erreur: 'commande' });
    const r = await paypal('/v2/checkout/orders/' + orderID + '/capture');
    const j = r.j || {};
    // déjà encaissée (double clic, rechargement) : on relit la commande
    const u = (j.purchase_units || [])[0] || {};
    const cap = ((u.payments || {}).captures || [])[0] || {};
    const ok = j.status === 'COMPLETED' && cap.status === 'COMPLETED' && cap.amount && cap.amount.currency_code === 'EUR'
      && Number(cap.amount.value) >= Number(prix()) - 0.001 && (u.custom_id || cap.custom_id) === PRODUIT;
    if (!ok) { console.error('capture', r.status, JSON.stringify(j).slice(0, 800)); return res.status(402).json({ erreur: 'paiement', detail: (j.details || [])[0] && j.details[0].issue }); }
    console.log('VENTE', orderID, cap.amount.value, (j.payer || {}).email_address || '');
    try {   // la vente apparaît dans /stats/ ; une erreur ici ne doit jamais bloquer le téléchargement
      const pays = ((j.payer || {}).address || {}).country_code || String(req.headers['x-vercel-ip-country'] || '');
      await requete('select public.ebook_vente($1,$2,$3,$4,$5)', ['pp_' + orderID, PRODUIT, Math.round(Number(cap.amount.value) * 100), 'EUR', pays]);
    } catch (e) { console.error('ebook_vente', String(e.message || e)); }
    res.status(200).json({ lien: lien(orderID), email: (j.payer || {}).email_address || '' });
  } catch (e) { console.error(e); res.status(500).json({ erreur: 'serveur' }); }
};
