// SKILLORA — réécrit le script d'un plan Copie en 3 versions, selon la
// demande du client (questions posées dans l'app). Synchrone et rapide.
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const MODELS = ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"];

function json(o: unknown, s = 200) {
  return new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
    const jwt = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "").trim();
    const { data: u } = await admin.auth.getUser(jwt);
    if (!u?.user) return json({ success: false, error: "Non authentifié." }, 401);

    const body = await req.json().catch(() => ({}));
    const script = String(body.script || "").trim().slice(0, 6000);
    const goal = String(body.goal || "").trim().slice(0, 60);
    const details = String(body.details || "").trim().slice(0, 500);
    if (!script) return json({ success: false, error: "Script manquant." }, 400);
    if (!goal && !details) return json({ success: false, error: "Dis-moi ce que tu veux changer." }, 400);

    const KEY = Deno.env.get("ANTHROPIC_API_KEY");
    if (!KEY) return json({ success: false, error: "IA non configurée." }, 500);

    const prompt =
      "Tu es un scénariste expert en vidéos virales courtes (TikTok/Reels/Shorts).\n" +
      "Voici le script actuel d'une vidéo :\n---\n" + script + "\n---\n" +
      "Demande du créateur : " + (goal || "améliorer") + (details ? (" — précisions : " + details) : "") + "\n\n" +
      "Réécris ce script en 3 VERSIONS distinctes qui respectent la demande. " +
      "Garde la même histoire et la même durée approximative. Chaque version doit être " +
      "prête à lire telle quelle (répliques comprises), dans la même langue que la " +
      "demande l'exige (sinon la langue du script actuel).\n" +
      "Réponds UNIQUEMENT avec ce JSON (aucun texte autour) :\n" +
      '{"versions":[{"titre":"nom court de l\'angle (3-5 mots)","script":"..."},{...},{...}]}';

    let out: { versions?: Array<{ titre?: string; script?: string }> } | null = null;
    for (const m of MODELS) {
      try {
        const r = await fetch("https://api.anthropic.com/v1/messages", {
          method: "POST",
          headers: { "x-api-key": KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json" },
          body: JSON.stringify({ model: m, max_tokens: 3500, messages: [{ role: "user", content: prompt }] }),
        });
        if (!r.ok) continue;
        const d = await r.json();
        const txt = (d.content || []).map((c: { text?: string }) => c.text || "").join("");
        const mjson = txt.match(/\{[\s\S]*\}/);
        if (mjson) { out = JSON.parse(mjson[0]); break; }
      } catch (_e) { /* modèle suivant */ }
    }
    const versions = (out?.versions || [])
      .filter((v) => v && typeof v.script === "string" && v.script.trim())
      .slice(0, 3)
      .map((v, i) => ({ titre: String(v.titre || ("Version " + (i + 1))).slice(0, 60), script: String(v.script).trim().slice(0, 6000) }));
    if (!versions.length) return json({ success: false, error: "L'IA n'a pas réussi. Réessaie." }, 502);
    return json({ success: true, versions });
  } catch (e) {
    return json({ success: false, error: String((e as Error)?.message || e) }, 500);
  }
});
