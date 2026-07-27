// Miniature publique d'une vidéo, résolue côté serveur.
//
// Pourquoi côté serveur : depuis le navigateur, les plateformes bloquent l'appel
// direct (CORS), et les liens courts (vm.tiktok.com) doivent d'abord être suivis.
// Résultat, la miniature n'apparaissait jamais dans l'animation de copie.
//
// N'expose qu'une URL d'image déjà publique, et seulement pour des hébergeurs connus.

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
};

const HOTES_AUTORISES = /(^|\.)(tiktok\.com|youtube\.com|youtu\.be|instagram\.com|facebook\.com|fb\.watch|fb\.me)$/i;

// Navigateur crédible : sans ça, plusieurs plateformes renvoient une page de
// vérification au lieu du balisage de la page.
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
           '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

function reponse(thumb: string | null, extra: Record<string, unknown> = {}) {
  return new Response(JSON.stringify({ thumb, ...extra }), {
    headers: { ...CORS, 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=86400' },
  });
}

// Abandonne vite : mieux vaut pas de miniature qu'une animation qui attend.
async function fetchAvecDelai(url: string, ms: number, init?: RequestInit) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { ...init, signal: ctl.signal, redirect: 'follow' }); }
  finally { clearTimeout(t); }
}

// Image que la page publie elle-même pour l'affichage des liens partagés.
// Toutes les plateformes la fournissent (Instagram, Facebook, TikTok, X…) :
// c'est le filet de sécurité universel, sans compte ni cookie.
async function ogImage(url: string): Promise<string | null> {
  let html = '';
  try {
    const r = await fetchAvecDelai(url, 6000, {
      headers: { 'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'fr,en;q=0.8' },
    });
    if (!r.ok) return null;
    html = (await r.text()).slice(0, 400000);
  } catch { return null; }

  const motifs = [
    /<meta[^>]+property=["']og:image(?::secure_url)?["'][^>]+content=["']([^"']+)/i,
    /<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image/i,
    /<meta[^>]+name=["']twitter:image["'][^>]+content=["']([^"']+)/i,
    /"thumbnail_url"\s*:\s*"([^"]+)"/i,
    /"display_url"\s*:\s*"([^"]+)"/i,
  ];
  for (const m of motifs) {
    const r = html.match(m);
    if (!r) continue;
    const src = r[1].replace(/&amp;/g, '&').replace(/\\u0026/g, '&').replace(/\\\//g, '/');
    if (src.startsWith('http')) return src;
  }
  return null;
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS });

  try {
    let brut = new URL(req.url).searchParams.get('url') || '';
    if (!brut && req.method === 'POST') {
      const body = await req.json().catch(() => ({}));
      brut = String(body?.url || '');
    }
    brut = brut.trim();
    if (!/^https?:\/\//i.test(brut)) return reponse(null, { raison: 'lien invalide' });

    let u: URL;
    try { u = new URL(brut); } catch { return reponse(null, { raison: 'lien illisible' }); }
    if (!HOTES_AUTORISES.test(u.hostname)) return reponse(null, { raison: 'hébergeur non pris en charge' });

    // 1. YouTube : la miniature se déduit de l'identifiant, aucun appel réseau.
    const yt = brut.match(/(?:youtu\.be\/|[?&]v=|\/shorts\/|\/embed\/|\/live\/)([\w-]{11})/);
    if (yt) return reponse(`https://i.ytimg.com/vi/${yt[1]}/hqdefault.jpg`, { source: 'youtube-id' });

    // 2. TikTok : oEmbed officiel. Les liens courts vm./vt. doivent d'abord être suivis.
    let cible = brut;
    if (/(^|\.)tiktok\.com$/i.test(u.hostname)) {
      if (/^(vm|vt)\./i.test(u.hostname)) {
        try {
          const r = await fetchAvecDelai(brut, 4000, { headers: { 'User-Agent': UA } });
          if (r.url && /\/video\/|\/photo\//.test(r.url)) cible = r.url.split('?')[0];
        } catch { /* on retente quand même l'oEmbed */ }
      }
      try {
        const r = await fetchAvecDelai('https://www.tiktok.com/oembed?url=' + encodeURIComponent(cible), 4000);
        if (r.ok) {
          const j = await r.json();
          if (j?.thumbnail_url) return reponse(String(j.thumbnail_url), { source: 'tiktok-oembed' });
        }
      } catch { /* on bascule sur og:image */ }
    }

    // 3. Filet universel : Instagram, Facebook, et TikTok si l'oEmbed a échoué.
    const og = await ogImage(cible);
    if (og) return reponse(og, { source: 'og:image' });

    return reponse(null, { raison: 'aucune miniature publique trouvée' });
  } catch (e) {
    return reponse(null, { raison: String((e as Error)?.message || e) });
  }
});
