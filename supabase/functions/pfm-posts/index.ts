// SKILLORA — pfm-posts : liste les vidéos publiées via Skillora (table scheduled_posts) et
// les enrichit avec les URLs PAR PLATEFORME (permaliens Post for Me) -> alimente la cloche 🔔
// et la section « Tes dernières vidéos » de l'accueil, avec un bouton « Voir » par réseau.
// AUCUN crédit SociaVault. On met en cache les permaliens dans scheduled_posts.results pour ne
// jamais redemander Post for Me sur une vidéo déjà publiée.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const PFM_BASE = "https://api.postforme.dev";

function json(o: unknown, s = 200) {
  return new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });
}
async function pfmFetch(path: string, key: string, init: RequestInit = {}) {
  const base = (init.headers as Record<string, string>) || {};
  let res = await fetch(PFM_BASE + path, { ...init, headers: { "Content-Type": "application/json", "x-post-for-me-api-key": key, ...base } });
  if (res.status === 401 || res.status === 403) {
    res = await fetch(PFM_BASE + path, { ...init, headers: { "Content-Type": "application/json", "Authorization": "Bearer " + key, ...base } });
  }
  return res;
}
function plat(s: unknown) {
  return String(s ?? "").toLowerCase().replace("_business", "").trim();
}
// Post for Me renvoie un post avec un tableau de résultats par compte (le nom du champ varie selon
// la version d'API) -> on tente tous les noms connus et on en extrait { platform, url }.
function extractResults(post: any): Array<{ platform: string; url: string | null; status: string | null }> {
  if (!post || typeof post !== "object") return [];
  const arr = post.results ?? post.social_posts ?? post.posts ?? post.platforms ?? post.items ?? post.targets ?? post.data ?? [];
  const list = Array.isArray(arr) ? arr : [];
  const out: Array<{ platform: string; url: string | null; status: string | null }> = [];
  for (const r of list) {
    if (!r || typeof r !== "object") continue;
    const platform = plat(r.platform ?? r.provider ?? r.type ?? r.social_account?.platform ?? r.account?.platform);
    if (!platform) continue;
    const url = r.platform_url ?? r.url ?? r.permalink ?? r.post_url ?? r.link ??
      (r.data && (r.data.url ?? r.data.permalink ?? r.data.platform_url)) ?? null;
    out.push({ platform, url: url ? String(url) : null, status: r.status ? String(r.status) : null });
  }
  return out;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const KEY = Deno.env.get("POSTFORME_API_KEY");
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
    const jwt = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "").trim();
    const { data: u } = await admin.auth.getUser(jwt);
    const userId = u && u.user ? u.user.id : null;
    if (!userId) return json({ success: false, error: "Non authentifié." }, 401);

    const { data: rows } = await admin.from("scheduled_posts")
      .select("id,caption,media_url,platforms,pfm_post_id,status,scheduled_at,created_at,published_at,results")
      .eq("user_id", userId).order("created_at", { ascending: false }).limit(20);

    const posts = [];
    let pfmCalls = 0;
    for (const row of (rows || [])) {
      let results = Array.isArray(row.results) ? row.results : [];
      const finalised = results.length > 0 && results.every((r: any) => r.url);
      // On n'interroge Post for Me que si on n'a pas encore tous les permaliens (max 10 appels / requête).
      if (KEY && row.pfm_post_id && !finalised && pfmCalls < 10) {
        pfmCalls++;
        try {
          const r = await pfmFetch("/v1/social-posts/" + row.pfm_post_id, KEY, { method: "GET" });
          const d = await r.json().catch(() => ({}));
          const fresh = extractResults(d.data ?? d);
          if (fresh.length) {
            results = fresh;
            // Cache si au moins un permalien est disponible (post réellement en ligne).
            if (fresh.some((x) => x.url)) {
              try { await admin.from("scheduled_posts").update({ results: fresh }).eq("id", row.id); } catch (_e) { /* */ }
            }
          }
        } catch (_e) { /* réseau : on garde ce qu'on a */ }
      }
      posts.push({
        id: row.id, caption: row.caption, media_url: row.media_url,
        platforms: row.platforms || [], status: row.status,
        scheduled_at: row.scheduled_at, created_at: row.created_at, published_at: row.published_at,
        results,
      });
    }
    return json({ success: true, posts });
  } catch (e) {
    return json({ success: false, error: "Erreur serveur: " + ((e as Error)?.message ?? String(e)) }, 500);
  }
});
