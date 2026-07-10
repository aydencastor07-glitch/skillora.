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
};

function j(o: unknown, s = 200) {
  return new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });
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

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const SV_KEY = Deno.env.get("SOCIAVAULT_API_KEY");
    if (!SV_KEY) return j({ success: false, error: "Clé SociaVault manquante." }, 500);
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
      { auth: { persistSession: false } });

    const body = await req.json().catch(() => ({}));
    const niches: Record<string, string> = (body.niches && typeof body.niches === "object" && Object.keys(body.niches).length)
      ? body.niches : DEFAULT_NICHES;
    const maxPerNiche = Math.max(1, Math.min(10, Number(body.max_per_niche) || DEFAULT_MAX_PER_NICHE));

    let queued = 0, searched = 0;
    const report: Record<string, number> = {};
    for (const [rawNiche, query] of Object.entries(niches)) {
      const niche = String(rawNiche).toLowerCase().replace(/[^a-z0-9_]/g, "") || "other";
      let data: any = null;
      try {
        data = await svGet(`/tiktok/search/keyword?query=${encodeURIComponent(String(query))}` +
                           `&sort_by=most-liked&date_posted=${DATE_POSTED}&region=US`, SV_KEY);
        searched++;
      } catch (e) { console.error("explore", niche, String(e)); continue; }
      const d = data.data ?? data;
      const list = d.aweme_list ?? d.videos ?? {};
      const arr = Array.isArray(list) ? list : Object.values(list);

      const rows = (arr as any[])
        .map((v: any) => {
          const handle = v?.author?.unique_id ?? v?.author?.uniqueId ?? "";
          return {
            views: Number(v?.statistics?.play_count ?? 0),
            create_time: Number(v?.create_time ?? 0),
            url: (v?.aweme_id && handle) ? `https://www.tiktok.com/@${handle}/video/${v.aweme_id}` : "",
            media_url: tiktokPlayUrl(v),
          };
        })
        .filter((x) => x.url && x.views >= GLOBAL_MIN_VIEWS)
        .sort((a, b) => b.views - a.views)
        .slice(0, maxPerNiche)
        .map((x) => ({
          user_id: null, platform: "tiktok", video_url: x.url, media_url: x.media_url || null,
          views: x.views, create_time: x.create_time, niche, scope: "global",
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
