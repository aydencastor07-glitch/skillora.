// Une seule fonction Vercel pour 3 routes (le plan gratuit limite à 12 fonctions) :
//   /api/whop-webhook   -> _whop-webhook.js  (paiements Whop : ebook + souffleur)
//   /api/stripe-webhook -> _stripe-webhook.js
//   /api/blower         -> _blower.js        (adresse du souffleur avant le paiement + suivi des visites)
//   /api/torch-stats    -> _boutique-stats.js (tableau Dropshipping)
// Les anciennes adresses restent valables grâce aux « rewrites » de vercel.json.
const ROUTES = {
  whop: () => require('./_whop-webhook'),
  stripe: () => require('./_stripe-webhook'),
  blower: () => require('./_blower'),
  stats: () => require('./_boutique-stats'),
};
module.exports = (req, res) => {
  const r = ROUTES[String((req.query || {}).src || '')];
  if (!r) return res.status(404).json({ erreur: 'route' });
  return r()(req, res);
};
