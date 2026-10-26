// Chiffres de la page /stats/ (site + livre), SANS connexion : la cle du lien
// est verifiee par son empreinte SHA-256 ici, puis encore une fois en base.
const crypto = require('crypto');
const { requete, corps } = require('./_db');

const EMPREINTE = 'bdc6b46cb6a4b4e49b656f0e807106375b4975fd88ebe742fc02583536589873';
const PERIODES = ['auj', '7j', '30j', '90j', '365j', 'tout'];

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'GET') {   // simple test de connexion, sans aucun chiffre
    try { await requete('select 1', []); return res.status(200).json({ base: 'ok' }); }
    catch (e) { return res.status(200).json({ base: 'injoignable', raison: String(e.message || e).slice(0, 200) }); }
  }
  if (req.method !== 'POST') return res.status(405).json({ success: false });
  const b = await corps(req);
  if (crypto.createHash('sha256').update(String(b.k || '')).digest('hex') !== EMPREINTE) {
    return res.status(403).json({ success: false, error: 'Lien invalide.' });
  }
  try {
    const per = PERIODES.includes(b.periode) ? b.periode : '30j';
    const r = await requete('select public.stats_publiques_cle($1, $2) as d', [String(b.k), per]);
    return res.status(200).json({ success: true, ...r.rows[0].d });
  } catch (e) {
    return res.status(500).json({ success: false, error: 'Base injoignable : ' + String(e.message || e).slice(0, 160) });
  }
};
