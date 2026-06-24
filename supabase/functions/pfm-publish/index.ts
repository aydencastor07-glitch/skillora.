// SKILLORA — pfm-publish : publie/programme une vidéo sur les réseaux via Post for Me.
// Reçoit { platforms:[..], media_url, caption, scheduled_at? } du front, résout les
// comptes connectés de l'utilisateur (social_connections) et appelle l'API Post for Me.
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

// Même logique d'auth que pfm-sync : clé dédiée, fallback Bearer.
async function pfmFetch(path: string, key: string, init: RequestInit = {}) {
  const base = (init.headers as Record<string, string>) || {};
  let res = await fetch(PFM_BASE + path, { ...init, headers: { "Content-Type": "application/json", "x-post-for-me-api-key": key, ...base } });
  if (res.status === 401 || res.status === 403) {
    res = await fetch(PFM_BASE + path, { ...init, headers: { "Content-Type": "application/json", "Authorization": "Bearer " + key, ...base } });
  }
  return res;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const KEY = Deno.env.get("POSTFORME_API_KEY");
    if (!KEY) return json({ success: false, error: "Publication non configurée (clé Post for Me manquante)." }, 500);

    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
    const jwt = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "").trim();
    const { data: u } = await admin.auth.getUser(jwt);
    const userId = u && u.user ? u.user.id : null;
    if (!userId) return json({ success: false, error: "Non authentifié." }, 401);

    const body = await req.json().catch(() => ({}));
    const platforms: string[] = Array.isArray(body.platforms) ? body.platforms.map((p: string) => String(p).toLowerCase()) : [];
    const mediaUrl: string = (body.media_url || "").toString();
    const caption: string = (body.caption || "").toString();
    const scheduledAt: string | null = body.scheduled_at ? String(body.scheduled_at) : null;

    if (!platforms.length) return json({ success: false, error: "Aucune plateforme sélectionnée." }, 400);
    if (!mediaUrl) return json({ success: false, error: "Vidéo manquante." }, 400);

    // Comptes Post for Me connectés de l'utilisateur pour les plateformes choisies.
    const { data: conns } = await admin.from("social_connections")
      .select("provider_account_id, platform").eq("user_id", userId).in("platform", platforms);
    const accountIds = (conns || []).map((c: any) => c.provider_account_id).filter(Boolean);
    if (!accountIds.length) {
      return json({ success: false, error: "Aucun compte connecté pour ces plateformes. Connecte-les d'abord." }, 400);
    }

    const payload: Record<string, unknown> = {
      caption,
      social_accounts: accountIds,
      media: [{ url: mediaUrl }],
    };
    if (scheduledAt) payload.scheduled_at = scheduledAt;

    const r = await pfmFetch("/v1/social-posts", KEY, { method: "POST", body: JSON.stringify(payload) });
    const d = await r.json().catch(() => ({}));

    if (!r.ok) {
      const err = (d && (d.error || d.message)) || ("Post for Me " + r.status);
      await admin.from("scheduled_posts").insert({
        user_id: userId, caption, media_url: mediaUrl, platforms,
        status: "failed", scheduled_at: scheduledAt, error: JSON.stringify(d).slice(0, 500),
      });
      return json({ success: false, error: err }, 200);
    }

    const postId = (d && (d.id || d.data?.id)) || null;
    await admin.from("scheduled_posts").insert({
      user_id: userId, caption, media_url: mediaUrl, platforms,
      pfm_post_id: postId, status: scheduledAt ? "scheduled" : "publishing", scheduled_at: scheduledAt,
    });

    return json({ success: true, id: postId, scheduled: !!scheduledAt });
  } catch (e) {
    return json({ success: false, error: "Erreur serveur: " + (e?.message ?? String(e)) }, 500);
  }
});
