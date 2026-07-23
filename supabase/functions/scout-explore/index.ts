// SKILLORA — scout-explore : l'agent CHERCHEUR autonome (il "balade Gemini sur internet").
// =========================================================================================
// Remplace l'humain qui cherchait des liens de vidéos incroyables : pour chaque STYLE (niche),
// l'agent interroge la RECHERCHE TikTok de SociaVault (tri "most-liked", période "this-week"),
// garde uniquement les vidéos >= 50 000 vues, et les met en file `winning_videos` (scope=global,
// niche imposée). Le video-worker les fait ensuite ÉTUDIER par Gemini au repos -> style-library.
// Résultat : l'école de Gemini se remplit TOUTE SEULE avec ce qui cartonne CETTE SEMAINE.
//
// Coût maîtrisé : 1 requête de recherche par niche et par exécution (défaut : 9 niches).
// Déclenchement : cron hebdomadaire (voir scout-winners/README.md) ou POST manuel
//   { "niches": { "horror": "pov horror storytime", ... }, "max_per_niche": 3 }.
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const SV_SCRAPE = "https://api.sociavault.com/v1/scrape";
const GLOBAL_MIN_VIEWS = 50000;   // même seuil que scout-winners : l'école de Gemini
const DEFAULT_MAX_PER_NICHE = 3;  // les 3 meilleures par niche suffisent (Gemini agrège par vote)
// Fenêtre LARGE : une vidéo d'il y a 2-3 mois qui a fait des millions de vues est une
// EXCELLENTE prof. Le tri "most-liked" + le seuil de vues font le filtre qualité.
const DATE_POSTED = "last-3-months";

// Requêtes de recherche par NICHE — le vocabulaire des créateurs, pas du jargon.
// Couvre les grands univers de contenu, pas seulement les styles de montage.
const DEFAULT_NICHES: Record<string, string> = {
  // styles de montage
  talk_facecam: "storytime advice talking to camera",
  energetic: "high energy edit fast cuts",
  vlog: "day in my life vlog",
  horror: "pov horror story scary",
  luxury_aesthetic: "luxury lifestyle aesthetic",
  dance: "dance trend choreography",
  product: "product review unboxing",
  story: "emotional storytelling",
  // univers de contenu (ce que publient vraiment les créateurs)
  football: "football skills highlights",
  basketball: "basketball highlights hoops",
  edit: "4k edit transition velocity",
  gym: "gym motivation fitness transformation",
  food: "recipe cooking asmr food",
  comedy: "funny skit comedy",
  gaming: "gaming clip funny moments",
  cars: "car edit supercar",
  fashion: "outfit fashion grwm",
  beauty: "makeup transformation beauty",
  motivation: "motivational speech discipline mindset",
  lifestyle: "aesthetic routine lifestyle",
  travel: "travel destination cinematic",
  pets: "funny pets cute animals",
  tech: "tech gadgets unboxing",
  tiktok_shop: "tiktok shop finds product review must have amazon",
};

// Hashtag Instagram par niche (un mot, sans #)
const IG_TAGS: Record<string, string> = {
  talk_facecam: "storytime", energetic: "edits", vlog: "dayinmylife", horror: "scarystories",
  luxury_aesthetic: "luxurylifestyle", dance: "dancechallenge", product: "unboxing",
  story: "motivation", football: "football", basketball: "basketball", edit: "edits",
  gym: "gymmotivation", food: "foodasmr", comedy: "comedyvideos", gaming: "gamingclips",
  cars: "carsofinstagram", fashion: "ootd", beauty: "makeuptransformation",
  motivation: "motivationdaily", lifestyle: "aestheticlifestyle", travel: "travelreels",
  pets: "funnypets", tech: "techtok", tiktok_shop: "tiktokshopfinds",
};

function j(o: unknown, s = 200) {
  return new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });
}
// Cherche un lien mp4 N'IMPORTE OÙ dans l'objet (video_versions, playable_url, video_url…)
function deepFindMedia(o: any, depth = 0): string {
  if (!o || typeof o !== "object" || depth > 6) return "";
  if (Array.isArray(o)) {
    for (const it of o) { const r = deepFindMedia(it, depth + 1); if (r) return r; }
    return "";
  }
  const vv = o.video_versions;
  if (Array.isArray(vv) && vv[0] && typeof vv[0].url === "string" && vv[0].url.startsWith("http")) return vv[0].url;
  for (const [k, v] of Object.entries(o)) {
    if (typeof v === "string" && v.startsWith("http") &&
        /playable_url|^video_url$|browser_native_hd|browser_native_sd/i.test(k)) return v;
  }
  for (const v of Object.values(o)) {
    if (v && typeof v === "object") { const r = deepFindMedia(v, depth + 1); if (r) return r; }
  }
  return "";
}
// Cherche un compteur de vues N'IMPORTE OÙ dans l'objet
function deepFindViews(o: any, depth = 0): number {
  if (!o || typeof o !== "object" || depth > 6) return 0;
  let best = 0;
  for (const [k, v] of Object.entries(o)) {
    if (/^(views?|view_count|viewcount|play_count|playcount|video_view_count|ig_play_count|video_play_count)$/i.test(k)) {
      best = Math.max(best, parseViews(v));
    } else if (v && typeof v === "object") {
      best = Math.max(best, deepFindViews(v, depth + 1));
    }
  }
  return best;
}
// Trouve le 1er tableau d'objets (la liste de posts) où qu'il soit dans la réponse
function firstArray(o: any, depth = 0): any[] {
  if (!o || depth > 5) return [];
  if (Array.isArray(o)) return o.filter((x) => x && typeof x === "object");
  if (typeof o !== "object") return [];
  for (const v of Object.values(o)) {
    const r = firstArray(v, depth + 1);
    if (r.length) return r;
  }
  return [];
}
// Trouve un lien facebook.com de vidéo/reel dans l'objet
function deepFindFbUrl(o: any, depth = 0): string {
  if (!o || typeof o !== "object" || depth > 6) return "";
  for (const v of Object.values(o)) {
    if (typeof v === "string" && /facebook\.com\/(reel\/|watch|[^"]*\/videos\/)/.test(v)) return v.split("?")[0];
    if (v && typeof v === "object") { const r = deepFindFbUrl(v, depth + 1); if (r) return r; }
  }
  return "";
}
async function svGet(path: string, key: string) {
  const r = await fetch(SV_SCRAPE + path, { headers: { "X-API-Key": key } });
  if (!r.ok) throw new Error(`SociaVault ${r.status}`);
  return r.json();
}
function tiktokPlayUrl(v: any): string {
  const cands = [v?.video?.play_addr?.url_list, v?.video?.download_addr?.url_list,
                 v?.video?.play_addr_h264?.url_list, v?.video?.bit_rate?.[0]?.play_addr?.url_list];
  for (const c of cands) {
    const arr = Array.isArray(c) ? c : (c ? Object.values(c) : []);
    for (const u of arr) if (typeof u === "string" && u.startsWith("http")) return u;
  }
  return "";
}
// "1,2 M de vues" / "1.2M views" / 1200000 -> nombre
function parseViews(x: any): number {
  if (typeof x === "number") return x;
  if (!x) return 0;
  const s = String(x).replace(/[\s, ]/g, "").toLowerCase();
  const m = s.match(/([\d.]+)\s*(k|m|b|md)?/);
  if (!m) return 0;
  const n = parseFloat(m[1]);
  const mult = m[2] === "k" ? 1e3 : (m[2] === "m" ? 1e6 : (m[2] ? 1e9 : 1));
  return Math.round(n * mult);
}
// Engagement (likes / commentaires / partages) : présent DANS la même réponse SociaVault
// que les vues -> 0 crédit en plus. On renvoie null quand c'est inconnu (une virale n'a jamais
// vraiment 0 like) pour que le feed affiche "—" plutôt qu'un faux "0".
const RE_LIKE = /^(likes?|like_count|digg_count|favorite_count|reaction_count)$/i;
const RE_COMMENT = /^(comments?|comment_count)$/i;
const RE_SHARE = /^(shares?|share_count|reshare_count|repost_count|forward_count)$/i;
function deepFindNum(o: any, re: RegExp, depth = 0): number {
  if (!o || typeof o !== "object" || depth > 6) return 0;
  let best = 0;
  for (const [k, v] of Object.entries(o)) {
    if (re.test(k)) best = Math.max(best, parseViews(v));
    else if (v && typeof v === "object") best = Math.max(best, deepFindNum(v, re, depth + 1));
  }
  return best;
}
function engage(v: any): { likes: number | null; comments: number | null; shares: number | null } {
  const st = v?.statistics ?? v?.stats ?? {};
  const likes = Number(st.digg_count ?? st.like_count ?? 0) || deepFindNum(v, RE_LIKE);
  const comments = Number(st.comment_count ?? 0) || deepFindNum(v, RE_COMMENT);
  const shares = Number(st.share_count ?? st.forward_count ?? 0) || deepFindNum(v, RE_SHARE);
  return { likes: likes || null, comments: comments || null, shares: shares || null };
}
// Recherche YouTube (Shorts + vidéos). Gemini lit les liens YouTube DIRECTEMENT,
// donc pas besoin de media_url : l'étude est gratuite en téléchargement.
async function youtubeSearch(query: string, key: string, uploadDate = "this_month") {
  const data = await svGet(`/youtube/search?query=${encodeURIComponent(query)}` +
                           (uploadDate ? `&uploadDate=${uploadDate}` : ""), key);
  const d = data.data ?? data;
  let groups = [d.shorts, d.videos, d.results, d.items].filter(Array.isArray) as any[][];
  if (!groups.length) groups = [firstArray(d)];   // dernier recours : 1er tableau trouvé
  const out: { views: number; create_time: number; url: string; media_url: string; likes: number | null; comments: number | null; shares: number | null }[] = [];
  for (const g of groups) {
    for (const it of g) {
      const v = it?.video ?? it?.short ?? it;      // résultat parfois emballé
      const id = v.video_id ?? v.videoId ?? v.id ?? "";
      if (!id || typeof id !== "string") continue;
      const views = parseViews(v.view_count ?? v.views ?? v.viewCount ?? v.view_count_text ??
                               v.viewCountText ?? v.short_view_count ?? v.stats?.views) || deepFindViews(v);
      const isShort = String(v.type ?? v.url ?? "").includes("short") || g === d.shorts;
      out.push({
        views, create_time: 0,
        url: isShort ? `https://youtube.com/shorts/${id}` : `https://youtube.com/watch?v=${id}`,
        media_url: "", ...engage(v),
      });
    }
  }
  return out;
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const SV_KEY = Deno.env.get("SOCIAVAULT_API_KEY");
    if (!SV_KEY) return j({ success: false, error: "Clé SociaVault manquante." }, 500);
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
      { auth: { persistSession: false } });

    const body = await req.json().catch(() => ({}));
    let niches: Record<string, string> = (body.niches && typeof body.niches === "object" && Object.keys(body.niches).length)
      ? body.niches : DEFAULT_NICHES;
    // ÉCONOMIE DE CRÉDITS : par défaut, ROTATION de 8 niches par passage (au fil des
    // semaines, toutes les niches sont couvertes). body.all=true pour tout faire d'un coup.
    if (!body.niches && !body.all) {
      const keys = Object.keys(niches);
      const week = Math.floor(Date.now() / 604800000);
      const start = (week * 8) % keys.length;
      const pick = Array.from({ length: 8 }, (_, i) => keys[(start + i) % keys.length]);
      // TikTok Shop est toujours présent (demande explicite) : on l'ajoute s'il manque.
      if (!pick.includes("tiktok_shop") && niches["tiktok_shop"]) pick[pick.length - 1] = "tiktok_shop";
      niches = Object.fromEntries(pick.map((k) => [k, niches[k]]));
    }
    const maxPerNiche = Math.max(1, Math.min(10, Number(body.max_per_niche) || DEFAULT_MAX_PER_NICHE));

    let queued = 0, searched = 0;
    const report: Record<string, number> = {};
    for (const [rawNiche, query] of Object.entries(niches)) {
      const niche = String(rawNiche).toLowerCase().replace(/[^a-z0-9_]/g, "") || "other";
      const found: { views: number; create_time: number; url: string; media_url: string; platform: string; likes?: number | null; comments?: number | null; shares?: number | null }[] = [];

      // --- TikTok (recherche par mot-clé, tri most-liked) ---
      // Repli progressif : fenêtre 3 mois -> 1 mois -> sans filtre de date, au cas où
      // SociaVault refuse une valeur de date_posted ou renvoie une liste vide.
      let ttArr: any[] = [];
      for (const dp of [DATE_POSTED, "this-month", ""]) {
        try {
          const q = `/tiktok/search/keyword?query=${encodeURIComponent(String(query))}` +
                    `&sort_by=most-liked&region=US` + (dp ? `&date_posted=${dp}` : "");
          const data = await svGet(q, SV_KEY);
          searched++;
          const d = data.data ?? data;
          // la RECHERCHE renvoie la liste sous plusieurs noms selon les cas
          const list = d.aweme_list ?? d.search_item_list ?? d.item_list ?? d.videos ?? d.data ?? {};
          ttArr = Array.isArray(list) ? list : Object.values(list);
          if (!ttArr.length) ttArr = firstArray(d);   // dernier recours : 1er tableau trouvé
          if (ttArr.length) break;
        } catch (e) { console.error("explore tiktok", niche, dp || "no-date", String(e)); }
      }
      for (const it of ttArr as any[]) {
        // chaque résultat de recherche est souvent EMBALLÉ : {aweme_info: {...}} ou {item: {...}}
        const v = it?.aweme_info ?? it?.item ?? it;
        const handle = v?.author?.unique_id ?? v?.author?.uniqueId ?? "";
        if (!v?.aweme_id || !handle) continue;
        found.push({
          views: Number(v?.statistics?.play_count ?? 0) || deepFindViews(v),
          create_time: Number(v?.create_time ?? 0),
          url: `https://www.tiktok.com/@${handle}/video/${v.aweme_id}`,
          media_url: tiktokPlayUrl(v) || deepFindMedia(v), platform: "tiktok", ...engage(v),
        });
      }

      // --- YouTube (Shorts + vidéos ; Gemini lit les liens directement) ---
      try {
        let yt = await youtubeSearch(String(query), SV_KEY);
        searched++;
        if (!yt.length) {              // repli : sans filtre de date
          yt = await youtubeSearch(String(query), SV_KEY, "");
          searched++;
        }
        for (const v of yt) found.push({ ...v, platform: "youtube" });
      } catch (e) { console.error("explore youtube", niche, String(e)); }

      // --- Instagram (posts du hashtag de la niche ; mp4 requis pour l'étude) ---
      try {
        const tag = IG_TAGS[niche] ?? niche;
        const data = await svGet(`/instagram/hashtag?tag=${encodeURIComponent(tag)}&limit=30`, SV_KEY);
        searched++;
        for (const it of firstArray(data.data ?? data)) {
          const v = it?.node ?? it;
          const code = v?.code ?? v?.shortcode ?? v?.short_code ?? "";
          const media = deepFindMedia(v);
          if (!code || !media) continue;   // pas de mp4 -> Gemini ne pourrait pas l'étudier
          found.push({
            views: deepFindViews(v),
            create_time: Number(v?.taken_at ?? v?.taken_at_timestamp ?? v?.timestamp ?? 0),
            url: `https://www.instagram.com/p/${code}/`,
            media_url: media, platform: "instagram", ...engage(v),
          });
        }
      } catch (e) { console.error("explore instagram", niche, String(e)); }

      // --- Facebook (recherche ; best-effort, mp4 requis) ---
      try {
        const data = await svGet(`/facebook/search?query=${encodeURIComponent(String(query))}`, SV_KEY);
        searched++;
        for (const it of firstArray(data.data ?? data)) {
          const media = deepFindMedia(it);
          const urlFb = deepFindFbUrl(it);
          if (!media || !urlFb) continue;
          found.push({
            views: deepFindViews(it), create_time: 0,
            url: urlFb, media_url: media, platform: "facebook", ...engage(it),
          });
        }
      } catch (e) { console.error("explore facebook", niche, String(e)); }

      const rows = found
        .filter((x) => x.url && x.views >= GLOBAL_MIN_VIEWS)
        .sort((a, b) => b.views - a.views)
        .slice(0, maxPerNiche * 3)   // top toutes plateformes confondues (TikTok/YouTube/IG/FB)
        .map((x) => ({
          user_id: null, platform: x.platform, video_url: x.url, media_url: x.media_url || null,
          views: x.views, likes: x.likes ?? null, comments: x.comments ?? null, shares: x.shares ?? null,
          create_time: x.create_time, niche, scope: "global",
        }));

      if (rows.length) {
        await admin.from("winning_videos").upsert(rows, { onConflict: "video_url,scope", ignoreDuplicates: true });
        queued += rows.length;
      }
      report[niche] = rows.length;
    }

    return j({ success: true, searched, queued, report });
  } catch (err) {
    return j({ success: false, error: String(err) }, 500);
  }
});
