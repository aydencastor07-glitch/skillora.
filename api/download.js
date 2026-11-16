// Téléchargement du PDF, uniquement avec un lien signé fourni après un paiement réussi.
const fs = require('fs');
const path = require('path');
const { lienValide, lireCookieAchat, cookieAchat, PRODUITS, produit } = require('./_paypal');
const { requete, empreinte } = require('./_db');

// Le lien ne marche que pour l'acheteur : son navigateur (cookie d'achat) ou son IP + appareil.
// Un lien partagé ouvert par quelqu'un d'autre renvoie vers la page de vente.
const VENTE = 'https://gesetze.skillora.me';   // + page du produit + ?lien=fremd
async function estAcheteur(req, commande, p) {
  if (lireCookieAchat(req, p) === commande) return true;
  try { const r = await requete('select public.ebook_achat_ok($1,$2) as v', ['pp_' + commande, empreinte(req)]); return r.rows[0] && r.rows[0].v ? 'fp' : false; }
  catch (e) { console.error('download', String(e.message || e)); return true; }   // base injoignable : on ne bloque pas un vrai acheteur
}

module.exports = async (req, res) => {
  const q = req.query || {};
  const mail = q.m === '1';
  const p = produit(String(q.p || '')); const P = PRODUITS[p]; const en = p !== 'gesetzbuch';   // lien de l'e-mail d'achat : il arrive dans la boîte de l'acheteur, on ne revérifie pas l'appareil
  if (!process.env.PAYPAL_SECRET || !lienValide(String(q.o || ''), String(q.e || ''), String(q.s || ''), mail, p)) {
    res.status(403).setHeader('Content-Type', 'text/plain; charset=utf-8');
    return res.end(en ? 'Invalid or expired link. Message us on TikTok @magniizz.' : 'Link ungültig oder abgelaufen. Schreib uns auf TikTok @magniizz.');
  }
  const ok = mail ? 'mail' : await estAcheteur(req, String(q.o), p);
  if (!ok) { res.statusCode = 302; res.setHeader('Location', VENTE + P.page + '?lien=fremd'); return res.end(); }
  if (ok === 'fp' || ok === 'mail') res.setHeader('Set-Cookie', cookieAchat(String(q.o), p));   // reconnu par IP + appareil : on marque aussi ce navigateur
  const f = path.join(process.cwd(), 'api', '_livre', P.pdf);
  res.setHeader('Content-Type', 'application/pdf');
  res.setHeader('Content-Disposition', 'attachment; filename="' + P.fichier + '"');
  res.setHeader('Cache-Control', 'private, no-store');
  fs.createReadStream(f).pipe(res);
};
