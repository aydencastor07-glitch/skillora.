// Encaisse la commande, vérifie montant + produit, puis renvoie le lien de téléchargement signé.
const { configure, prixMin, paypal, lien, lireCorps, cookieAchat, PRODUITS } = require('./_paypal');
const { requete, empreinte } = require('./_db');
const { noterEssai } = require('./_essai');

module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ erreur: 'POST' });
  if (!configure()) return res.status(503).json({ erreur: 'PayPal non configuré' });
  try {
    const { orderID, moi } = await lireCorps(req);
    if (!orderID || !/^[A-Z0-9]{8,30}$/.test(orderID)) return res.status(400).json({ erreur: 'commande' });
    const r = await paypal('/v2/checkout/orders/' + orderID + '/capture');
    const j = r.j || {};
    // déjà encaissée (double clic, rechargement) : on relit la commande
    const u = (j.purchase_units || [])[0] || {};
    const cap = ((u.payments || {}).captures || [])[0] || {};
    const p = u.custom_id || cap.custom_id;   // produit enregistré dans la commande par api/paypal-order.js
    const P = Object.prototype.hasOwnProperty.call(PRODUITS, p) ? PRODUITS[p] : null;
    const ok = !!P && j.status === 'COMPLETED' && cap.status === 'COMPLETED' && cap.amount && cap.amount.currency_code === P.devise
      && Number(cap.amount.value) >= Number(prixMin(p)) - 0.001;
    if (!ok) { console.error('capture', r.status, JSON.stringify(j).slice(0, 800)); await noterEssai(req, P ? p : 'laws', 'refus', orderID, ((j.details || [])[0] || {}).issue || ('statut ' + (j.status || r.status)), moi); return res.status(402).json({ erreur: 'paiement', detail: (j.details || [])[0] && j.details[0].issue }); }
    await noterEssai(req, p, 'paye', orderID, '', moi);
    console.log('VENTE', orderID, p, cap.amount.value, cap.amount.currency_code, (j.payer || {}).email_address || '');
    try {   // la vente apparaît dans /stats/ ; une erreur ici ne doit jamais bloquer le téléchargement
      const pays = ((j.payer || {}).address || {}).country_code || String(req.headers['x-vercel-ip-country'] || '');
      await requete('select public.ebook_vente($1,$2,$3,$4,$5,$6)', ['pp_' + orderID, p, Math.round(Number(cap.amount.value) * 100), P.devise, pays, empreinte(req)]);
      await requete('select public.ebook_email($1,$2)', ['pp_' + orderID, (j.payer || {}).email_address || '']);
    } catch (e) { console.error('ebook_vente', String(e.message || e)); }
    // l'e-mail n'est PAS envoyé ici : l'acheteur confirme ou corrige son adresse sur l'écran « Danke » (api/envoyer-livre.js)
    res.setHeader('Set-Cookie', cookieAchat(orderID, p));   // ce navigateur est reconnu comme acheteur
    res.status(200).json({ lien: lien(orderID, false, p), email: (j.payer || {}).email_address || '' });
  } catch (e) { console.error(e); res.status(500).json({ erreur: 'serveur' }); }
};
