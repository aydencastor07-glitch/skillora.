// Étape 1 de la caisse (/laws/) : l'email donné AVANT le paiement. On le garde pour envoyer le livre
// et pour pouvoir relancer les personnes qui n'ont pas acheté (avec désinscription possible).
// Stocké dans ebook_leads (Supabase) via public.ebook_lead() ; aucune IP enregistrée.
const { requete, corps, empreinte } = require('./_db');

const EMAIL = /^[^\s@<>"]{1,64}@[^\s@<>"]{1,180}\.[a-z]{2,24}$/i;

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') return res.status(405).json({ ok: false });
  try {
    const b = await corps(req);
    const email = String(b.email || '').trim().toLowerCase();
    const p = String(b.produit || '');
    if (!EMAIL.test(email) || !['laws', 'gesetzbuch'].includes(p)) return res.status(400).json({ ok: false });
    const pays = String(req.headers['x-vercel-ip-country'] || '').toUpperCase();
    await requete('select public.ebook_lead($1,$2,$3,$4)', [p, email, empreinte(req) || null, /^[A-Z]{2}$/.test(pays) ? pays : null]);
    return res.status(200).json({ ok: true });
  } catch (e) {
    console.log('lead:', String(e.message || e));
    return res.status(200).json({ ok: false });   // ne jamais bloquer l'achat
  }
};
