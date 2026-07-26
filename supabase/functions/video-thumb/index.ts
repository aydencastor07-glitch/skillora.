// Miniature publique d'une vidéo, résolue côté serveur.
//
// Pourquoi côté serveur : depuis le navigateur, l'oEmbed de TikTok est bloqué par
// CORS, et les liens courts (vm.tiktok.com) doivent d'abord être suivis. Résultat,
// la miniature n'apparaissait jamais dans l'animation de copie. Ici on suit la
// redirection puis on interroge l'oEmbed, sans contrainte d'origine.
//
// N'expose qu'une URL d'image déjà publique, et seulement pour des hébergeurs connus.

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
};

const HOTES_AUTORISES = /(^|\.)(tiktok\.com|youtube\.com|youtu\.be|instagram\.com|facebook\.com|fb\.watch)$/i;

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

    // YouTube : la miniature se déduit de l'identifiant, aucun appel réseau.
    const yt = brut.match(/(?:youtu\.be\/|[?&]v=|\/shorts\/|\/embed\/)([\w-]{11})/);
    if (yt) return reponse(`https://i.ytimg.com/vi/${yt[1]}/hqdefault.jpg`, { source: 'youtube-id' });

    if (/tiktok\.com$/i.test(u.hostname) || /(^|\.)tiktok\.com$/i.test(u.hostname)) {
      // Lien court (vm./vt.tiktok.com) : on suit la redirection pour obtenir l'URL longue,
      // l'oEmbed ne répond pas correctement sur les liens courts.
      let cible = brut;
      if (/^(vm|vt)\./i.test(u.hostname)) {
        try {
          const r = await fetchAvecDelai(brut, 3500, { method: 'GET' });
          if (r.url && /\/video\/|\/photo\//.test(r.url)) cible = r.url.split('?')[0];
        } catch { /* on retente quand même l'oEmbed sur le lien court */ }
      }
      try {
        const r = await fetchAvecDelai('https://www.tiktok.com/oembed?url=' + encodeURIComponent(cible), 3500);
        if (r.ok) {
          const j = await r.json();
          if (j?.thumbnail_url) return reponse(String(j.thumbnail_url), { source: 'tiktok-oembed' });
        }
      } catch { /* silence : on renverra null */ }
      return reponse(null, { raison: 'miniature TikTok indisponible' });
    }

    return reponse(null, { raison: 'aucune miniature publique pour cet hébergeur' });
  } catch (e) {
    return reponse(null, { raison: String((e as Error)?.message || e) });
  }
});
