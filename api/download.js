// Téléchargement du PDF, uniquement avec un lien signé fourni après un paiement réussi.
const fs = require('fs');
const path = require('path');
const { lienValide, lireCookieAchat } = require('./_paypal');
const { requete, empreinte } = require('./_db');

// Le lien ne marche que pour l'acheteur : son navigateur (cookie d'achat) ou son IP + appareil.
// Un lien partagé ouvert par quelqu'un d'autre renvoie vers la page de vente.
const VENTE = 'https://gesetze.skillora.me/gesetze/?lien=fremd';
async function estAcheteur(req, commande) {
  if (lireCookieAchat(req) === commande) return true;
  try { const r = await requete('select public.ebook_achat_ok($1,$2) as v', ['pp_' + commande, empreinte(req)]); return !!(r.rows[0] && r.rows[0].v); }
  catch (e) { console.error('download', String(e.message || e)); return true; }   // base injoignable : on ne bloque pas un vrai acheteur
}

module.exports = async (req, res) => {
  const q = req.query || {};
  if (!process.env.PAYPAL_SECRET || !lienValide(String(q.o || ''), String(q.e || ''), String(q.s || ''))) {
    res.status(403).setHeader('Content-Type', 'text/plain; charset=utf-8');
    return res.end('Link ungültig oder abgelaufen. Schreib uns auf TikTok @magniizz.');
  }
  if (!(await estAcheteur(req, String(q.o)))) { res.statusCode = 302; res.setHeader('Location', VENTE); return res.end(); }
  const f = path.join(process.cwd(), 'api', '_livre', 'gesetzbuch.pdf');
  res.setHeader('Content-Type', 'application/pdf');
  res.setHeader('Content-Disposition', 'attachment; filename="Das_Gesetzbuch_des_Geistes.pdf"');
  res.setHeader('Cache-Control', 'private, no-store');
  fs.createReadStream(f).pipe(res);
};
