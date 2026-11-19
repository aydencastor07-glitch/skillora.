// Note chaque essai de paiement (début, refus, annulation, erreur, payé) dans paiement_essais.
// Sert à voir si PayPal bloque des acheteurs, et dans quels pays. Ne bloque jamais le paiement.
const { requete, empreinte } = require('./_db');

const ROBOTS = /bot|crawl|spider|slurp|preview|headless|lighthouse/i;

async function noterEssai(req, site, etape, orderID, detail, moi) {
  try {
    const ua = String(req.headers['user-agent'] || '');
    if (moi || ROBOTS.test(ua)) return;   // le propriétaire (?moi=1) et les robots ne comptent pas
    const u = ua.toLowerCase();
    const device = /ipad|tablet|(android(?!.*mobi))/.test(u) ? 'tablette' : /iphone|ipod|android.*mobi|windows phone/.test(u) ? 'mobile' : 'desktop';
    const os = /iphone|ipad|ipod/.test(u) ? 'iOS' : /android/.test(u) ? 'Android' : /windows/.test(u) ? 'Windows' : /mac os|macintosh/.test(u) ? 'macOS' : null;
    const pays = String(req.headers['x-vercel-ip-country'] || '').toUpperCase();
    let ville = String(req.headers['x-vercel-ip-city'] || ''); try { ville = decodeURIComponent(ville); } catch (e) {}
    await requete('select public.paiement_noter($1,$2,$3,$4,$5,$6,$7,$8,$9)', [site, etape, orderID || '', detail || '', empreinte(req),
      /^[A-Z]{2}$/.test(pays) ? pays : null, ville || null, device, os]);
  } catch (e) { console.error('paiement_noter', String(e.message || e)); }
}

module.exports = { noterEssai };
