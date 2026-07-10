// SKILLORA — scout-winners : l'agent ÉCLAIREUR autonome.
// =========================================================================================
// Remplace la recherche humaine de "vidéos qui cartonnent". Pour CHAQUE compte connecté :
//   1) à la 1ʳᵉ vue, on pose une LIGNE DE BASE (baseline_at = maintenant + médiane de vues) ;
//      → tout ce qui existait AVANT la connexion est ignoré. On n'apprend que du NEUF.
//   2) aux passages suivants, on repère les vidéos publiées APRÈS la connexion qui EXPLOSENT :
//        • gagnante DU CRÉATEUR (user-styles) : vues >= max(1000, 3× sa médiane) ;
//        • gagnante GÉNÉRALE (style-library, l'école de Gemini) : vues >= 50 000.
//   3) on les met en file `winning_videos`. Le video-worker les fait ÉTUDIER par Gemini au repos.
//
// ÉCONOMIE DE CRÉDITS SociaVault : on ne rescane un compte qu'au plus une fois / SCAN_INTERVAL_H
// (défaut 20 h) et seulement les plateformes qui exposent une liste de vidéos (tiktok/instagram/youtube).
// Déclenchement : cron Supabase (voir README) OU POST manuel { user_id?, force? }.
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const SV_SCRAPE = "https://api.sociavault.com/v1/scrape";
const GLOBAL_MIN_VIEWS = 50000;   // seuil "école de Gemini" (bibliothèque générale)
const CREATOR_MIN_VIEWS = 1000;   // plancher perso : en dessous, ce n'est pas une "gagnante"
const CREATOR_MULT = 3;           // gagnante perso = >= 3× la médiane du compte
const SCAN_INTERVAL_H = 20;       // on ne rescane pas un compte plus d'une fois toutes les 20 h
const MAX_ACCOUNTS = 40;          // plafond par exécution (protège les crédits)

function j(o: unknown, s = 200) {
  return new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });
}
async function svGet(path: string, key: string) {
  const r = await fetch(SV_SCRAPE + path, { headers: { "X-API-Key": key } });
  if (!r.ok) throw new Error(`SociaVault ${r.status}`);
  return r.json();
}
function median(nums: number[]) {
  const a = nums.filter((n) => typeof n === "number" && n >= 0).sort((x, y) => x - y);
  if (!a.length) return 0;
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : Math.round((a[m - 1] + a[m]) / 2);
}

// ---- récupération des vidéos récentes { url, media_url, views, create_time } par plateforme ----
// media_url = lien mp4 DIRECT (CDN) quand la plateforme le donne : c'est lui que Gemini pourra
// télécharger pour étudier la vidéo (les pages TikTok/Instagram ne sont pas des fichiers vidéo).
function tiktokPlayUrl(v: any): string {
  const cands = [v?.video?.play_addr?.url_list, v?.video?.download_addr?.url_list,
                 v?.video?.play_addr_h264?.url_list, v?.video?.bit_rate?.[0]?.play_addr?.url_list];
  for (const c of cands) {
    const arr = Array.isArray(c) ? c : (c ? Object.values(c) : []);
    for (const u of arr) if (typeof u === "string" && u.startsWith("http")) return u;
  }
  return "";
}
async function tiktokVideos(handle: string, key: string) {
  const data = await svGet(`/tiktok/videos?handle=${encodeURIComponent(handle)}&count=30`, key);
  const d = data.data ?? data;
  const list = d.aweme_list ?? {};
  const arr = Array.isArray(list) ? list : Object.values(list);
  return arr.map((v: any) => ({
    views: Number(v?.statistics?.play_count ?? 0),
    create_time: Number(v?.create_time ?? 0),
    url: v?.aweme_id ? `https://www.tiktok.com/@${handle}/video/${v.aweme_id}` : "",
    media_url: tiktokPlayUrl(v),
  })).filter((x) => x.url);
}
async function instagramVideos(handle: string, key: string) {
  const data = await svGet(`/instagram/posts?handle=${encodeURIComponent(handle)}&trim=true`, key);
  const d = data.data ?? data;
  const arr = Array.isArray(d) ? d : (d.items ?? d.posts ?? d.edges ?? Object.values(d).find(Array.isArray) ?? []);
  return (arr as any[]).map((it: any) => {
    const v = it.node ?? it;
    const code = v.code ?? v.shortcode ?? v.short_code ?? "";
    const media = v.video_versions?.[0]?.url ?? v.video_url ?? "";
    return {
      views: Number(v.play_count ?? v.view_count ?? v.video_view_count ?? v.ig_play_count ?? v.views ?? 0),
      create_time: Number(v.taken_at ?? v.taken_at_timestamp ?? v.timestamp ?? 0),
      url: code ? `https://www.instagram.com/p/${code}/` : "",
      media_url: typeof media === "string" && media.startsWith("http") ? media : "",
    };
  }).filter((x) => x.url);
}
async function youtubeVideos(handle: string, key: string) {
  let data: any = null;
  for (const q of [`/youtube/videos?handle=${encodeURIComponent(handle)}&count=50`,
                   `/youtube/channel-videos?handle=${encodeURIComponent(handle)}`]) {
    try { data = await svGet(q, key); if (data) break; } catch { /* try next */ }
  }
  if (!data) return [];
  const d = data.data ?? data;
  const arr = Array.isArray(d) ? d : (d.videos ?? d.items ?? Object.values(d).find(Array.isArray) ?? []);
  return (arr as any[]).map((v: any) => {
    const id = v.video_id ?? v.id ?? "";
    const t = v.published_at ?? v.publish_date ?? v.upload_date ?? 0;
    const ts = typeof t === "string" ? Math.floor(Date.parse(t) / 1000) : Number(t);
    return {
      views: Number(v.view_count ?? v.views ?? v.viewCount ?? v.statistics?.viewCount ?? 0),
      create_time: Number.isFinite(ts) ? ts : 0,
      url: v.url ?? (id ? `https://youtube.com/watch?v=${id}` : ""),
      media_url: "",  // YouTube : Gemini lit le lien directement, pas besoin de mp4
    };
  }).filter((x) => x.url);
}
async function fetchVideos(platform: string, handle: string, key: string) {
  if (platform === "tiktok" || platform === "tiktok_business") return tiktokVideos(handle, key);
  if (platform === "instagram") return instagramVideos(handle, key);
  if (platform === "youtube") return youtubeVideos(handle, key);
  return []; // Facebook / X / LinkedIn : pas de liste vidéo exploitable ici
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const SV_KEY = Deno.env.get("SOCIAVAULT_API_KEY");
    if (!SV_KEY) return j({ success: false, error: "Clé SociaVault manquante." }, 500);
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
      { auth: { persistSession: false } });

    const body = await req.json().catch(() => ({}));
    const onlyUser: string | null = body.user_id || null;   // scanner un seul créateur (ex. juste après connexion)
    const force: boolean = !!body.force;                    // ignorer l'intervalle anti-crédits

    // Comptes connectés vérifiés, plateformes analysables uniquement.
    let q = admin.from("social_connections")
      .select("user_id, platform, handle, handle_verified")
      .eq("handle_verified", true)
      .in("platform", ["tiktok", "tiktok_business", "instagram", "youtube"]);
    if (onlyUser) q = q.eq("user_id", onlyUser);
    const { data: conns } = await q;
    const accounts = (conns || []).filter((c) => c.handle);

    let scanned = 0, queued = 0, baselined = 0;
    const cutoff = Date.now() - SCAN_INTERVAL_H * 3600 * 1000;

    for (const acc of accounts) {
      if (scanned >= MAX_ACCOUNTS) break;
      const handle = String(acc.handle).replace(/^@/, "");

      // baseline existante ?
      const { data: base } = await admin.from("scout_accounts")
        .select("*").eq("user_id", acc.user_id).eq("platform", acc.platform).eq("handle", handle).maybeSingle();

      // ÉCONOMIE MAXIMALE (0 crédit) : si une ANALYSE récente de ce compte existe déjà en base
      // (payée quand l'utilisateur a analysé son compte sur le site), on RÉUTILISE ses vidéos
      // récentes au lieu de re-scraper. Une dépense, deux usages.
      let vids: { views: number; create_time: number; url: string; media_url?: string }[] = [];
      let fromAnalysis = false;
      try {
        const aPlat = acc.platform.startsWith("tiktok") ? "tiktok" : acc.platform;
        const { data: ana } = await admin.from("analyses")
          .select("summary, created_at").eq("user_id", acc.user_id).eq("platform", aPlat)
          .ilike("username", handle).order("created_at", { ascending: false }).limit(1).maybeSingle();
        const rv = ana?.summary?.recent_videos;
        if (ana && Array.isArray(rv) && rv.length && Date.parse(ana.created_at) > cutoff) {
          vids = rv.map((v: any) => ({
            views: Number(v.views) || 0, create_time: Number(v.create_time) || 0,
            url: String(v.url || ""), media_url: "",
          })).filter((v: any) => v.url);
          fromAnalysis = vids.length > 0;
        }
      } catch (_e) { /* pas d'analyse exploitable -> scrape classique */ }

      if (!fromAnalysis) {
        // anti-crédits : on ne rescane pas trop souvent (sauf force / juste après connexion)
        if (base && !force && base.last_scanned_at && Date.parse(base.last_scanned_at) > cutoff) continue;
        try { vids = await fetchVideos(acc.platform, handle, SV_KEY); }
        catch (e) { console.error("scout fetch", acc.platform, handle, String(e)); continue; }
      }
      scanned++;
      // médiane : fiable seulement sur un vrai scrape (30 vidéos) ; sinon on garde celle connue
      const med = fromAnalysis ? (base?.median_views || median(vids.map((v) => v.views)))
                               : median(vids.map((v) => v.views));

      // 1ʳᵉ vue : on pose la ligne de base et on N'APPREND RIEN du passé.
      if (!base) {
        await admin.from("scout_accounts").insert({
          user_id: acc.user_id, platform: acc.platform, handle,
          median_views: med, last_scanned_at: new Date().toISOString(), scans: 1,
        });
        baselined++;
        continue;
      }

      const baselineSec = Math.floor(Date.parse(base.baseline_at) / 1000);
      const runningMed = med || base.median_views || 0;
      const creatorThreshold = Math.max(CREATOR_MIN_VIEWS, CREATOR_MULT * runningMed);
      const rows: any[] = [];
      for (const v of vids) {
        if (!v.create_time || v.create_time <= baselineSec) continue;   // publiée AVANT la connexion -> ignorée
        if (v.views >= creatorThreshold) {
          rows.push({ user_id: acc.user_id, platform: acc.platform, video_url: v.url,
            media_url: v.media_url || null, views: v.views, create_time: v.create_time, scope: "creator" });
        }
        if (v.views >= GLOBAL_MIN_VIEWS) {
          rows.push({ user_id: acc.user_id, platform: acc.platform, video_url: v.url,
            media_url: v.media_url || null, views: v.views, create_time: v.create_time, scope: "global" });
        }
      }
      if (rows.length) {
        // unique(video_url, scope) -> ignore les doublons déjà en file/étudiés.
        await admin.from("winning_videos").upsert(rows, { onConflict: "video_url,scope", ignoreDuplicates: true });
        queued += rows.length;
      }
      await admin.from("scout_accounts").update({
        median_views: runningMed, last_scanned_at: new Date().toISOString(), scans: (base.scans || 0) + 1,
      }).eq("id", base.id);
    }

    return j({ success: true, accounts: accounts.length, scanned, baselined, queued });
  } catch (err) {
    return j({ success: false, error: String(err) }, 500);
  }
});
