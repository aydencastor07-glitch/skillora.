// Boutique Truflame (Shopify) : paiement PayPal / carte directement sur la page du briquet, comme l'e-book.
// Les prix sont fixés ICI (la page ne peut pas choisir le prix). Les clés PayPal restent dans les réglages Vercel.
// POST { action: 'config' }                       -> { actif, clientId }
// POST { action: 'order', qty, mode, carte, retour } -> { id, approuver }
// POST { action: 'capture', orderID }              -> { ok, commande, nom, email }
const { configure, paypal, lireCorps } = require('./_paypal');
const { requete } = require('./_db');

const PRIX = { 1: '34.99', 2: '59.48', 3: '83.97' };   // 1 / 2 (-15 %) / 3 (-20 %) : les mêmes que sur la page
const NOM = 'Truflame Jet Torch';
const ORIGINES = /^https:\/\/([a-z0-9-]+\.myshopify\.com|(www\.)?truflame\.[a-z.]+)$/i;

function cors(req, res) {
  const o = String(req.headers.origin || '');
  if (ORIGINES.test(o)) { res.setHeader('Access-Control-Allow-Origin', o); res.setHeader('Vary', 'Origin'); }
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Cache-Control', 'no-store');
}

module.exports = async (req, res) => {
  cors(req, res);
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ erreur: 'POST' });
  const b = await lireCorps(req);
  if (b.action === 'config') return res.status(200).json(configure() ? { actif: true, clientId: process.env.PAYPAL_CLIENT_ID } : { actif: false });
  if (!configure()) return res.status(503).json({ erreur: 'PayPal non configuré' });
  try {
    if (b.action === 'order') {
      const qty = PRIX[b.qty] ? Number(b.qty) : 1;
      const value = PRIX[qty];
      const unite = {
        amount: { currency_code: 'USD', value, breakdown: { item_total: { currency_code: 'USD', value } } },
        items: [{ name: qty > 1 ? NOM + ' × ' + qty : NOM, quantity: '1', unit_amount: { currency_code: 'USD', value }, category: 'PHYSICAL_GOODS' }],
        description: NOM + ' × ' + qty, custom_id: 'torch:' + qty,
      };
      const contexte = { brand_name: 'Truflame', locale: 'en-US', shipping_preference: 'GET_FROM_FILE', user_action: 'PAY_NOW' };
      const corps = { intent: 'CAPTURE', purchase_units: [unite] };
      let base = String(b.retour || ''); try { const u = new URL(base); base = ORIGINES.test(u.origin) ? u.origin + u.pathname : ''; } catch (e) { base = ''; }
      if (b.mode === 'redirect' && base) {
        corps.payment_source = { paypal: { experience_context: { ...contexte, landing_page: b.carte ? 'GUEST_CHECKOUT' : 'LOGIN',
          return_url: base + '?pp=ok', cancel_url: base + '?pp=cancel' } } };
      } else corps.application_context = contexte;
      const r = await paypal('/v2/checkout/orders', corps);
      if (!r.ok) { console.error('torch order', r.status, JSON.stringify(r.j).slice(0, 500)); return res.status(502).json({ erreur: 'commande' }); }
      const approuver = (r.j.links || []).find((l) => l.rel === 'payer-action' || l.rel === 'approve');
      console.log('TORCH COMMANDE', r.j.id, qty, b.mode || 'sdk', b.carte ? 'carte' : 'paypal');
      return res.status(200).json({ id: r.j.id, approuver: approuver ? approuver.href : null });
    }
    if (b.action === 'capture') {
      const orderID = String(b.orderID || '');
      if (!/^[A-Z0-9]{8,30}$/.test(orderID)) return res.status(400).json({ erreur: 'commande' });
      const r = await paypal('/v2/checkout/orders/' + orderID + '/capture');
      const j = r.j || {};
      const u = (j.purchase_units || [])[0] || {};
      const cap = ((u.payments || {}).captures || [])[0] || {};
      const qty = Number(String(u.custom_id || cap.custom_id || '').replace('torch:', '')) || 0;
      const ok = !!PRIX[qty] && j.status === 'COMPLETED' && cap.status === 'COMPLETED' && cap.amount
        && cap.amount.currency_code === 'USD' && Number(cap.amount.value) >= Number(PRIX[qty]) - 0.001;
      if (!ok) { console.error('torch capture', r.status, JSON.stringify(j).slice(0, 800)); return res.status(402).json({ erreur: 'paiement', detail: (j.details || [])[0] && j.details[0].issue }); }
      const liv = u.shipping || {};
      const nom = (liv.name || {}).full_name || [((j.payer || {}).name || {}).given_name, ((j.payer || {}).name || {}).surname].filter(Boolean).join(' ');
      const email = (j.payer || {}).email_address || '';
      console.log('TORCH VENTE', orderID, qty, cap.amount.value, nom, JSON.stringify(liv.address || {}));
      try { await requete('select public.torch_commande($1,$2,$3,$4,$5,$6)', [orderID, qty, Math.round(Number(cap.amount.value) * 100), email, nom, JSON.stringify(liv.address || {})]); }
      catch (e) { console.error('torch_commande', String(e.message || e)); }   // la vente reste dans PayPal même si la base ne répond pas
      return res.status(200).json({ ok: true, commande: orderID, nom, email });
    }
    return res.status(400).json({ erreur: 'action' });
  } catch (e) { console.error(e); return res.status(500).json({ erreur: 'serveur' }); }
};
