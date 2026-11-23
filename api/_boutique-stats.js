// Tableau de bord Dropshipping (/stats/truflame.html) : même clé que la page /stats/ (vérifiée par son empreinte).
// Produit actuel : Turbo Jet Blower (souffleur). Tables SQL torch_* gardées (visites + commandes de la boutique).
const crypto = require('crypto');
const { requete, corps } = require('./_db');

const EMPREINTE = 'bdc6b46cb6a4b4e49b656f0e807106375b4975fd88ebe742fc02583536589873';
const PERIODES = ['auj', '7j', '30j', '90j', 'tout'];

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') return res.status(405).json({ success: false });
  const b = await corps(req);
  if (crypto.createHash('sha256').update(String(b.k || '')).digest('hex') !== EMPREINTE) return res.status(403).json({ success: false, error: 'Lien invalide.' });
  try {
    if (b.action === 'statut') {
      await requete('select public.torch_statut($1,$2)', [String(b.id || ''), String(b.statut || '')]);
      return res.status(200).json({ success: true });
    }
    const r = await requete('select public.torch_stats($1) as d', [PERIODES.includes(b.periode) ? b.periode : '30j']);
    const d = r.rows[0].d;
    try { d.paiements = (await requete("select public.paiement_stats(array['torch'], $1) as p", [PERIODES.includes(b.periode) ? b.periode : '30j'])).rows[0].p; }
    catch (e) { console.error('paiement_stats', String(e.message || e)); }
    return res.status(200).json({ success: true, ...d });
  } catch (e) { return res.status(500).json({ success: false, error: 'Base injoignable : ' + String(e.message || e).slice(0, 160) }); }
};
