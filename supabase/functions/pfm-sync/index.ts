// SKILLORA — pfm-sync v16 : synchronise les comptes connectés (Post for Me) dans social_connections.
// ÉCONOMIE CRÉDITS : on ne re-scrape JAMAIS un compte TikTok déjà vérifié (avant, chaque synchro — donc
// chaque connexion d'un AUTRE réseau — re-scrapait TikTok via SociaVault). Facebook/X/LinkedIn = aucun scrape.
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const PFM_BASE = "https://api.postforme.dev";
const SV_BASE = "https://api.sociavault.com/v1/scrape";

function json(o, s) { return new Response(JSON.stringify(o), { status: s || 200, headers: { ...cors, "Content-Type": "application/json" } }); }
async function pfmFetch(path, key, init) {
  init = init || {}; const base = init.headers || {};
  let res = await fetch(PFM_BASE + path, { ...init, headers: { "Content-Type": "application/json", "x-post-for-me-api-key": key, ...base } });
  if (res.status === 401 || res.status === 403) res = await fetch(PFM_BASE + path, { ...init, headers: { "Content-Type": "application/json", "Authorization": "Bearer " + key, ...base } });
  return res;
}
function handleFromUrl(url) { if (!url) return null; var m = String(url).match(/@([A-Za-z0-9._]{2,})/); return m ? m[1] : null; }
function cleanHandle(s) { return (s && /^[A-Za-z0-9._]{2,30}$/.test(s)) ? s : null; }
function norm(s) { return String(s || "").toLowerCase().replace(/[^a-z0-9]/g, ""); }
function namesMatch(a, b) { a = norm(a); b = norm(b); if (a.length < 3 || b.length < 3) return false; return a === b || a.indexOf(b) >= 0 || b.indexOf(a) >= 0; }
async function svNickname(handle, svKey) {
  try {
    const r = await fetch(SV_BASE + "/tiktok/profile?handle=" + encodeURIComponent(handle), { headers: { "X-API-Key": svKey } });
    if (!r.ok) return null;
    const p = await r.json(); const d = p.data ?? p; const u = d.user ?? d.userInfo?.user ?? d.author ?? d;
    return u.nickname ?? u.nick_name ?? u.display_name ?? d.nickname ?? null;
  } catch (_e) { return null; }
}
async function feedCandidates(accountId, key) {
  try {
    const fr = await pfmFetch("/v1/social-account-feeds/" + accountId + "?limit=20", key, { method: "GET" });
    const fd = await fr.json().catch(() => ({}));
    const posts = (fd && (fd.data || fd.posts)) || [];
    const counts = {};
    for (const p of posts) { const h = handleFromUrl(p.platform_url || p.url || ""); if (h) counts[h] = (counts[h] || 0) + 1; }
    return Object.keys(counts).sort((x, y) => counts[y] - counts[x]);
  } catch (_e) { return []; }
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const KEY = Deno.env.get("POSTFORME_API_KEY");
    const SV_KEY = Deno.env.get("SOCIAVAULT_API_KEY");
    if (!KEY) return json({ success: false, error: "Cle Post for Me manquante." }, 500);
    const admin = createClient(Deno.env.get("SUPABASE_URL"), Deno.env.get("SUPABASE_SERVICE_ROLE_KEY"), { auth: { persistSession: false } });
    const jwt = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "").trim();
    const { data: u } = await admin.auth.getUser(jwt);
    const userId = u && u.user ? u.user.id : null;
    if (!userId) return json({ success: false, error: "Non authentifie." }, 401);

    const res = await pfmFetch("/v1/social-accounts?external_id=" + encodeURIComponent(userId), KEY, { method: "GET" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return json({ success: false, error: (data && (data.error || data.message)) || ("Erreur Post for Me (" + res.status + ")"), raw: data }, 200);
    const listRaw = Array.isArray(data) ? data : (data.data || data.accounts || []);
    const list = listRaw.filter((a) => (!a.external_id || a.external_id === userId) && (!a.status || String(a.status).toLowerCase() === "connected"));

    // Comptes déjà en base (avec leur handle vérifié) -> on évite de re-scraper ce qui est déjà connu.
    const { data: existingRows } = await admin.from("social_connections")
      .select("provider_account_id, handle, handle_verified").eq("user_id", userId);
    const existById = {};
    (existingRows || []).forEach((e) => { existById[e.provider_account_id] = e; });

    const rows = [];
    for (const a of list) {
      let handle = null, verified = false;
      if (a.platform === "youtube" || a.platform === "instagram") {
        handle = cleanHandle(a.username) || null; verified = !!handle;
      } else if (a.platform === "tiktok" || a.platform === "tiktok_business") {
        // Déjà vérifié ? -> on réutilise, AUCUN scrape SociaVault.
        const ex = existById[a.id];
        if (ex && ex.handle_verified && ex.handle) {
          handle = ex.handle; verified = true;
        } else {
          // 1ère fois : le @ vient des URLs de TES posts (le feed). On confirme via SociaVault si possible.
          const cands = await feedCandidates(a.id, KEY);
          if (cleanHandle(a.username) && cands.indexOf(a.username) < 0) cands.push(a.username);
          handle = cands[0] || cleanHandle(a.username) || null;
          verified = !!handle;
          if (SV_KEY && cands.length) {
            for (const c of cands.slice(0, 5)) {
              const nick = await svNickname(c, SV_KEY);
              if (nick && namesMatch(nick, a.username)) { handle = c; verified = true; break; }
            }
          }
        }
      } else {
        // Facebook / X / LinkedIn : publication seule, aucune analyse, AUCUN scrape.
        handle = cleanHandle(a.username) || a.username || null; verified = !!handle;
      }
      rows.push({
        user_id: userId, provider_account_id: a.id, platform: a.platform,
        username: a.username || null, display_name: a.username || null,
        handle: handle, handle_verified: verified,
        provider_user_id: a.user_id || null, profile_photo_url: a.profile_photo_url || null,
        metadata: null, external_id: a.external_id || userId,
      });
    }
    if (rows.length) await admin.from("social_connections").upsert(rows, { onConflict: "user_id,provider_account_id" });
    const keep = rows.map((r) => r.provider_account_id);
    for (const e of (existingRows || [])) { if (keep.indexOf(e.provider_account_id) < 0) { try { await admin.from("social_connections").delete().eq("user_id", userId).eq("provider_account_id", e.provider_account_id); } catch (_e) {} } }

    return json({ success: true, accounts: rows, count: rows.length });
  } catch (err) { return json({ success: false, error: String(err) }, 500); }
});
