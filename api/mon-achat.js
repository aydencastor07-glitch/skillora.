// « Ai-je déjà acheté ce livre ? » — reconnu par le cookie d'achat de ce navigateur, sinon par l'empreinte
// IP + appareil. Si oui : nouveau lien de téléchargement (le client ne repaie jamais).
const { configure, lien, cookieAchat, lireCookieAchat, produit } = require('./_paypal');
const { requete, empreinte } = require('./_db');

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (!configure()) return res.status(200).json({ achete: false });
  const p = produit(String((req.query || {}).produit || ''));   // ?produit=laws : édition anglaise
  let commande = lireCookieAchat(req, p);
  if (!commande) {
    try {
      const r = await requete('select public.ebook_achat_fp($1,$2) as v', [p, empreinte(req)]);
      const v = r.rows[0] && r.rows[0].v;
      if (v && v.startsWith('pp_')) { commande = v.slice(3); res.setHeader('Set-Cookie', cookieAchat(commande, p)); }
    } catch (e) { console.error('mon-achat', String(e.message || e)); }
  }
  if (!commande) return res.status(200).json({ achete: false });
  let email = '';
  try { const r = await requete('select public.ebook_email_lire($1) as v', ['pp_' + commande]); email = (r.rows[0] && r.rows[0].v) || ''; } catch (e) {}
  res.status(200).json({ achete: true, lien: lien(commande, false, p), email });
};
