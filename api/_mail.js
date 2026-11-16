// E-mail d'achat (Resend) : le PDF en pièce jointe + un lien de téléchargement valable 1 an.
// Clé RESEND_API_KEY dans les réglages Vercel (jamais dans le code). Sans clé : rien n'est envoyé.
const fs = require('fs');
const path = require('path');

const FROM = process.env.EMAIL_FROM_BUCH || 'Das Gesetzbuch des Geistes <buch@skillora.me>';
const SITE = 'https://gesetze.skillora.me';

async function envoyerLivre(email, lienMail, p) {
  if (p === 'laws') return envoyerLaws(email, lienMail);
  if (!process.env.RESEND_API_KEY || !email) return false;
  const pdf = fs.readFileSync(path.join(process.cwd(), 'api', '_livre', 'gesetzbuch.pdf')).toString('base64');
  const url = SITE + lienMail;
  // E-mail sobre (peu de couleurs, un seul bouton, version texte) : il a plus de chances d'arriver dans « Principale » et non « Promotions ».
  const html = `<div style="font-family:Georgia,serif;max-width:520px;margin:auto;color:#2a2622;line-height:1.5">
  <p style="text-align:center;margin:0 0 10px"><img src="${SITE}/gesetze/mail_buch.jpg" width="150" alt="Das Gesetzbuch des Geistes" style="width:150px;height:auto;border:0"></p>
  <h2 style="font-family:Georgia,serif;color:#a8803a;margin-bottom:4px">Danke für deinen Kauf!</h2>
  <p>Hier ist dein E-Book <b>„Das Gesetzbuch des Geistes – 21 Gesetze, die dein Leben formen“</b>.</p>
  <p>📎 <b>Das PDF hängt an dieser E-Mail</b> – tippe darauf und speichere es (iPhone: Teilen → „In Bücher sichern“). So kannst du es jederzeit lesen, auch ohne Internet.</p>
  <p style="text-align:center;margin:26px 0"><a href="${url}" style="background:#c9a25a;color:#1a140b;text-decoration:none;font-weight:bold;padding:14px 26px;border-radius:8px;display:inline-block">⬇ PDF herunterladen</a></p>
  <p style="font-size:14px;color:#6b5f4d">Der Download-Link gilt 1 Jahr. Bitte teile ihn nicht – er ist für dich persönlich.</p>
  <p>Fang mit Gesetz Nr. 1 an: „Handle nie aus Wut“ – lies es heute und mach die Übung.</p>
  <p style="font-size:14px;color:#6b5f4d">@magniizz</p></div>`;
  const texte = 'Danke für deinen Kauf!\n\nHier ist dein E-Book „Das Gesetzbuch des Geistes – 21 Gesetze, die dein Leben formen“.\n'
    + 'Das PDF hängt an dieser E-Mail. iPhone: antippen, Teilen, „In Bücher sichern“ – dann kannst du es auch ohne Internet lesen.\n\n'
    + 'Download (1 Jahr gültig, bitte nicht teilen): ' + url + '\n\nFang mit Gesetz Nr. 1 an: „Handle nie aus Wut“.\n\n@magniizz';
  const r = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + process.env.RESEND_API_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from: FROM, to: [email], subject: 'Dein E-Book: Das Gesetzbuch des Geistes', html, text: texte,
      attachments: [{ filename: 'Das_Gesetzbuch_des_Geistes.pdf', content: pdf }],
    }),
  });
  if (!r.ok) { console.error('mail', r.status, (await r.text()).slice(0, 300)); return false; }
  return true;
}

// Édition anglaise « The Laws of the Mind » (page /laws/) : même e-mail, en anglais, avec le PDF anglais.
async function envoyerLaws(email, lienMail) {
  if (!process.env.RESEND_API_KEY || !email) return false;
  const pdf = fs.readFileSync(path.join(process.cwd(), 'api', '_livre', 'laws_of_the_mind.pdf')).toString('base64');
  const url = SITE + lienMail;
  const html = `<div style="font-family:Georgia,serif;max-width:520px;margin:auto;color:#2a2622;line-height:1.5">
  <p style="text-align:center;margin:0 0 10px"><img src="${SITE}/laws/mail_book.jpg" width="150" alt="The Laws of the Mind" style="width:150px;height:auto;border:0"></p>
  <h2 style="font-family:Georgia,serif;color:#a8803a;margin-bottom:4px">Thank you for your purchase!</h2>
  <p>Here is your ebook <b>“The Laws of the Mind – 21 Laws That Shape Your Life”</b>.</p>
  <p>📎 <b>The PDF is attached to this email</b> – tap it and save it (iPhone: Share → “Save to Books”). That way you can read it anytime, even offline.</p>
  <p style="text-align:center;margin:26px 0"><a href="${url}" style="background:#c9a25a;color:#1a140b;text-decoration:none;font-weight:bold;padding:14px 26px;border-radius:8px;display:inline-block">⬇ Download the PDF</a></p>
  <p style="font-size:14px;color:#6b5f4d">The download link is valid for 1 year. Please don't share it – it's just for you.</p>
  <p>Start with Law No. 1: “Never act out of anger” – read it today and do the exercise.</p>
  <p style="font-size:14px;color:#6b5f4d">@magniizz</p></div>`;
  const texte = 'Thank you for your purchase!\n\nHere is your ebook “The Laws of the Mind – 21 Laws That Shape Your Life”.\n'
    + 'The PDF is attached to this email. iPhone: tap it, Share, “Save to Books” – then you can read it offline too.\n\n'
    + 'Download (valid for 1 year, please don\'t share): ' + url + '\n\nStart with Law No. 1: “Never act out of anger”.\n\n@magniizz';
  const r = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + process.env.RESEND_API_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from: process.env.EMAIL_FROM_LAWS || 'The Laws of the Mind <buch@skillora.me>', to: [email], subject: 'Your ebook: The Laws of the Mind', html, text: texte,
      attachments: [{ filename: 'The_Laws_of_the_Mind.pdf', content: pdf }],
    }),
  });
  if (!r.ok) { console.error('mail laws', r.status, (await r.text()).slice(0, 300)); return false; }
  return true;
}

module.exports = { envoyerLivre };
