import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

// Améliorations par mois selon le plan. 'none' (gratuit) = 1 pour goûter.
const PLAN_IMPROVES = { starter: 5, growth: 20, elite: 60 };
const FREE_IMPROVES = 1;
const UNLIMITED_EMAILS = ["aydencastor1020@gmail.com"];

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
    const email = (u.user && u.user.email ? String(u.user.email) : "").toLowerCase();
    const unlimited = UNLIMITED_EMAILS.indexOf(email) >= 0;

    const body = await req.json().catch(() => ({}));
    const sourceUrl = String(body.source_url || "").trim();
    if (!sourceUrl) return json({ success: false, error: "source_url manquant." }, 400);
    // On n'accepte que des fichiers de NOTRE storage (pas d'URL arbitraire à faire télécharger au worker).
    const expectedPrefix = Deno.env.get("SUPABASE_URL") + "/storage/v1/object/public/post-media/";
    if (!sourceUrl.startsWith(expectedPrefix)) return json({ success: false, error: "source_url invalide." }, 400);

    // --- Quota mensuel selon le plan (échec OUVERT sur erreur DB, comme pfm-connect) ---
    if (!unlimited) {
      let maxImproves = FREE_IMPROVES;
      try {
        const { data: subRow } = await admin.from("subscriptions")
          .select("plan, status").eq("user_id", userId).maybeSingle();
        const plan = (subRow && subRow.plan ? String(subRow.plan) : "none").toLowerCase();
        const status = (subRow && subRow.status ? String(subRow.status) : "").toLowerCase();
        if (status === "active" && PLAN_IMPROVES[plan]) maxImproves = PLAN_IMPROVES[plan];
        const monthStart = new Date();
        monthStart.setUTCDate(1); monthStart.setUTCHours(0, 0, 0, 0);
        const { count } = await admin.from("video_jobs")
          .select("id", { count: "exact", head: true })
          .eq("user_id", userId)
          .neq("status", "error")
          .gte("created_at", monthStart.toISOString());
        if ((count || 0) >= maxImproves) {
          return json({
            success: false, code: "quota",
            error: "Tu as utilisé tes " + maxImproves + " amélioration" + (maxImproves > 1 ? "s" : "") + " du mois. Passe à un plan supérieur pour en avoir plus.",
          }, 403);
        }
      } catch (_e) { /* fail open */ }
    }

    // Pas plus d'un job actif à la fois par personne (le worker est partagé).
    const { data: active } = await admin.from("video_jobs")
      .select("id").eq("user_id", userId).in("status", ["queued", "processing"]).limit(1);
    if (active && active.length) return json({ success: false, code: "busy", error: "Une amélioration est déjà en cours. Attends qu'elle se termine." }, 409);

    const context = typeof body.context === "object" && body.context ? body.context : {};
    const { data: job, error } = await admin.from("video_jobs").insert({
      user_id: userId,
      source_url: sourceUrl,
      context: context,
      score_before: typeof body.score_before === "number" ? body.score_before : null,
      steps: [{ key: "wait", label: "En file d'attente…", state: "running" }],
    }).select("id").single();
    if (error) return json({ success: false, error: "Création du job impossible: " + error.message }, 500);

    return json({ success: true, job_id: job.id });
  } catch (e) {
    return json({ success: false, error: String(e && e.message || e) }, 500);
  }
});
