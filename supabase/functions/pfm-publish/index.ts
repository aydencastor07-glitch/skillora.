// SKILLORA — pfm-publish : publie/programme une vidéo OU un carrousel via Post for Me.
// Reçoit { platforms:[..], media_url | media_urls:[..], video_url?, caption, scheduled_at? }
// du front, résout les comptes connectés (social_connections) et appelle l'API Post for Me.
//
// CARROUSEL : plusieurs images dans media_urls. Chaque réseau a ses propres limites, donc
// on ne peut pas envoyer la même chose à tout le monde — on surcharge par plateforme :
//   • TikTok    : 2 à 35 images + musique ajoutée automatiquement (auto_add_music)
//   • Instagram : 2 à 10 images  (au-delà, on coupe — sinon le post entier échoue)
//   • YouTube   : pas de carrousel du tout -> il lui faut la version diaporama (video_url)
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const MAX_TIKTOK = 35;
const MAX_INSTAGRAM = 10;
// Ces réseaux ne savent pas afficher un carrousel d'images : sans vidéo, on les écarte.
const SANS_CARROUSEL = ["youtube"];

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
    const email = (u.user && u.user.email ? String(u.user.email) : "").toLowerCase();
    const UNLIMITED_EMAILS = ["aydencastor1020@gmail.com"];
    const unlimited = UNLIMITED_EMAILS.indexOf(email) >= 0;

    const body = await req.json().catch(() => ({}));
    const platforms: string[] = Array.isArray(body.platforms) ? body.platforms.map((p: string) => String(p).toLowerCase()) : [];
    // Un post porte UNE vidéo (media_url) ou PLUSIEURS images (media_urls = carrousel).
    // media_url seul reste accepté : tout l'existant continue de marcher sans changement.
    const medias: string[] = [
      ...(Array.isArray(body.media_urls) ? body.media_urls : []),
      ...(body.media_url ? [body.media_url] : []),
    ].map((m: unknown) => String(m || "").trim()).filter(Boolean)
      .filter((m, i, t) => t.indexOf(m) === i)
      .slice(0, MAX_TIKTOK);
    const mediaUrl: string = medias[0] || "";
    const videoUrl: string = (body.video_url || "").toString().trim(); // diaporama, pour YouTube
    const carrousel = medias.length > 1;
    const caption: string = (body.caption || "").toString();
    const scheduledAt: string | null = body.scheduled_at ? String(body.scheduled_at) : null;
    const templateId: string | null = body.template_id ? String(body.template_id) : null;

    if (!platforms.length) return json({ success: false, error: "Aucune plateforme sélectionnée." }, 400);
    // Vidéo, carrousel OU post texte : au moins un média, ou du texte (pour X/Threads/Facebook).
    if (!mediaUrl && !caption.trim()) return json({ success: false, error: "Post vide : ajoute une vidéo/image ou écris un texte." }, 400);
    // Clé de comptage : l'URL média si présente, sinon le texte (un post = une publication).
    const pubKey = mediaUrl || ("text:" + caption.trim());

    // ── LIMITE DE PUBLICATION MENSUELLE (anti-abus / maîtrise des coûts) ────────────
    // On compte les publications DISTINCTES ce mois civil — une même vidéo/post envoyé(e)
    // sur 3 réseaux = 1 publication. Les échecs ne comptent pas.
    const PUB_MONTH: Record<string, number> = { none: 5, starter: 60, growth: 150, elite: 400 };
    const { data: subRow } = await admin.from("subscriptions").select("plan,status").eq("user_id", userId).maybeSingle();
    const plan = String(subRow?.plan ?? "none").toLowerCase();
    const maxMonth = PUB_MONTH[plan] ?? PUB_MONTH.none;
    const monthStart = new Date(); monthStart.setUTCDate(1); monthStart.setUTCHours(0, 0, 0, 0);
    const { data: monthRows } = await admin.from("scheduled_posts")
      .select("media_url,caption,status").eq("user_id", userId).gte("created_at", monthStart.toISOString());
    const usedVideos = new Set((monthRows || [])
      .filter((r: any) => String(r.status || "") !== "failed")
      .map((r: any) => r.media_url || ("text:" + String(r.caption || "").trim())));
    // Si déjà publié ce mois (même média ou même texte), on ne le recompte pas.
    if (!unlimited && !usedVideos.has(pubKey) && usedVideos.size >= maxMonth) {
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
    let comptes = (conns || []).filter((c: any) => c.provider_account_id);

    // Un carrousel sans diaporama ne peut pas partir sur YouTube : on retire ces comptes
    // au lieu de laisser Post for Me refuser TOUT le post (les autres réseaux passeraient à la trappe).
    let ecartes: string[] = [];
    if (carrousel && !videoUrl) {
      const avant = comptes.length;
      ecartes = [...new Set(comptes.filter((c: any) => SANS_CARROUSEL.includes(String(c.platform)))
        .map((c: any) => String(c.platform)))];
      comptes = comptes.filter((c: any) => !SANS_CARROUSEL.includes(String(c.platform)));
      if (!comptes.length && avant) {
        return json({ success: false, error: "YouTube n'accepte pas les carrousels d'images. Ajoute une version vidéo (diaporama) ou choisis TikTok / Instagram." }, 400);
      }
    }

    const accountIds = [...new Set(comptes.map((c: any) => c.provider_account_id))];
    if (!accountIds.length) {
      return json({ success: false, error: "Aucun compte connecté pour ces plateformes. Connecte-les d'abord." }, 400);
    }

    const payload: Record<string, unknown> = {
      caption,
      social_accounts: accountIds,
    };
    if (mediaUrl) payload.media = medias.map((url) => ({ url })); // post texte = pas de média
    if (scheduledAt) payload.scheduled_at = scheduledAt;

    // ── SURCHARGES PAR PLATEFORME ────────────────────────────────────────────────
    // Sans elles, un carrousel de 12 images fait échouer Instagram (max 10) et part
    // sur TikTok en silence, sans musique — donc invisible dans l'algo photo.
    if (carrousel) {
      const conf: Record<string, unknown> = {};
      // TikTok : la musique est ce qui fait exister un post photo. auto_add_music est
      // INCOMPATIBLE avec is_draft : on ne met jamais les deux.
      const tiktok = { auto_add_music: true, media: medias.slice(0, MAX_TIKTOK).map((url) => ({ url })) };
      conf.tiktok = tiktok;
      conf.tiktok_business = tiktok;
      conf.instagram = { media: medias.slice(0, MAX_INSTAGRAM).map((url) => ({ url })) };
      if (videoUrl) conf.youtube = { media: [{ url: videoUrl }] }; // YouTube reçoit le diaporama
      payload.platform_configurations = conf;
    }

    const r = await pfmFetch("/v1/social-posts", KEY, { method: "POST", body: JSON.stringify(payload) });
    const d = await r.json().catch(() => ({}));

    if (!r.ok) {
      const err = (d && (d.error || d.message)) || ("Post for Me " + r.status);
      await admin.from("scheduled_posts").insert({
        user_id: userId, caption, media_url: mediaUrl, media_urls: medias, template_id: templateId, platforms,
        status: "failed", scheduled_at: scheduledAt, error: JSON.stringify(d).slice(0, 500),
      });
      return json({ success: false, error: err }, 200);
    }

    const postId = (d && (d.id || d.data?.id)) || null;
    await admin.from("scheduled_posts").insert({
      user_id: userId, caption, media_url: mediaUrl, media_urls: medias, template_id: templateId, platforms,
      pfm_post_id: postId, status: scheduledAt ? "scheduled" : "publishing", scheduled_at: scheduledAt,
    });

    return json({
      success: true, id: postId, scheduled: !!scheduledAt,
      slides: carrousel ? medias.length : 0,
      ignores: ecartes,   // réseaux volontairement écartés (ex. YouTube sur un carrousel)
    });
  } catch (e) {
    return json({ success: false, error: "Erreur serveur: " + (e?.message ?? String(e)) }, 500);
  }
});
