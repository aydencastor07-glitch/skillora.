// « Mein E-Book senden » : l'acheteur (reconnu par son cookie d'achat ou son IP + appareil) reçoit le PDF
// à l'adresse qu'il a confirmée ou corrigée. Maximum 5 envois par achat.
const { configure, lien, lireCorps, lireCookieAchat, PRODUIT } = require('./_paypal');
const { requete, empreinte } = require('./_db');
const { envoyerLivre } = require('./_mail');

const EMAIL = /^[^\s@<>"]{1,64}@[^\s@<>"]{1,180}\.[a-z]{2,24}$/i;

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') return res.status(405).json({ erreur: 'POST' });
  if (!configure() || !process.env.RESEND_API_KEY) return res.status(503).json({ erreur: 'indisponible' });
  const { email } = await lireCorps(req);
  const adresse = String(email || '').trim();
  if (!EMAIL.test(adresse)) return res.status(400).json({ erreur: 'adresse' });
  try {
    let commande = lireCookieAchat(req);
    if (!commande) {
      const r = await requete('select public.ebook_achat_fp($1,$2) as v', [PRODUIT, empreinte(req)]);
      const v = r.rows[0] && r.rows[0].v; if (v && v.startsWith('pp_')) commande = v.slice(3);
    }
    if (!commande) return res.status(403).json({ erreur: 'acheteur' });
    const c = await requete('select public.ebook_mail_compte($1) as n', ['pp_' + commande]);
    const n = c.rows[0] ? c.rows[0].n : -1;
    if (n < 0) return res.status(403).json({ erreur: 'acheteur' });
    if (n > 5) return res.status(429).json({ erreur: 'limite' });
    const ok = await envoyerLivre(adresse, lien(commande, true));
    console.log('MAIL', commande, ok ? 'envoyé' : 'échec');
    res.status(ok ? 200 : 502).json({ ok });
  } catch (e) { console.error('envoyer-livre', String(e.message || e)); res.status(500).json({ erreur: 'serveur' }); }
};
