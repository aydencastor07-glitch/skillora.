// Miniature publique d'une vidéo, résolue ET SERVIE côté serveur.
//
// Deux raisons de tout faire ici :
//  1. le navigateur ne peut pas interroger les plateformes directement (CORS) ;
//  2. surtout, les CDN d'Instagram et Facebook REFUSENT d'être affichés depuis
//     un autre domaine. Renvoyer l'adresse de l'image ne suffit donc pas : le
//     navigateur la reçoit et n'arrive pas à la charger. On relaie les octets.
//
// Deux modes :
//   ?url=...          -> JSON { thumb } (adresse trouvée)
//   ?url=...&raw=1    -> l'image elle-même (à mettre directement dans <img src>)

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
};

const HOTES_AUTORISES = /(^|\.)(tiktok\.com|youtube\.com|youtu\.be|instagram\.com|facebook\.com|fb\.watch|fb\.me)$/i;

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
           '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

function json(thumb: string | null, extra: Record<string, unknown> = {}) {
  return new Response(JSON.stringify({ thumb, ...extra }), {
    headers: { ...CORS, 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=86400' },
  });
}

async function fetchAvecDelai(url: string, ms: number, init?: RequestInit) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { ...init, signal: ctl.signal, redirect: 'follow' }); }
  finally { clearTimeout(t); }
}

// Image que la page publie elle-même pour l'affichage des liens partagés.
// Toutes les plateformes la fournissent : filet universel, sans compte ni cookie.
async function ogImage(url: string): Promise<string | null> {
  let html = '';
  try {
    const r = await fetchAvecDelai(url, 7000, {
      headers: { 'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'fr,en;q=0.8' },
    });
    if (!r.ok) return null;
    html = (await r.text()).slice(0, 500000);
  } catch { return null; }

  const motifs = [
    /<meta[^>]+property=["']og:image(?::secure_url)?["'][^>]+content=["']([^"']+)/i,
    /<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image/i,
    /<meta[^>]+name=["']twitter:image["'][^>]+content=["']([^"']+)/i,
    /"thumbnail_url"\s*:\s*"([^"]+)"/i,
    /"display_url"\s*:\s*"([^"]+)"/i,
    /"thumbnailUrl"\s*:\s*\[?\s*"([^"]+)"/i,
  ];
  for (const m of motifs) {
    const r = html.match(m);
    if (!r) continue;
    const src = r[1].replace(/&amp;/g, '&').replace(/\\u0026/g, '&').replace(/\\\//g, '/');
    if (src.startsWith('http')) return src;
  }
  return null;
}

async function resoudre(brut: string): Promise<{ src: string | null; source: string }> {
  const u = new URL(brut);

  // 1. YouTube : l'affiche se déduit de l'identifiant, aucun appel réseau.
  const yt = brut.match(/(?:youtu\.be\/|[?&]v=|\/shorts\/|\/embed\/|\/live\/)([\w-]{11})/);
  if (yt) return { src: `https://i.ytimg.com/vi/${yt[1]}/hqdefault.jpg`, source: 'youtube-id' };

  // 2. TikTok : oEmbed officiel (les liens courts vm./vt. sont suivis d'abord).
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
        if (j?.thumbnail_url) return { src: String(j.thumbnail_url), source: 'tiktok-oembed' };
      }
    } catch { /* on bascule sur og:image */ }
  }

  // 3. Filet universel : Instagram, Facebook, et TikTok si l'oEmbed a échoué.
  const og = await ogImage(cible);
  return og ? { src: og, source: 'og:image' } : { src: null, source: 'aucune' };
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS });

  const params = new URL(req.url).searchParams;
  const raw = params.get('raw') === '1';

  try {
    let brut = params.get('url') || '';
    if (!brut && req.method === 'POST') {
      const body = await req.json().catch(() => ({}));
      brut = String(body?.url || '');
    }
    brut = brut.trim();

    let u: URL | null = null;
    if (/^https?:\/\//i.test(brut)) { try { u = new URL(brut); } catch { u = null; } }
    if (!u || !HOTES_AUTORISES.test(u.hostname)) {
      return raw ? new Response('lien non pris en charge', { status: 400, headers: CORS })
                 : json(null, { raison: 'lien non pris en charge' });
    }

    const { src, source } = await resoudre(brut);
    if (!src) {
      return raw ? new Response('aucune miniature', { status: 404, headers: CORS })
                 : json(null, { raison: 'aucune miniature publique trouvée' });
    }
    if (!raw) return json(src, { source });

    // Mode image : on relaie les octets. Le referer de la plateforme evite les
    // refus d'affichage ; c'est le serveur qui telecharge, pas le navigateur.
    const ref = u.origin + '/';
    const img = await fetchAvecDelai(src, 12000, {
      headers: { 'User-Agent': UA, 'Referer': ref, 'Accept': 'image/avif,image/webp,image/*,*/*;q=0.8' },
    });
    if (!img.ok || !img.body) {
      return new Response('image inaccessible (' + img.status + ')', { status: 502, headers: CORS });
    }
    return new Response(img.body, {
      headers: {
        ...CORS,
        'Content-Type': img.headers.get('Content-Type') || 'image/jpeg',
        'Cache-Control': 'public, max-age=86400',
        'X-Skillora-Source': source,
      },
    });
  } catch (e) {
    const msg = String((e as Error)?.message || e);
    return raw ? new Response(msg, { status: 500, headers: CORS }) : json(null, { raison: msg });
  }
});
