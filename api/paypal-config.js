// Donne à la page le Client ID PayPal (public par nature) et le prix ; vide si PayPal n'est pas encore configuré.
const { configure, prix } = require('./_paypal');

module.exports = (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (!configure()) return res.status(200).json({ actif: false });
  res.status(200).json({ actif: true, clientId: process.env.PAYPAL_CLIENT_ID, prix: prix(), prixCode: prix('MAGNIIZZ') });
};
