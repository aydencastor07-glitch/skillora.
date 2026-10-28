// « Ai-je déjà acheté ce livre ? » — reconnu par le cookie d'achat de ce navigateur, sinon par l'empreinte
// IP + appareil. Si oui : nouveau lien de téléchargement (le client ne repaie jamais).
const { configure, lien, cookieAchat, lireCookieAchat, PRODUIT } = require('./_paypal');
const { requete, empreinte } = require('./_db');

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (!configure()) return res.status(200).json({ achete: false });
  let commande = lireCookieAchat(req);
  if (!commande) {
    try {
      const r = await requete('select public.ebook_achat_fp($1,$2) as v', [PRODUIT, empreinte(req)]);
      const v = r.rows[0] && r.rows[0].v;
      if (v && v.startsWith('pp_')) { commande = v.slice(3); res.setHeader('Set-Cookie', cookieAchat(commande)); }
    } catch (e) { console.error('mon-achat', String(e.message || e)); }
  }
  if (!commande) return res.status(200).json({ achete: false });
  res.status(200).json({ achete: true, lien: lien(commande) });
};
