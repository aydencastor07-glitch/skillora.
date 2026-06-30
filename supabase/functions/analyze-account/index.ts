// SKILLORA — analyze-account v25 : ACTUALISATION INTELLIGENTE. Si le nb de vidéos n'a pas bougé -> on ne
// re-scrape PAS les vidéos et on ne relance PAS l'IA (réutilisation), juste le profil = 1 crédit. Nouvelle
// vidéo -> profil + 1 page vidéos (2 cr), IA réutilisée. « Régénérer » (regen) relance l'IA. + verrou
// anti-doublon, MAX_VIDEOS 30, cache, recent_videos. IA appelée 1× (1ère analyse) au lieu d'à chaque fois.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SV_BASE = "https://api.sociavault.com";
const SV_SCRAPE = SV_BASE + "/v1/scrape";
const MAX_VIDEOS = 30; // 30 récentes = assez pour moyenne + top 3, et 1 page vidéos au lieu de 2 (~25% de crédits en moins)
const CACHE_DAYS = 7;
const AI_MODELS = ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"];
const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const SV_KEY = Deno.env.get("SOCIAVAULT_API_KEY");
    const AI_KEY = Deno.env.get("ANTHROPIC_API_KEY");
    if (!SV_KEY) return j({ error: "Clé SociaVault manquante." }, 500);

    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_ANON_KEY")!,
      { global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } } },
    );
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return j({ error: "Non authentifié." }, 401);

    const body = await req.json().catch(() => ({}));
    const platform = (body.platform ?? "").toLowerCase().trim();
    const username = (body.username ?? "").trim().replace(/^@/, "");
    const owner = body.owner === "competitor" ? "competitor" : "self";
    const force = body.force === true;
    const regen = force && body.regen === true; // « Régénérer ma stratégie » -> relance l'IA (rare). Sinon IA réutilisée.
    if (!platform || !username) return j({ error: "platform et username requis." }, 400);

    const { data: sub } = await supabase.from("subscriptions").select("plan,status").eq("user_id", user.id).maybeSingle();
    const plan = (sub?.plan ?? "none").toLowerCase();
    const UNLIMITED_EMAILS = ["aydencastor1020@gmail.com"];
    const unlimited = UNLIMITED_EMAILS.indexOf(String(user.email || "").toLowerCase()) >= 0;
    if (owner === "competitor" && plan !== "elite" && !unlimited) {
      return j({ error: "upgrade_required", message: "L'analyse des concurrents est réservée au plan Elite." }, 403);
    }

    // Client service-role (pour les vérifs inter-comptes).
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });

    // BLOCAGE ANTI-DOUBLON (AVANT tout scraping = 0 crédit gaspillé) :
    if (owner === "self") {
      try {
        const { data: mineHas } = await admin.from("connected_accounts")
          .select("user_id").eq("platform", platform).ilike("username", username).eq("user_id", user.id).limit(1);
        if (!mineHas || !mineHas.length) {
          const { data: others } = await admin.from("connected_accounts")
            .select("user_id").eq("platform", platform).ilike("username", username)
            .eq("is_active", true).neq("user_id", user.id).limit(1);
          if (others && others.length) {
            return j({ error: "already_connected_elsewhere", message: "Ce compte est déjà connecté sur un autre compte Skillora." }, 200);
          }
        }
      } catch (_e) { /* en cas d'erreur de vérif, on ne bloque pas */ }
    }

    const lastAnalysis = async () => {
      const { data } = await supabase.from("analyses")
        .select("*").eq("user_id", user.id).eq("platform", platform).eq("username", username)
        .order("created_at", { ascending: false }).limit(1).maybeSingle();
      return data;
    };

    // ── RELEVÉ DE COURBE LÉGER (option B) ───────────────────────────────────────
    // Vues fraîches UNIQUEMENT (pas d'IA, pas de profil complet) = ~1 crédit. Déclenché 1×/jour/compte
    // par le front quand l'utilisateur ouvre l'app. C'est ce qui fait monter la courbe "vues gagnées".
    if (body.curveOnly === true && owner === "self") {
      const lockKeyC = `curve|${user.id}|${platform}|${username.toLowerCase()}`;
      let okC = false;
      try { const { data: lk } = await admin.rpc("claim_scrape_lock", { p_key: lockKeyC, p_ttl: 3600 }); okC = lk === true; } catch (_e) { okC = true; }
      if (!okC) return j({ success: true, curve: true, skipped: "locked" }, 200);
      const priorC = (await lastAnalysis())?.summary || null;
      let totalViews = 0;
      try {
        if (platform === "tiktok") {
          const vids = await fetchAllTikTokVideos(username, SV_KEY);
          totalViews = vids.reduce((s, v) => s + (Number(v.views) || 0), 0);
        } else if (platform === "instagram") {
          const pr = await svGet(`/instagram/posts?handle=${encodeURIComponent(username)}&trim=true`, SV_KEY);
          const d = pr.data ?? pr;
          const raw = d.posts ?? d.items ?? d.edges ?? d.media ?? d.data ?? (Array.isArray(d) ? d : []);
          const arr = Array.isArray(raw) ? raw : Object.values(raw ?? {});
          totalViews = arr.map(mapInstagramItem).reduce((s, v) => s + (Number(v.views) || 0), 0);
        } else if (platform === "youtube") {
          let ch;
          try { ch = await svGet(`/youtube/channel?handle=${encodeURIComponent(username)}`, SV_KEY); } catch { /* */ }
          const c = ch?.data ?? ch ?? {};
          totalViews = c.view_count ?? c.viewCount ?? c.stats?.viewCount ?? 0;
        }
      } catch (_e) { return j({ success: true, curve: true, skipped: "scrape_err" }, 200); }
      if (totalViews > 0) {
        const today = new Date().toISOString().slice(0, 10);
        const snap = { user_id: user.id, platform, username, total_views: totalViews,
          followers: priorC?.audience ?? 0, total_videos: priorC?.total_published ?? 0, total_likes: priorC?.profile?.total_likes ?? 0, snapshot_date: today };
        const { data: ex } = await supabase.from("account_snapshots")
          .select("id").eq("user_id", user.id).eq("platform", platform).ilike("username", username).eq("snapshot_date", today).maybeSingle();
        if (ex) await supabase.from("account_snapshots").update(snap).eq("id", ex.id);
        else await supabase.from("account_snapshots").insert(snap);
      }
      return j({ success: true, curve: true, total_views: totalViews }, 200);
    }

    const since = new Date(Date.now() - CACHE_DAYS * 24 * 3600 * 1000).toISOString();
    const { data: recent } = await supabase.from("analyses")
      .select("*").eq("user_id", user.id).eq("platform", platform).eq("username", username)
      .gte("created_at", since).order("created_at", { ascending: false }).limit(1).maybeSingle();
    // CACHE : toute analyse récente AVEC des vidéos est réutilisée (même si l'IA n'a pas mis de niche).
    // -> évite de re-scraper en boucle quand l'IA échoue. 0 crédit gaspillé.
    if (recent && !force && (
          (recent.summary?.video_count ?? 0) > 0 ||
          recent.summary?.profile_only === true   // X/Facebook/Threads = stats de profil -> réutilisé (0 crédit), MÊME si 0 abonné / 0 vue (sinon on re-scrape en boucle)
       )) {
      return j({ success: true, analysis: recent, cached: true }, 200);
    }

    // VERROU ANTI-SCRAPE CONCURRENT : un seul scrape par compte à la fois.
    // Si 3 appels analyze-account partent en parallèle, UN SEUL scrape ; les autres renvoient la dernière analyse.
    // -> fini le profil scrapé 2-3x pour une seule action = fini les crédits gaspillés.
    const lockKey = `${user.id}|${platform}|${username.toLowerCase()}`;
    let gotLock = false;
    try { const { data: lk } = await admin.rpc("claim_scrape_lock", { p_key: lockKey, p_ttl: 150 }); gotLock = lk === true; }
    catch (_e) { gotLock = true; /* si le RPC échoue, on ne bloque pas l'analyse */ }
    if (!gotLock) {
      const prev = await lastAnalysis();
      if (prev) return j({ success: true, analysis: prev, cached: true, inflight: true }, 200);
      return j({ success: false, error: "in_progress", message: "Analyse déjà en cours pour ce compte, réessaie dans un instant." }, 200);
    }

    try {
    // Analyse précédente -> actualisation intelligente : pas de re-scrape des vidéos s'il n'y en a pas de
    // nouvelle, et pas de relance de l'IA (on réutilise la stratégie déjà calculée).
    const priorSummary = (recent && recent.summary) ? recent.summary : ((await lastAnalysis())?.summary || null);
    let result;
    try {
      if (platform === "tiktok") result = await analyzeTikTok(username, SV_KEY, AI_KEY, owner, priorSummary, regen);
      else if (platform === "youtube") result = await analyzeYouTube(username, SV_KEY, AI_KEY, owner, priorSummary, regen);
      else if (platform === "instagram") result = await analyzeInstagram(username, SV_KEY, AI_KEY, owner, priorSummary, regen);
      else if (platform === "twitter" || platform === "x") result = await analyzeTwitter(username, SV_KEY);
      else if (platform === "facebook") result = await analyzeFacebook(username, SV_KEY);
      else if (platform === "threads") result = await analyzeThreads(username, SV_KEY);
      else return j({ error: `${platform} sera bientôt disponible.` }, 501);
    } catch (scrapeErr) {
      const msg = String(scrapeErr?.message ?? scrapeErr);
      console.error("SCRAPE_FAIL", platform, username, msg);
      const prev = await lastAnalysis();
      if (prev) return j({ success: true, analysis: prev, cached: true, stale: true, scrape_error: msg }, 200);
      const quota = /\b(402|429)\b/.test(msg);
      return j({ error: "scrape_unavailable",
        message: quota
          ? "Le service d'analyse a atteint sa limite pour le moment. Réessaie dans quelques minutes."
          : "Le service d'analyse est momentanément indisponible. Réessaie dans un instant.",
        detail: msg }, 200);
    }

    const _fetched = result?.summary?.video_count ?? 0;
    const _published = result?.summary?.total_published ?? 0;
    if (_fetched === 0 && _published > 0) {
      const prev = await lastAnalysis();
      if (prev && (prev.summary?.video_count ?? 0) > 0) {
        return j({ success: true, analysis: prev, cached: true, stale: true }, 200);
      }
    }

    const { data: account } = await supabase.from("connected_accounts")
      .upsert({ user_id: user.id, platform, username, method: "scrape", is_active: owner === "self" },
        { onConflict: "user_id,platform,username" }).select().maybeSingle();

    const { data: analysis, error } = await supabase.from("analyses")
      .insert({ user_id: user.id, account_id: account?.id ?? null, platform, username,
        raw_data: result.rawData, summary: result.summary }).select().single();
    if (error) return j({ error: "Enregistrement: " + error.message }, 500);

    // ── RELEVÉ DE COURBE : on met à jour le point du JOUR avec les chiffres FRAIS de cette analyse.
    // (Avant, une actualisation mettait à jour l'analyse mais PAS le relevé -> la courbe restait plate.)
    if (owner === "self") {
      try {
        const today = new Date().toISOString().slice(0, 10);
        const snap = {
          user_id: user.id, platform, username,
          total_views: result.summary?.total_views ?? 0,
          followers: result.summary?.audience ?? 0,
          total_videos: result.summary?.total_published ?? result.summary?.video_count ?? 0,
          total_likes: result.summary?.profile?.total_likes ?? 0,
          snapshot_date: today,
        };
        const { data: ex } = await supabase.from("account_snapshots")
          .select("id").eq("user_id", user.id).eq("platform", platform).ilike("username", username).eq("snapshot_date", today).maybeSingle();
        if (ex) await supabase.from("account_snapshots").update(snap).eq("id", ex.id);
        else await supabase.from("account_snapshots").insert(snap);
      } catch (_e) { /* la courbe se mettra à jour à la prochaine analyse */ }
    }

    return j({ success: true, analysis }, 200);
    } finally {
      try { await admin.from("scrape_locks").delete().eq("lock_key", lockKey); } catch (_e) { /* libère le verrou */ }
    }
  } catch (e) {
    return j({ error: "Erreur serveur: " + (e?.message ?? String(e)) }, 500);
  }
});

function j(o, s = 200) {
  return new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });
}
async function svGet(path, key) {
  const r = await fetch(SV_SCRAPE + path, { headers: { "X-API-Key": key } });
  if (!r.ok) {
    let b = "";
    try { b = (await r.text()).slice(0, 150); } catch { /* ignore */ }
    throw new Error(`SociaVault ${r.status} ${b}`);
  }
  return r.json();
}
async function svTranscript(url, key) {
  try {
    const r = await fetch(`${SV_BASE}/tiktok/transcript?url=${encodeURIComponent(url)}`, { headers: { "X-API-Key": key } });
    if (!r.ok) return "";
    const d = await r.json();
    const raw = d.transcript ?? d.data?.transcript ?? "";
    return String(raw).replace(/WEBVTT/g, "").replace(/[\d:.]+ --> [\d:.]+/g, "").replace(/\n{2,}/g, " ").trim();
  } catch { return ""; }
}

function deepFindAvatar(obj, depth = 0) {
  if (!obj || depth > 5) return "";
  if (typeof obj === "string") {
    if (/^https?:\/\/.*\.(jpe?g|png|webp|heic)/i.test(obj) && /(avatar|profile|user|tiktokcdn|cdninstagram|p16|p77|p19)/i.test(obj)) return obj;
    return "";
  }
  if (Array.isArray(obj)) {
    for (const it of obj) { const f = deepFindAvatar(it, depth + 1); if (f) return f; }
    return "";
  }
  if (typeof obj === "object") {
    const keys = Object.keys(obj).sort((a, b) => {
      const av = /avatar|profile_pic|profilePic|pfp/i;
      return (av.test(b) ? 1 : 0) - (av.test(a) ? 1 : 0);
    });
    for (const k of keys) {
      if (obj[k] && obj[k].url_list) {
        const u = obj[k].url_list;
        const first = Array.isArray(u) ? u[0] : (u["0"] ?? Object.values(u)[0]);
        if (typeof first === "string" && first.startsWith("http")) return first;
      }
      const f = deepFindAvatar(obj[k], depth + 1);
      if (f) return f;
    }
  }
  return "";
}

function mapTikTokVideo(v, handle) {
  const st = v.statistics ?? {};
  const cover = v.video?.dynamic_cover?.url_list?.["0"] ?? v.video?.origin_cover?.url_list?.["0"] ?? "";
  const tags = v.text_extra ? Object.values(v.text_extra).map((t) => t.hashtag_name).filter(Boolean) : [];
  const durMs = v.video?.duration ?? v.duration ?? 0;
  const createTime = v.create_time ?? 0;
  return {
    id: v.aweme_id ?? "", description: v.desc ?? "",
    views: st.play_count ?? 0, likes: st.digg_count ?? 0,
    comments: st.comment_count ?? 0, shares: st.share_count ?? 0,
    saves: st.collect_count ?? 0,
    duration_s: durMs > 1000 ? Math.round(durMs / 1000) : Math.round(durMs),
    create_time: createTime,
    url: v.aweme_id ? `https://www.tiktok.com/@${handle}/video/${v.aweme_id}` : "",
    cover, hashtags: tags,
  };
}
async function fetchAllTikTokVideos(handle, key) {
  let all = [];
  let cursor = null;
  for (let page = 0; page < Math.ceil(MAX_VIDEOS / 30); page++) {
    const q = `/tiktok/videos?handle=${encodeURIComponent(handle)}&count=30` + (cursor ? `&max_cursor=${cursor}` : "");
    let resp = null;
    const tries = page === 0 ? 3 : 1;
    for (let t = 0; t < tries; t++) {
      try { resp = await svGet(q, key); break; }
      catch (e) { if (t < tries - 1) await new Promise((r) => setTimeout(r, 700 * (t + 1))); else if (page === 0) throw e; }
    }
    if (!resp) break;
    const data = resp.data ?? resp;
    const list = data.aweme_list ?? {};
    const arr = Array.isArray(list) ? list : Object.values(list);
    if (!arr.length) break;
    all = all.concat(arr.map((v) => mapTikTokVideo(v, handle)));
    if (!data.has_more || all.length >= MAX_VIDEOS) break;
    cursor = data.max_cursor;
    if (!cursor) break;
  }
  return all.filter((v) => typeof v.views === "number");
}

async function analyzeTikTok(handle, key, aiKey, owner, prior, regen) {
  const profile = await svGet(`/tiktok/profile?handle=${encodeURIComponent(handle)}`, key);
  const p = profile.data ?? profile;
  const u = p.user ?? p.userInfo?.user ?? p.author ?? p;
  const st = p.stats ?? p.statistics ?? p.userInfo?.stats ?? u.stats ?? {};
  const followers = u.follower_count ?? st.followerCount ?? st.follower_count ?? p.follower_count ?? 0;
  const totalLikes = u.total_favorited ?? u.heart_count ?? u.heartCount ?? st.heartCount ?? st.heart ?? st.diggCount ?? p.total_favorited ?? p.heart_count ?? 0;
  const following = u.following_count ?? st.followingCount ?? p.following_count ?? 0;
  const totalPublished = u.aweme_count ?? st.videoCount ?? p.aweme_count ?? p.video_count ?? 0;
  let avatar = deepFindAvatar(p);
  const nickname = u.nickname ?? u.nick_name ?? u.display_name ?? u.displayName ?? p.nickname ?? handle;
  const uniqueId = u.unique_id ?? u.uniqueId ?? u.username ?? handle;
  const bio = u.signature ?? u.bio ?? p.signature ?? "";

  // ACTUALISATION INTELLIGENTE : si le nb de vidéos n'a pas bougé, on NE re-scrape PAS les vidéos ni l'IA
  // -> on réutilise l'analyse précédente en rafraîchissant juste les chiffres du profil. = 1 crédit.
  if (prior && !regen && prior.video_count > 0 && (prior.total_published ?? 0) === totalPublished) {
    const summary = JSON.parse(JSON.stringify(prior));
    summary.audience = followers; summary.total_published = totalPublished;
    summary.profile = { avatar: avatar || prior.profile?.avatar || "", nickname, handle: uniqueId, following, total_likes: totalLikes };
    return { rawData: { followers, total_published: totalPublished, fetched: prior.video_count, reused: true }, summary };
  }

  let videos = [];
  try { videos = await fetchAllTikTokVideos(handle, key); } catch (e) { console.error("VIDEOS_FAIL", handle, String(e?.message ?? e)); }
  if (!videos.length && totalPublished > 0) {
    for (let t = 0; t < 2 && !videos.length; t++) {
      await new Promise((r) => setTimeout(r, 1200));
      try { videos = await fetchAllTikTokVideos(handle, key); } catch { /* on garde [] */ }
    }
  }
  const top = [...videos].sort((a, b) => b.views - a.views).slice(0, 3);
  // Transcript DÉSACTIVÉ pour économiser 1 crédit/analyse (le type est déduit sans appel payant).
  top.forEach((v) => { v.video_type = "visual"; });

  const aiKeyUse = (regen || !(prior?.insights?.niche)) ? aiKey : null; // IA seulement à la 1ère analyse ou « Régénérer »
  const summary = await buildSmartSummary(followers, videos, top, "tiktok", aiKeyUse, owner, totalPublished, bio, prior?.insights);
  summary.profile = { avatar, nickname, handle: uniqueId, following, total_likes: totalLikes };
  const dbg = { keys: Object.keys(p).slice(0, 30), user_keys: u !== p ? Object.keys(u).slice(0, 30) : [], avatar_found: !!avatar, ai_error: summary._ai_error || null };
  return { rawData: { followers, total_published: totalPublished, fetched: videos.length, profile_debug: dbg }, summary };
}

async function analyzeYouTube(handle, key, aiKey, owner, prior, regen) {
  let ch;
  for (const q of [`/youtube/channel?handle=${encodeURIComponent(handle)}`,
                   `/youtube/channel?channelId=${encodeURIComponent(handle)}`,
                   `/youtube/channel?username=${encodeURIComponent(handle)}`]) {
    try { ch = await svGet(q, key); if (ch) break; } catch { /* next */ }
  }
  const c = ch?.data ?? ch ?? {};
  const subs = c.subscriber_count ?? c.subscriberCount ?? c.stats?.subscriberCount ?? 0;
  const totalPublished = c.video_count ?? c.videoCount ?? c.stats?.videoCount ?? 0;
  let avatar = deepFindAvatar(c);
  const nickname = c.title ?? c.name ?? c.author ?? handle;
  const bio = c.description ?? "";

  // Actualisation intelligente : pas de nouvelle vidéo -> on réutilise l'analyse précédente (1 crédit).
  if (prior && !regen && prior.video_count > 0 && (prior.total_published ?? 0) === totalPublished) {
    const summary = JSON.parse(JSON.stringify(prior));
    summary.audience = subs; summary.total_published = totalPublished;
    summary.profile = { avatar: avatar || prior.profile?.avatar || "", nickname, handle, following: 0, total_likes: 0 };
    return { rawData: { subs, total_published: totalPublished, fetched: prior.video_count, reused: true }, summary };
  }

  let vlist = c.videos ?? c.data?.videos ?? [];
  if (!vlist || (Array.isArray(vlist) && !vlist.length)) {
    for (const q of [`/youtube/videos?handle=${encodeURIComponent(handle)}&count=50`,
                     `/youtube/channel-videos?handle=${encodeURIComponent(handle)}`]) {
      try { const vr = await svGet(q, key); vlist = vr.data?.videos ?? vr.videos ?? vr.data ?? []; if (vlist && (Array.isArray(vlist) ? vlist.length : Object.keys(vlist).length)) break; } catch { /* next */ }
    }
  }
  const arr = Array.isArray(vlist) ? vlist : Object.values(vlist ?? {});
  const videos = arr.map((v) => ({
    id: v.video_id ?? v.id ?? "", description: v.title ?? v.description ?? "",
    views: v.view_count ?? v.views ?? v.viewCount ?? v.statistics?.viewCount ?? 0,
    likes: v.like_count ?? v.likes ?? v.statistics?.likeCount ?? 0,
    comments: v.comment_count ?? v.comments ?? v.statistics?.commentCount ?? 0,
    shares: 0, saves: 0, duration_s: 0, create_time: v.published_at ?? 0,
    url: v.url ?? (v.video_id ? `https://youtube.com/watch?v=${v.video_id}` : ""),
    cover: v.thumbnail ?? v.thumbnails?.high?.url ?? "", hashtags: [],
  })).filter((v) => typeof v.views === "number");

  const top = [...videos].sort((a, b) => b.views - a.views).slice(0, 3);
  top.forEach((v) => { v.video_type = "visual"; });
  const aiKeyUse = (regen || !(prior?.insights?.niche)) ? aiKey : null;
  const summary = await buildSmartSummary(subs, videos, top, "youtube", aiKeyUse, owner, totalPublished, bio, prior?.insights);
  summary.profile = { avatar, nickname, handle, following: 0, total_likes: 0 };
  return { rawData: { subs, total_published: totalPublished, fetched: videos.length, profile_debug: { ai_error: summary._ai_error || null } }, summary };
}

// ── INSTAGRAM ──────────────────────────────────────────────────────────────
// Extraction défensive : SociaVault peut renvoyer la forme IG native (edge_*) OU une forme aplatie.
function igNum(...xs) { for (const x of xs) { if (typeof x === "number") return x; if (x && typeof x.count === "number") return x.count; } return 0; }
function mapInstagramItem(it) {
  const v = it.node ?? it;
  let cap = v.caption?.text ?? v.caption ?? v.edge_media_to_caption?.edges?.[0]?.node?.text ?? v.description ?? "";
  if (cap && typeof cap !== "string") cap = cap.text ?? "";
  const cover = v.image_versions2?.candidates?.[0]?.url ?? v.thumbnail_url ?? v.display_url ?? v.thumbnail_src ?? v.image_url ?? v.cover ?? deepFindAvatar(v);
  const shortcode = v.code ?? v.shortcode ?? v.short_code ?? "";
  const dur = v.video_duration ?? v.video_duration_s ?? 0;
  const tags = (typeof cap === "string") ? (cap.match(/#[\p{L}0-9_]+/gu) || []).map((t) => t.slice(1)) : [];
  return {
    id: v.id ?? v.pk ?? shortcode ?? "",
    description: typeof cap === "string" ? cap : "",
    views: igNum(v.play_count, v.view_count, v.video_view_count, v.ig_play_count, v.views),
    likes: igNum(v.like_count, v.edge_liked_by, v.edge_media_preview_like, v.likes),
    comments: igNum(v.comment_count, v.edge_media_to_comment, v.comments),
    shares: igNum(v.share_count, v.reshare_count),
    saves: igNum(v.save_count),
    duration_s: dur > 1000 ? Math.round(dur / 1000) : Math.round(dur),
    create_time: v.taken_at ?? v.taken_at_timestamp ?? v.timestamp ?? 0,
    url: shortcode ? `https://www.instagram.com/p/${shortcode}/` : "",
    cover: cover ?? "", hashtags: tags,
  };
}
async function analyzeInstagram(handle, key, aiKey, owner, prior, regen) {
  const profile = await svGet(`/instagram/profile?handle=${encodeURIComponent(handle)}`, key);
  const p = profile.data ?? profile;
  const u = p.user ?? p.userInfo?.user ?? p.profile ?? p.data?.user ?? p;
  const followers = igNum(u.follower_count, u.edge_followed_by, u.followers, u.followers_count, p.follower_count, p.followers);
  const following = igNum(u.following_count, u.edge_follow, u.following);
  const totalPublished = igNum(u.media_count, u.edge_owner_to_timeline_media, u.posts_count, u.post_count, p.media_count);
  let avatar = u.profile_pic_url_hd ?? u.profile_pic_url ?? u.profilePicUrl ?? u.avatar ?? deepFindAvatar(p);
  const nickname = u.full_name ?? u.fullName ?? u.nickname ?? u.name ?? handle;
  const uniqueId = u.username ?? u.handle ?? handle;
  const bio = u.biography ?? u.bio ?? "";

  // Actualisation intelligente : pas de nouveau post -> on réutilise l'analyse précédente (1 crédit).
  if (prior && !regen && prior.video_count > 0 && (prior.total_published ?? 0) === totalPublished) {
    const summary = JSON.parse(JSON.stringify(prior));
    summary.audience = followers; summary.total_published = totalPublished;
    summary.profile = { avatar: avatar || prior.profile?.avatar || "", nickname, handle: uniqueId, following, total_likes: prior.profile?.total_likes ?? 0 };
    return { rawData: { followers, total_published: totalPublished, fetched: prior.video_count, reused: true }, summary };
  }

  let raw = [];
  try {
    const pr = await svGet(`/instagram/posts?handle=${encodeURIComponent(handle)}&trim=true`, key);
    const d = pr.data ?? pr;
    raw = d.posts ?? d.items ?? d.edges ?? d.media ?? d.data ?? (Array.isArray(d) ? d : []);
  } catch (e) { console.error("IG_POSTS_FAIL", handle, String(e?.message ?? e)); }
  const arr = Array.isArray(raw) ? raw : Object.values(raw ?? {});
  const videos = arr.map(mapInstagramItem).filter((v) => typeof v.views === "number");

  const top = [...videos].sort((a, b) => b.views - a.views).slice(0, 3);
  top.forEach((v) => { v.video_type = "visual"; });

  const aiKeyUse = (regen || !(prior?.insights?.niche)) ? aiKey : null;
  const summary = await buildSmartSummary(followers, videos, top, "instagram", aiKeyUse, owner, totalPublished, bio, prior?.insights);
  // IG n'expose pas le total de likes du profil -> on somme les likes des posts récupérés (approx récente).
  const totalLikes = videos.reduce((sm, v) => sm + (Number(v.likes) || 0), 0);
  summary.profile = { avatar, nickname, handle: uniqueId, following, total_likes: totalLikes };
  return { rawData: { followers, total_published: totalPublished, fetched: videos.length, profile_debug: { ai_error: summary._ai_error || null } }, summary };
}

// ── STATS DE PROFIL (X / Facebook / LinkedIn) ─────────────────────────────────
// SociaVault expose le PROFIL de ces réseaux (abonnés + métadonnées) — 1 crédit, pas d'IA, pas de vidéos.
// On renvoie le MÊME format `summary` que les autres, avec profile_only=true (l'app affiche une carte adaptée).
function svNum(...vals) { for (const v of vals) { const n = Number(v); if (Number.isFinite(n) && n > 0) return n; } return 0; }
function socialSummary(o) {
  return {
    audience: o.audience || 0,
    video_count: 0, total_published: o.totalPublished || 0,
    avg_views: 0, total_views: 0, avg_engagement_rate: 0, total_shares: 0, total_saves: 0,
    best_videos: [], worst_videos: [], recent_videos: [], top_videos: [],
    owner: "self", profile_only: true, platform: o.platform, social_stats: o.stats || [], bio: o.bio || "",
    profile: { avatar: o.avatar || "", nickname: o.nickname || o.handle, handle: o.handle, following: o.following || 0, total_likes: o.totalLikes || 0 },
    insights: { verdict: "", niche: "", content_type: "", production_kind: "", needs_script: false, patterns: [], equivalents: [], formula: null, why: [], blueprints: [], scorecard: null },
  };
}
async function analyzeTwitter(handle, key) {
  const cleanH = String(handle).replace(/^@/, "");
  const r = await svGet(`/twitter/profile?handle=${encodeURIComponent(cleanH)}`, key);
  const d = r.data ?? r;
  const u = d.user ?? d.result ?? d;
  const legacy = u.legacy ?? d.legacy ?? {};
  const core = u.core ?? d.core ?? {};
  const followers = svNum(legacy.followers_count, u.followers_count, d.followers_count, d.followers);
  const following = svNum(legacy.friends_count, u.friends_count);
  const tweetsCount = svNum(legacy.statuses_count, u.statuses_count);
  const nickname = core.name ?? legacy.name ?? u.name ?? handle;
  const screen = core.screen_name ?? legacy.screen_name ?? u.screen_name ?? cleanH;
  const bio = legacy.description ?? u.description ?? "";
  const avatar = legacy.profile_image_url_https ?? u.profile_image_url_https ?? d.profile_image_url ?? deepFindAvatar(d);

  // 2e appel (~1 crédit) : les tweets, pour les VUES (tweets[].views.count) + likes REÇUS.
  // Twitter public expose ~100 tweets les plus POPULAIRES -> la somme des vues ≈ l'essentiel des vues du compte.
  let totalViews = 0, likesRecv = 0, fetched = 0;
  try {
    const tr = await svGet(`/twitter/user-tweets?handle=${encodeURIComponent(cleanH)}`, key);
    const td = tr.data ?? tr;
    const tw = td.tweets ?? td.data?.tweets ?? {};
    const arr = Array.isArray(tw) ? tw : Object.values(tw ?? {});
    for (const t of arr) {
      if (!t || typeof t !== "object") continue;
      const tl = t.legacy ?? t;
      totalViews += svNum(t.views?.count, t.views, tl.views, tl.view_count);
      likesRecv += svNum(tl.favorite_count, tl.favourite_count);
      fetched++;
    }
  } catch (_e) { /* l'appel tweets a échoué -> on garde au moins le profil (abonnés) */ }

  const stats = [{ label: "Abonnés", value: followers }];
  if (totalViews > 0) stats.push({ label: "Vues", value: totalViews });
  stats.push({ label: "Tweets", value: tweetsCount || fetched });
  if (totalViews > 0 && likesRecv > 0) stats.push({ label: "J'aime", value: likesRecv });
  const summary = socialSummary({ platform: "twitter", audience: followers, totalPublished: tweetsCount || fetched, nickname, handle: screen, avatar, following, totalLikes: likesRecv, bio, stats });
  // Stats EXISTANTES affichées dès la connexion (la courbe, elle, monte avec les vues futures).
  summary.total_views = totalViews;
  summary.avg_views = fetched > 0 ? Math.round(totalViews / fetched) : 0;
  summary.avg_engagement_rate = totalViews > 0 ? Math.round((likesRecv / totalViews) * 1000) / 10 : 0;
  return { rawData: { followers, total_published: tweetsCount, total_views: totalViews, fetched, profile_only: true }, summary };
}
async function analyzeThreads(handle, key) {
  const cleanH = String(handle).replace(/^@/, "");
  const r = await svGet(`/threads/profile?handle=${encodeURIComponent(cleanH)}`, key);
  const d = r.data ?? r;
  const dd = d.data ?? d;
  const followers = svNum(dd.follower_count, dd.followers, dd.followers_count);
  const nickname = dd.full_name ?? dd.username ?? handle;
  const screen = dd.username ?? cleanH;
  const avatar = dd.profile_pic_url ?? dd.profile_pic ?? deepFindAvatar(d);
  const bio = dd.biography ?? dd.bio ?? "";

  // Posts (~20-30, ~1 crédit) -> J'aime (engagement) + vues SI la liste les expose.
  let totalViews = 0, totalLikes = 0, postCount = 0;
  try {
    const pr = await svGet(`/threads/user-posts?handle=${encodeURIComponent(cleanH)}`, key);
    const pd = pr.data ?? pr;
    const posts = pd.posts ?? pd.data?.posts ?? {};
    const arr = Array.isArray(posts) ? posts : Object.values(posts ?? {});
    for (const p of arr) {
      if (!p || typeof p !== "object") continue;
      totalViews += svNum(p.view_counts, p.view_count, p.views);
      totalLikes += svNum(p.like_count, p.likes);
      postCount++;
    }
  } catch (_e) { /* garde au moins le profil (abonnés) */ }

  const stats = [{ label: "Abonnés", value: followers }];
  if (totalViews > 0) stats.push({ label: "Vues", value: totalViews });
  if (postCount > 0) stats.push({ label: "Posts", value: postCount });
  if (totalLikes > 0) stats.push({ label: "J'aime", value: totalLikes });
  const summary = socialSummary({ platform: "threads", audience: followers, totalPublished: postCount, nickname, handle: screen, avatar, totalLikes, bio, stats });
  summary.total_views = totalViews;
  summary.avg_views = postCount > 0 ? Math.round(totalViews / postCount) : 0;
  summary.avg_engagement_rate = totalViews > 0 ? Math.round((totalLikes / totalViews) * 1000) / 10 : 0;
  return { rawData: { followers, total_views: totalViews, posts: postCount, profile_only: true }, summary };
}
async function analyzeFacebook(handle, key) {
  const isUrl = /^https?:\/\//i.test(handle);
  const url = isUrl ? handle : `https://www.facebook.com/${String(handle).replace(/^@/, "")}`;
  const r = await svGet(`/facebook/profile?url=${encodeURIComponent(url)}`, key);
  const d = r.data ?? r;
  const dd = d.data ?? d;
  const followers = svNum(dd.followers, dd.followers_count, dd.fan_count, dd.followerCount, dd.likes, dd.likes_count);
  const nickname = dd.name ?? handle;
  const avatar = dd.profilePicLarge ?? dd.profile_pic_url ?? dd.profilePic ?? dd.image ?? deepFindAvatar(d);
  const pageLikes = svNum(dd.likes, dd.likes_count);

  // Reels (10 max, ~1 crédit) -> VUES : reels[].view_count.
  let totalViews = 0, reelCount = 0;
  try {
    const rr = await svGet(`/facebook/profile/reels?url=${encodeURIComponent(url)}`, key);
    const rd = rr.data ?? rr;
    const reels = rd.reels ?? rd.data?.reels ?? [];
    const arr = Array.isArray(reels) ? reels : Object.values(reels ?? {});
    for (const x of arr) {
      if (!x || typeof x !== "object") continue;
      totalViews += svNum(x.view_count, x.views, x.viewCount);
      reelCount++;
    }
  } catch (_e) { /* reels indispo -> on garde au moins le profil (abonnés) */ }

  const stats = [{ label: "Abonnés", value: followers }];
  if (totalViews > 0) stats.push({ label: "Vues", value: totalViews });
  if (reelCount > 0) stats.push({ label: "Reels", value: reelCount });
  else if (pageLikes && pageLikes !== followers) stats.push({ label: "J'aime la Page", value: pageLikes });
  const summary = socialSummary({ platform: "facebook", audience: followers, totalPublished: reelCount, nickname, handle, avatar, totalLikes: pageLikes, stats });
  summary.total_views = totalViews;
  summary.avg_views = reelCount > 0 ? Math.round(totalViews / reelCount) : 0;
  return { rawData: { followers, total_views: totalViews, reels: reelCount, profile_only: true }, summary };
}
async function analyzeLinkedIn(handle, key) {
  const isUrl = /^https?:\/\//i.test(handle);
  const url = isUrl ? handle : `https://www.linkedin.com/in/${String(handle).replace(/^@/, "")}/`;
  const r = await svGet(`/linkedin/profile?url=${encodeURIComponent(url)}`, key);
  const d = r.data ?? r;
  const dd = d.data ?? d;
  const followers = svNum(dd.followers, dd.followers_count, dd.followerCount);
  const nickname = dd.name ?? handle;
  const avatar = dd.image ?? dd.profilePic ?? dd.profile_pic_url ?? deepFindAvatar(d);
  const rp = dd.recentPosts;
  const postCount = Array.isArray(rp) ? rp.length : (rp && typeof rp === "object" ? Object.keys(rp).length : 0);
  const stats = [{ label: "Abonnés", value: followers }];
  if (postCount) stats.push({ label: "Posts récents", value: postCount });
  return { rawData: { followers, profile_only: true }, summary: socialSummary({ platform: "linkedin", audience: followers, totalPublished: postCount, nickname, handle, avatar, bio: dd.about || "", stats }) };
}

function guessNiche(videos, bio) {
  const text = (bio + " " + videos.map((v) => (v.description || "") + " " + (v.hashtags || []).join(" ")).join(" ")).toLowerCase();
  const map = [
    ["Football", ["football", "soccer", "messi", "ronaldo", "neymar", "mbappe", "foot", "premierleague", "championsleague", "laliga", "fifa"]],
    ["Basketball", ["basketball", "basket", "nba", "lebron", "curry", "jordan", "dunk", "hoops"]],
    ["MMA & combat", ["mma", "ufc", "boxing", "boxe", "knockout", "fighter", "jiujitsu"]],
    ["Tennis", ["tennis", "federer", "nadal", "djokovic", "atp", "wimbledon"]],
    ["Sport auto (F1)", ["formula1", "f1", "verstappen", "hamilton", "racing", "grandprix"]],
    ["Histoires & storytime", ["storytime", "story", "histoire", "raconte", "pov", "truestory"]],
    ["Horreur & mystère", ["horror", "horreur", "scary", "creepy", "mystère", "mystery", "paranormal", "ghost", "unsolved"]],
    ["Beauté & mode", ["makeup", "beauty", "mode", "fashion", "outfit", "skincare", "grwm"]],
    ["Fitness & musculation", ["gym", "fitness", "workout", "muscu", "transformation", "abs", "gains"]],
    ["Business & argent", ["business", "money", "argent", "entrepreneur", "invest", "crypto", "trading", "sidehustle"]],
    ["Cuisine & food", ["recipe", "recette", "food", "cuisine", "cooking", "foodie", "eat"]],
    ["Gaming", ["gaming", "game", "gamer", "fortnite", "minecraft", "valorant", "twitch"]],
    ["Voyage", ["travel", "voyage", "trip", "wanderlust", "explore"]],
    ["Animaux", ["dog", "cat", "chien", "chat", "puppy", "animal", "pet"]],
    ["Éducation & astuces", ["tips", "astuce", "learn", "tuto", "howto", "hack", "apprendre"]],
    ["Développement personnel", ["motivation", "mindset", "discipline", "selfimprovement", "développement"]],
  ];
  let best = "", bestScore = 0;
  for (const [niche, kws] of map) {
    let score = 0;
    for (const kw of kws) { if (text.includes(kw)) score++; }
    if (score > bestScore) { bestScore = score; best = niche; }
  }
  if (!best && /\b(sport|athlete|highlights)\b/.test(text)) best = "Sport";
  return bestScore > 0 ? best : (best || "");
}

async function buildSmartSummary(audience, videos, top, platform, aiKey, owner, totalPublished, bio, priorInsights) {
  const base = { audience, video_count: videos.length, total_published: totalPublished || videos.length,
    avg_views: 0, avg_engagement_rate: 0, total_shares: 0, total_saves: 0, top_videos: top, owner, insights: null };
  if (!videos.length) {
    base.insights = { verdict: "Aucune vidéo publique trouvée.", niche: "", content_type: "", production_kind: "", needs_script: true, patterns: [], equivalents: [], formula: null, why: [], blueprints: [], scorecard: null };
    base.best_videos = []; base.worst_videos = [];
    return base;
  }
  const totalViews = videos.reduce((s, v) => s + (v.views || 0), 0);
  base.avg_views = Math.round(totalViews / videos.length);
  base.total_views = totalViews;
  base.total_shares = videos.reduce((s, v) => s + (v.shares || 0), 0);
  base.total_saves = videos.reduce((s, v) => s + (v.saves || 0), 0);
  const er = videos.filter((v) => v.views > 0).map((v) => ((v.likes + v.comments + v.shares) / v.views) * 100);
  base.avg_engagement_rate = er.length ? +(er.reduce((s, r) => s + r, 0) / er.length).toFixed(2) : 0;

  const sorted = [...videos].sort((a, b) => b.views - a.views);
  base.best_videos = sorted.slice(0, 3);
  const withViews = sorted.filter(v => v.views > 0);
  base.worst_videos = withViews.slice(-2).reverse();
  // 6 vidéos les plus RÉCENTES (par date de publication) -> détection "nouvelle vidéo" + verdict côté app.
  base.recent_videos = [...videos].sort((a, b) => (b.create_time || 0) - (a.create_time || 0)).slice(0, 6)
    .map((v) => ({ id: v.id, description: v.description, views: v.views, likes: v.likes, comments: v.comments, create_time: v.create_time, cover: v.cover, url: v.url }));

  const fallbackNiche = guessNiche(videos, bio || "");
  if (aiKey && top.length) {
    try {
      base.insights = await aiInsights(audience, base, top, platform, aiKey, owner, bio);
      if (base.insights && !base.insights.niche && fallbackNiche) base.insights.niche = fallbackNiche;
      if (base.insights && typeof base.insights.needs_script !== "boolean") base.insights.needs_script = guessNeedsScript(base.insights);
    }
    catch (e) {
      base._ai_error = String(e?.message ?? e).slice(0, 300);
      base.insights = fb(top, fallbackNiche);
    }
  } else { base.insights = priorInsights || fb(top, fallbackNiche); }  // pas d'IA -> on réutilise la stratégie précédente
  return base;
}

// Heuristique de secours : une niche a-t-elle besoin d'un script/voix off ?
function guessNeedsScript(ins) {
  const hay = ((ins?.niche || "") + " " + (ins?.content_type || "") + " " + (ins?.production_kind || "")).toLowerCase();
  if (/(clip|compil|repost|extrait|highlight|podcast|best of|moment|gameplay|react)/.test(hay)) return false;
  return true;
}

function fb(top, niche) {
  return { verdict: "Voici les vidéos qui performent le mieux.", niche: niche || "", content_type: "", production_kind: "", needs_script: true, patterns: [], equivalents: [], formula: null, why: [], blueprints: [], scorecard: null };
}

async function aiInsights(audience, stats, top, platform, key, owner, bio) {
  const vids = top.map((v, i) => `Vidéo ${i+1} [${v.video_type === "scripted" ? "SCRIPTÉE" : "VISUELLE"}${v.duration_s ? ", " + v.duration_s + "s" : ""}${v.words_per_sec ? ", débit " + v.words_per_sec + " mots/s" : ""}]: "${v.description}" — ${v.views} vues, ${v.likes} likes. Hashtags: ${(v.hashtags||[]).join(", ")}.${v.transcript && v.transcript.length > 60 ? ' Script: "' + v.transcript.slice(0, 400) + '"' : ''}`).join("\n");
  const isComp = owner === "competitor";
  const tone = isComp ? "Compte CONCURRENT: 3e personne." : "Compte de l'utilisateur: tutoie-le.";
  const system = `Tu es le moteur d'analyse Skillora. ${tone}
Déduis le mode de production depuis les descriptions, hashtags, scripts et durées.
Style: comme un créateur PRO qui explique à un DÉBUTANT TOTAL, zéro emoji, zéro blabla, 100% actionnable.

IMPORTANT "niche": sois PRÉCIS, pas générique, en 1-2 mots (ex: "Football" pas "Sport"; "Histoires & mystère"; "Basketball"; "Maquillage").

DÉTECTE le type de production ("production_kind") :
- "clipping" = l'utilisateur DÉCOUPE et reposte des extraits d'une vidéo SOURCE d'un AUTRE créateur (ex: clips MrBeast, extraits de podcast, highlights de match, moments de stream). La vidéo source existe déjà AVEC son audio.
- "original" = contenu créé par l'utilisateur (filmé caméra, voix off perso, généré par IA).

"needs_script" (booléen) = ce compte a-t-il besoin qu'on lui écrive un SCRIPT/voix off ?
- false si clipping/repost (l'extrait a DÉJÀ son audio d'origine) OU si une personne parle face caméra en direct.
- true si voix off / narration / storytelling faceless / vidéos IA qui ont besoin d'un texte à dire.

REGLE clipping (production_kind = "clipping") : les blueprints doivent être VRAIS et CONCRETS. NE dis JAMAIS d'\"ajouter un script\" ou de \"filmer\". À la place, explique :
1) où trouver la vidéo SOURCE ENTIÈRE (nom exact de la chaîne/créateur, type de vidéo, mots-clés de recherche YouTube),
2) quels MOMENTS découper (le pic d'action, le retournement, la punchline), comment repérer le passage fort,
3) le format (vertical 9:16, recadrage sur l'action, sous-titres incrustés, hook texte dès la 1ère seconde),
4) la durée idéale et l'outil de montage simple (CapCut).
Pour ces comptes, "stack" = outils de téléchargement + montage (ex: \"YouTube source + CapCut\"), et "sources" = mots-clés de recherche EXACTS pour trouver les vidéos sources.

REGLE original : jamais reprendre le même clip ; donne des ÉQUIVALENTS (même mécanique, autre sujet). blueprints: déduis IA (Midjourney/Kling/ElevenLabs), clips réels, ou filmé.

Chaque "steps" : 5 étapes courtes, dans l'ordre, qu'un débutant peut suivre sans rien connaître.
JSON strict:
{
  "niche": "<niche PRÉCISE, 1-2 mots>", "content_type": "<Réel|IA|Mixte>",
  "production_kind": "<clipping|original>", "needs_script": <true|false>,
  "verdict": "<max 16 mots>",
  "scorecard": {"hook": <0-10>, "tension": <0-10>, "emotion": <0-10>, "sujet": <0-10>, "explication": "<max 20 mots>"},
  "why": [{"video": "<titre court>", "raison": "<max 25 mots>"}],
  "blueprints": [{"video": "<titre court>", "mode": "<Clipping|IA animée|Clips réels|Filmé caméra|Mixte>", "stack": "<outils>", "difficulty": "<Facile|Moyen|Avancé>", "budget": "<~X€/mois>", "time": "<~X min>", "steps": ["<1>","<2>","<3>","<4>","<5>"], "prompt_example": "<si IA sinon vide>", "sources": "<mots-clés exacts pour trouver la matière>"}],
  "equivalents": ["<même mécanique autre sujet + mot-clé, max 20 mots>", "<2>", "<3>"],
  "patterns": ["<max 14 mots>", "<2>", "<3>"],
  "formula": {"hook": "<max 12 mots>", "structure": ["<max 10 mots>","<2>","<3>","<4>"], "cta": "<max 10 mots>"}
}`;
  const userMsg = `Compte: ${audience} abonnés. Bio: "${(bio||'').slice(0,150)}". ${stats.total_published} vidéos publiées, ${stats.video_count} analysées. Vues moy: ${stats.avg_views}. Engagement: ${stats.avg_engagement_rate}%.\nTop 3:\n${vids}`;
  let r = null, lastErr = "";
  for (const model of AI_MODELS) {
    r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01" },
      body: JSON.stringify({ model, max_tokens: 3000, system, messages: [{ role: "user", content: userMsg }] }),
    });
    if (r.ok) break;
    const errTxt = await r.text();
    lastErr = `Anthropic ${r.status}: ${errTxt.slice(0, 150)}`;
    if (r.status !== 404) throw new Error(lastErr);
    r = null;
  }
  if (!r) throw new Error(lastErr || "Aucun modèle IA disponible.");
  const d = await r.json();
  let t = "";
  if (Array.isArray(d.content)) for (const b of d.content) if (b.type === "text") t += b.text;
  t = t.replace(/```json/g, "").replace(/```/g, "").trim();
  const s = t.indexOf("{"), e = t.lastIndexOf("}");
  return JSON.parse(s >= 0 && e > s ? t.slice(s, e + 1) : t);
}
