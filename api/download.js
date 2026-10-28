// Téléchargement du PDF, uniquement avec un lien signé fourni après un paiement réussi.
const fs = require('fs');
const path = require('path');
const { lienValide } = require('./_paypal');

module.exports = (req, res) => {
  const q = req.query || {};
  if (!process.env.PAYPAL_SECRET || !lienValide(String(q.o || ''), String(q.e || ''), String(q.s || ''))) {
    res.status(403).setHeader('Content-Type', 'text/plain; charset=utf-8');
    return res.end('Link ungültig oder abgelaufen. Schreib uns auf TikTok @magniizz.');
  }
  const f = path.join(process.cwd(), 'api', '_livre', 'gesetzbuch.pdf');
  res.setHeader('Content-Type', 'application/pdf');
  res.setHeader('Content-Disposition', 'attachment; filename="Das_Gesetzbuch_des_Geistes.pdf"');
  res.setHeader('Cache-Control', 'private, no-store');
  fs.createReadStream(f).pipe(res);
};
