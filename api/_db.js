// Connexion DIRECTE a la base Supabase, sans passer par son « guichet web »
// (REST / fonctions) : quand Supabase le coupe (erreur 402, quota gratuit
// depasse), la base reste joignable par le pooler et ces pages marchent encore.
// Role skillora_stats : il ne peut qu'appeler stats_publiques_cle() et
// ebook_enregistrer() (voir supabase/migrations/20261027_stats_vercel.sql).
const { Pool } = require('pg');

const REF = 'fkjqlmtugzdluzshxqsk';
// Le nom du pooler depend du projet (aws-0 ou aws-1) : on essaie les deux et on retient celui qui repond.
const HOTES = ['aws-0-us-west-2.pooler.supabase.com', 'aws-1-us-west-2.pooler.supabase.com'];
let pool = null;

async function connecter() {
  let derniere;
  for (const host of HOTES) {
    const p = new Pool({
      host, port: 6543, database: 'postgres',
      user: 'skillora_stats.' + REF, password: process.env.STATS_DB_PASSWORD,
      ssl: { rejectUnauthorized: false }, max: 2, connectionTimeoutMillis: 6000, idleTimeoutMillis: 10000,
    });
    try { await p.query('select 1'); return p; }
    catch (e) { derniere = e; await p.end().catch(() => {}); }
  }
  throw derniere;
}

async function requete(sql, params) {
  if (!process.env.STATS_DB_PASSWORD) throw new Error('variable STATS_DB_PASSWORD absente dans Vercel');
  if (!pool) pool = await connecter();
  try { return await pool.query(sql, params); }
  catch (e) { pool = null; throw e; }
}

// Petit lecteur de corps : sendBeacon envoie du texte brut.
function corps(req) {
  return new Promise((ok) => {
    if (req.body && typeof req.body === 'object') return ok(req.body);
    if (typeof req.body === 'string') { try { return ok(JSON.parse(req.body || '{}')); } catch { return ok({}); } }
    let s = ''; req.on('data', (c) => { s += c; if (s.length > 20000) req.destroy(); });
    req.on('end', () => { try { ok(JSON.parse(s || '{}')); } catch { ok({}); } });
  });
}

// Empreinte d'un visiteur : IP + système du téléphone, salée puis hachée. L'IP n'est jamais enregistrée
// (impossible de la retrouver à partir de l'empreinte).
function empreinte(req) {
  const crypto = require('crypto');
  const ip = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim() || String(req.headers['x-real-ip'] || '');
  if (!ip) return '';
  const u = String(req.headers['user-agent'] || '').toLowerCase();
  const os = /iphone|ipad|ipod|ios/.test(u) ? 'iOS' : /android/.test(u) ? 'Android' : /windows/.test(u) ? 'Windows'
    : /mac os|macintosh/.test(u) ? 'macOS' : /linux/.test(u) ? 'Linux' : null;
  return 'ip_' + crypto.createHmac('sha256', 'vis:' + (process.env.STATS_DB_PASSWORD || '')).update(ip + '|' + os).digest('hex').slice(0, 24);
}

module.exports = { requete, corps, empreinte };
