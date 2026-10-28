// Téléchargement du PDF, uniquement avec un lien signé fourni après un paiement réussi.
const fs = require('fs');
const path = require('path');
const { lienValide, lireCookieAchat, cookieAchat } = require('./_paypal');
const { requete, empreinte } = require('./_db');

// Le lien ne marche que pour l'acheteur : son navigateur (cookie d'achat) ou son IP + appareil.
// Un lien partagé ouvert par quelqu'un d'autre renvoie vers la page de vente.
const VENTE = 'https://gesetze.skillora.me/gesetze/?lien=fremd';
async function estAcheteur(req, commande) {
  if (lireCookieAchat(req) === commande) return true;
  try { const r = await requete('select public.ebook_achat_ok($1,$2) as v', ['pp_' + commande, empreinte(req)]); return r.rows[0] && r.rows[0].v ? 'fp' : false; }
  catch (e) { console.error('download', String(e.message || e)); return true; }   // base injoignable : on ne bloque pas un vrai acheteur
}

module.exports = async (req, res) => {
  const q = req.query || {};
  const mail = q.m === '1';   // lien de l'e-mail d'achat : il arrive dans la boîte de l'acheteur, on ne revérifie pas l'appareil
  if (!process.env.PAYPAL_SECRET || !lienValide(String(q.o || ''), String(q.e || ''), String(q.s || ''), mail)) {
    res.status(403).setHeader('Content-Type', 'text/plain; charset=utf-8');
    return res.end('Link ungültig oder abgelaufen. Schreib uns auf TikTok @magniizz.');
  }
  const ok = mail ? 'mail' : await estAcheteur(req, String(q.o));
  if (!ok) { res.statusCode = 302; res.setHeader('Location', VENTE); return res.end(); }
  if (ok === 'fp' || ok === 'mail') res.setHeader('Set-Cookie', cookieAchat(String(q.o)));   // reconnu par IP + appareil : on marque aussi ce navigateur
  const f = path.join(process.cwd(), 'api', '_livre', 'gesetzbuch.pdf');
  res.setHeader('Content-Type', 'application/pdf');
  res.setHeader('Content-Disposition', 'attachment; filename="Das_Gesetzbuch_des_Geistes.pdf"');
  res.setHeader('Cache-Control', 'private, no-store');
  fs.createReadStream(f).pipe(res);
};
