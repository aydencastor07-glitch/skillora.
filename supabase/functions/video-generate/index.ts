// Crée un job de GÉNÉRATION vidéo (« Copier une vidéo » du Studio) : à partir
// d'une IDÉE texte ou du LIEN d'une vidéo à reproduire, le video-worker génère
// une nouvelle vidéo (Directeur -> images -> animation -> montage). Traité par
// le même worker que l'amélioration, via context.mode = "generate".
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

function json(o, s) {
  return new Response(JSON.stringify(o), { status: s || 200, headers: { ...cors, "Content-Type": "application/json" } });
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

    // Anti-abus : pas trop de générations en même temps par personne.
    if (!TEST_MODE_NO_LIMITS) { /* place réservée à la facturation par crédits */ }
    const { count: activeCount } = await admin.from("video_jobs")
      .select("id", { count: "exact", head: true })
      .eq("user_id", userId).in("status", ["queued", "processing"]);
    if ((activeCount || 0) >= MAX_PARALLEL) {
      return json({ success: false, code: "busy",
        error: "Tu as déjà " + MAX_PARALLEL + " vidéos en cours. Attends qu'une se termine." }, 409);
    }

    // Deux modes : "blueprint" (analyse/plan, quasi gratuit) ou "generate"
    // (génération complète, coûteux). Par défaut : blueprint.
    const mode = body.blueprint === false ? "generate" : "blueprint";
    const vo = body.variation_opts && typeof body.variation_opts === "object" ? {
      lang: typeof body.variation_opts.lang === "string" ? body.variation_opts.lang.slice(0, 20) : null,
      changes: Array.isArray(body.variation_opts.changes) ? body.variation_opts.changes.filter((x) => typeof x === "string").slice(0, 6) : [],
    } : null;
    const context = { mode, idea, source_url: sourceUrl, variation: !!body.variation, variation_opts: vo };
    const { data: job, error } = await admin.from("video_jobs").insert({
      user_id: userId,
      source_url: sourceUrl || "generate://idea",
      context: context,
      steps: [{ key: "wait", label: "En file d'attente…", state: "running" }],
    }).select("id").single();
    if (error) return json({ success: false, error: "Création du job impossible: " + error.message }, 500);

    return json({ success: true, job_id: job.id });
  } catch (e) {
    return json({ success: false, error: String(e && e.message || e) }, 500);
  }
});
