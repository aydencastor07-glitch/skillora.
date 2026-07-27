// Crée un job de GÉNÉRATION vidéo (« Copier une vidéo » du Studio) : à partir
// d'une IDÉE texte ou du LIEN d'une vidéo à reproduire, le video-worker génère
// une nouvelle vidéo (Directeur -> images -> animation -> montage). Traité par
// le même worker que l'amélioration, via context.mode = "generate".
//
// MÉMOIRE DES VIDÉOS DÉJÀ ANALYSÉES
// ---------------------------------
// Analyser une vidéo coûte des crédits. Or la même vidéo revient souvent — et
// souvent sous un lien DIFFÉRENT (vm.tiktok.com/ZN8… et tiktok.com/@x/video/76…
// sont la même vidéo). On calcule donc une IDENTITÉ canonique de la vidéo :
// si on a déjà le plan de cette vidéo dans cette langue, on le redonne tout de
// suite, sans rien redépenser.
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

// MODE TEST (bêta) : pas de quota crédit pour l'instant, on teste le système.
// La facturation par crédits sera branchée ici ensuite.
const TEST_MODE_NO_LIMITS = true;
const MAX_PARALLEL = 3; // anti-abus : la génération est lourde (images + vidéos)

const NAV_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";

function json(o, s) {
  return new Response(JSON.stringify(o), { status: s || 200, headers: { ...cors, "Content-Type": "application/json" } });
}

async function sha256hex(txt) {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(txt));
  return Array.from(new Uint8Array(b)).map((x) => x.toString(16).padStart(2, "0")).join("");
}

// Identité de la vidéo lisible DIRECTEMENT dans le lien, sans appel réseau.
// Même format que côté worker (worker.py : _video_key) — les deux doivent
// toujours produire la même chaîne, sinon le cache ne se retrouve plus.
function cleDirecte(url) {
  let m;
  if ((m = url.match(/(?:youtu\.be\/|[?&]v=|\/shorts\/|\/embed\/|\/live\/)([\w-]{11})/))) return "yt:" + m[1];
  if ((m = url.match(/tiktok\.com\/@[^/]+\/(?:video|photo)\/(\d+)/))) return "tt:" + m[1];
  if ((m = url.match(/tiktok\.com\/(?:v|embed)\/(\d+)/))) return "tt:" + m[1];
  if ((m = url.match(/instagram\.com\/(?:reels?|p|tv)\/([A-Za-z0-9_-]+)/))) return "ig:" + m[1];
  if ((m = url.match(/facebook\.com\/(?:[^/]+\/)?(?:videos|reel)\/(\d+)/))) return "fb:" + m[1];
  if ((m = url.match(/facebook\.com\/watch\/?\?(?:.*&)?v=(\d+)/))) return "fb:" + m[1];
  if ((m = url.match(/(?:twitter|x)\.com\/[^/]+\/status\/(\d+)/))) return "x:" + m[1];
  return null;
}

// Liens raccourcis : le code ne dit rien de la vidéo, il faut suivre la
// redirection pour découvrir la vraie adresse. C'est ce qui permet de
// reconnaître qu'un lien de partage TikTok pointe vers une vidéo déjà analysée.
function estRaccourci(url) {
  return /^https?:\/\/(vm|vt)\.tiktok\.com\//i.test(url)
    || /tiktok\.com\/t\//i.test(url)
    || /^https?:\/\/fb\.watch\//i.test(url)
    || /facebook\.com\/share\//i.test(url)
    || /instagram\.com\/share\//i.test(url)
    || /^https?:\/\/(youtu\.be|bit\.ly|t\.co|tinyurl\.com|lnkd\.in)\//i.test(url);
}

async function suivreRedirection(url) {
  const stop = AbortSignal.timeout ? AbortSignal.timeout(7000) : undefined;
  try {
    const r = await fetch(url, {
      redirect: "follow",
      signal: stop,
      headers: { "User-Agent": NAV_UA, "Accept-Language": "fr,en;q=0.8" },
    });
    try { await r.body?.cancel(); } catch (_e) { /* on ne lit pas la page */ }
    return r.url || null;
  } catch (_e) {
    return null;
  }
}

// Repli quand aucune plateforme n'est reconnue : l'adresse elle-même, nettoyée
// (pas de www., pas de paramètres de suivi, pas de barre finale). Deux liens
// identiques à un ?igsh=… près se retrouvent donc quand même.
async function cleAdresse(url) {
  const nu = url.split("#")[0].split("?")[0]
    .replace(/^https?:\/\/(www\.|m\.)?/i, "")
    .replace(/\/+$/, "");
  const hote = nu.split("/")[0].toLowerCase();
  const norm = hote + nu.slice(nu.split("/")[0].length);
  return "url:" + (await sha256hex(norm)).slice(0, 32);
}

async function videoKey(url) {
  if (!url || !/^https?:\/\//i.test(url)) return null;
  if (url.includes("/storage/v1/object/public/")) return null; // fichier importé : unique
  const directe = cleDirecte(url);
  if (directe) return directe;
  if (estRaccourci(url)) {
    const vraie = await suivreRedirection(url);
    if (vraie) {
      const k = cleDirecte(vraie);
      if (k) return k;
      return await cleAdresse(vraie);
    }
  }
  return await cleAdresse(url);
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const admin = createClient(Deno.env.get("SUPABASE_URL"), Deno.env.get("SUPABASE_SERVICE_ROLE_KEY"), { auth: { persistSession: false } });
    const jwt = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "").trim();
    const { data: u } = await admin.auth.getUser(jwt);
    const userId = u && u.user ? u.user.id : null;
    if (!userId) return json({ success: false, error: "Non authentifié." }, 401);

    const body = await req.json().catch(() => ({}));
    const idea = String(body.idea || "").trim().slice(0, 2000);
    const sourceUrl = String(body.source_url || "").trim();
    if (!idea && !sourceUrl) {
      return json({ success: false, error: "Donne une idée ou colle le lien d'une vidéo à reproduire." }, 400);
    }
    if (sourceUrl && !/^https?:\/\//i.test(sourceUrl)) {
      return json({ success: false, error: "Le lien doit commencer par http(s)://" }, 400);
    }

    // Deux modes : "blueprint" (analyse/plan, quasi gratuit) ou "generate"
    // (génération complète, coûteux). Par défaut : blueprint.
    const mode = body.blueprint === false ? "generate" : "blueprint";
    const vo = body.variation_opts && typeof body.variation_opts === "object" ? {
      lang: typeof body.variation_opts.lang === "string" ? body.variation_opts.lang.slice(0, 20) : null,
      changes: Array.isArray(body.variation_opts.changes) ? body.variation_opts.changes.filter((x) => typeof x === "string").slice(0, 6) : [],
    } : null;
    // Langue de l'interface : le plan doit etre redige dans la langue de la
    // personne, pas dans celle de la video qu'elle copie.
    const lang = ["fr", "en", "es", "pt", "de"].includes(String(body.lang || "")) ? String(body.lang) : "fr";
    const variation = !!body.variation;

    // ── Identité de la vidéo, puis mémoire ──────────────────────────────────
    // On la calcule avant tout : une vidéo déjà analysée ne repasse jamais par
    // le worker, donc ni file d'attente, ni crédits.
    let vkey = null;
    if (sourceUrl) {
      try { vkey = await videoKey(sourceUrl); } catch (_e) { vkey = null; }
    }

    if (vkey && mode === "blueprint" && !variation) {
      // Une variation change le résultat : elle ne se sert jamais du cache.
      // La langue fait partie de l'identité : un plan allemand n'est pas la
      // réponse à une demande française.
      // On lit d'abord les candidats SANS leur plan (des rangées légères), on
      // choisit, et on ne rapatrie que le plan retenu.
      const { data: dejaVu } = await admin.from("video_jobs")
        .select("id, context")
        .eq("video_key", vkey).eq("status", "done")
        .not("plan", "is", null)
        .order("created_at", { ascending: false }).limit(60);
      const choix = (dejaVu || []).find((j) => {
        const c = j.context || {};
        if (c.mode && c.mode !== "blueprint") return false;
        if (c.variation) return false;
        return (c.lang || "fr") === lang;
      });
      let memo = null;
      if (choix) {
        const { data: complet } = await admin.from("video_jobs")
          .select("id, plan, steps").eq("id", choix.id).single();
        if (complet && complet.plan && complet.plan.blueprint) memo = complet;
      }
      if (memo) {
        const context = {
          mode, idea, source_url: sourceUrl, variation: false, variation_opts: null, lang,
          cached_from: memo.id,
        };
        const { data: clone, error: eClone } = await admin.from("video_jobs").insert({
          user_id: userId,
          source_url: sourceUrl,
          video_key: vkey,
          status: "done",
          context,
          plan: memo.plan,
          steps: memo.steps || [],
          started_at: "now()",
          finished_at: "now()",
        }).select("id").single();
        if (!eClone && clone) {
          return json({ success: true, job_id: clone.id, cached: true });
        }
        // Si l'enregistrement échoue on ne bloque pas la personne : on
        // repart sur une analyse normale, juste en dessous.
      }
    }

    // Anti-abus : pas trop de générations en même temps par personne.
    // (après le cache : une réponse instantanée n'occupe aucune place)
    if (!TEST_MODE_NO_LIMITS) { /* place réservée à la facturation par crédits */ }
    const { count: activeCount } = await admin.from("video_jobs")
      .select("id", { count: "exact", head: true })
      .eq("user_id", userId).in("status", ["queued", "processing"]);
    if ((activeCount || 0) >= MAX_PARALLEL) {
      return json({ success: false, code: "busy",
        error: "Tu as déjà " + MAX_PARALLEL + " vidéos en cours. Attends qu'une se termine." }, 409);
    }

    const context = { mode, idea, source_url: sourceUrl, variation, variation_opts: vo, lang };
    const { data: job, error } = await admin.from("video_jobs").insert({
      user_id: userId,
      source_url: sourceUrl || "generate://idea",
      video_key: vkey,
      context: context,
      steps: [{ key: "wait", label: "En file d'attente…", state: "running" }],
    }).select("id").single();
    if (error) return json({ success: false, error: "Création du job impossible: " + error.message }, 500);

    return json({ success: true, job_id: job.id });
  } catch (e) {
    return json({ success: false, error: String(e && e.message || e) }, 500);
  }
});
