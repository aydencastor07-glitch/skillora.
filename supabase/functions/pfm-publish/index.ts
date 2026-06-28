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

    // ── LIMITE DE PUBLICATION MENSUELLE (anti-abus / maîtrise des coûts) ────────────
    // On compte les VIDÉOS distinctes (par media_url) publiées ce mois civil — une même vidéo
    // envoyée sur 3 réseaux = 1 publication. Les échecs ne comptent pas.
    const PUB_MONTH: Record<string, number> = { none: 5, starter: 60, growth: 150, elite: 400 };
    const { data: subRow } = await admin.from("subscriptions").select("plan,status").eq("user_id", userId).maybeSingle();
    const plan = String(subRow?.plan ?? "none").toLowerCase();
    const maxMonth = PUB_MONTH[plan] ?? PUB_MONTH.none;
    const monthStart = new Date(); monthStart.setUTCDate(1); monthStart.setUTCHours(0, 0, 0, 0);
    const { data: monthRows } = await admin.from("scheduled_posts")
      .select("media_url,status").eq("user_id", userId).gte("created_at", monthStart.toISOString());
    const usedVideos = new Set((monthRows || [])
      .filter((r: any) => String(r.status || "") !== "failed" && r.media_url)
      .map((r: any) => r.media_url));
    // Si la vidéo a déjà été publiée ce mois (re-publication même URL), on ne la recompte pas.
    if (!usedVideos.has(mediaUrl) && usedVideos.size >= maxMonth) {
      return json({
        success: false, limit_reached: true, used: usedVideos.size, max: maxMonth, plan,
        error: `Tu as atteint ta limite de ${maxMonth} publications ce mois-ci. Passe à un plan supérieur pour en publier davantage.`,
      }, 200);
    }

    // Comptes Post for Me connectés pour les plateformes choisies.
    // IMPORTANT : TikTok est stocké en base sous "tiktok_business" -> on l'ajoute comme alias,
    // sinon le compte TikTok n'est jamais trouvé et seule l'autre plateforme publie.
    const wanted = new Set(platforms);
    if (wanted.has("tiktok")) wanted.add("tiktok_business");
    if (wanted.has("tiktok_business")) wanted.add("tiktok");
    const { data: conns } = await admin.from("social_connections")
      .select("provider_account_id, platform").eq("user_id", userId).in("platform", [...wanted]);
    const accountIds = [...new Set((conns || []).map((c: any) => c.provider_account_id).filter(Boolean))];
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
