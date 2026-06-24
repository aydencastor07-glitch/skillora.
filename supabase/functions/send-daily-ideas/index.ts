// SKILLORA — send-daily-ideas v3 : Haiku 4.5 + score de viralité dans l'email. Cron quotidien -> Resend.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const APP_URL = "https://skillora.me/app.html";
const MODEL = "claude-haiku-4-5";
const FROM = "Skillora <idees@skillora.me>"; // domaine vérifié dans Resend

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok");
  if (req.method !== "POST") return new Response("Method not allowed", { status: 405 });
  try {
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
    const given = req.headers.get("x-cron-secret") ?? "";
    const { data: cfg } = await admin.from("cron_config").select("secret").eq("name", "send_daily_ideas").maybeSingle();
    if (!cfg || !given || given !== cfg.secret) return new Response("forbidden", { status: 403 });

    const AI_KEY = Deno.env.get("ANTHROPIC_API_KEY");
    const RESEND = Deno.env.get("RESEND_API_KEY");
    const today = new Date().toISOString().slice(0, 10);
    const { data: subs } = await admin.from("idea_email_subs").select("*").eq("active", true);
    let sent = 0, skipped = 0;

    for (const sub of (subs || [])) {
      if (sub.last_sent === today) { skipped++; continue; }
      const email = sub.email;
      if (!email) { skipped++; continue; }

      let ideas = null;
      const { data: cached } = await admin.from("daily_ideas")
        .select("ideas").eq("user_id", sub.user_id).eq("platform", sub.platform)
        .eq("username", sub.username).eq("idea_date", today).maybeSingle();
      if (cached && Array.isArray(cached.ideas) && cached.ideas.length) ideas = cached.ideas;

      if (!ideas) {
        const niche = await resolveNiche(admin, sub);
        if (!niche.niche && !niche.best) { skipped++; continue; }
        if (!AI_KEY) { skipped++; continue; }
        try {
          ideas = await generateIdeas({ platform: sub.platform, ...niche }, AI_KEY);
          await admin.from("daily_ideas").upsert(
            { user_id: sub.user_id, platform: sub.platform, username: sub.username, idea_date: today, ideas },
            { onConflict: "user_id,platform,username,idea_date" },
          );
        } catch (_e) { skipped++; continue; }
      }
      if (!ideas || !ideas.length) { skipped++; continue; }

      if (RESEND) {
        const topScore = Math.max(...ideas.map((it) => Number(it.viral_score) || 0));
        const html = emailHtml(sub.username, ideas);
        const subject = topScore >= 1
          ? `Nouvelle idée avec un potentiel ${topScore}/10 pour @${sub.username}`
          : `Tes idées du jour pour @${sub.username} sont prêtes`;
        const r = await fetch("https://api.resend.com/emails", {
          method: "POST",
          headers: { "Authorization": `Bearer ${RESEND}`, "Content-Type": "application/json" },
          body: JSON.stringify({ from: FROM, to: [email], subject, html }),
        });
        if (r.ok) { sent++; await admin.from("idea_email_subs").update({ last_sent: today, updated_at: new Date().toISOString() }).eq("user_id", sub.user_id).eq("platform", sub.platform).eq("username", sub.username); }
        else { skipped++; }
      } else { skipped++; }
    }
    return new Response(JSON.stringify({ ok: true, sent, skipped }), { headers: { "Content-Type": "application/json" } });
  } catch (e) {
    return new Response("err: " + (e?.message ?? String(e)), { status: 500 });
  }
});

async function resolveNiche(admin, sub) {
  const uLow = String(sub.username).toLowerCase();
  const { data: profs } = await admin.from("niche_profiles").select("*").eq("user_id", sub.user_id).eq("platform", sub.platform);
  let prof = null;
  if (profs && profs.length) {
    const m = profs.filter((p) => String(p.account || "").toLowerCase().replace(/^@/, "") === uLow);
    prof = m.find((p) => p.is_active) || m.find((p) => p.is_connected) || m[0] || null;
  }
  const { data: an } = await admin.from("analyses").select("summary")
    .eq("user_id", sub.user_id).eq("platform", sub.platform).eq("username", sub.username)
    .order("created_at", { ascending: false }).limit(1).maybeSingle();
  const s = an?.summary ?? {};
  const ins = s.insights ?? {};
  const best = (s.best_videos || []).slice(0, 3).map((v) =>
    `"${(v.description || "").slice(0, 90)}" — ${v.views || 0} vues, ${v.likes || 0} likes`).join("\n");
  return {
    niche: (prof && prof.niche) || ins.niche || "",
    contentType: (prof && prof.format) || ins.content_type || "",
    face: (prof && prof.face) || "",
    profTags: (prof && Array.isArray(prof.tags)) ? prof.tags.join(" ") : "",
    best,
    formula: ins.formula ? JSON.stringify(ins.formula) : "",
    patterns: (ins.patterns || []).join(" | "),
  };
}

function esc(x) { return String(x == null ? "" : x).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

function emailHtml(username, ideas) {
  const items = ideas.slice(0, 3).map((it, i) => {
    const sc = Number(it.viral_score) || 0;
    const badge = sc >= 1 ? `<span style="background:#1d6b3f;color:#7ef0ab;border-radius:6px;padding:2px 8px;font-size:12px;font-weight:700;">Potentiel ${sc}/10</span>` : "";
    return `
    <div style="background:#0f1830;border:1px solid #1e2a4a;border-radius:12px;padding:14px 16px;margin-bottom:10px;">
      <div style="margin-bottom:6px;">${badge} <span style="font-size:12px;color:#7aa2ff;font-weight:700;text-transform:uppercase;">${esc(it.format || "TikTok")}</span></div>
      <div style="font-size:16px;color:#fff;font-weight:700;margin-bottom:6px;">${esc(it.title || "")}</div>
      <div style="font-size:14px;color:#cdd6f4;line-height:1.5;"><b style="color:#7aa2ff;">Hook :</b> ${esc(it.hook || "")}</div>
    </div>`;
  }).join("");
  return `
  <div style="font-family:Arial,Helvetica,sans-serif;background:#070d1f;padding:24px;color:#cdd6f4;">
    <div style="max-width:560px;margin:0 auto;">
      <div style="font-size:22px;font-weight:800;color:#fff;margin-bottom:4px;">On a trouvé tes idées du jour 💡</div>
      <div style="font-size:14px;color:#8b9bc4;margin-bottom:18px;">Pour ton compte @${esc(username)} — prêtes à tourner aujourd'hui.</div>
      ${items}
      <a href="${APP_URL}" style="display:block;text-align:center;background:#2f7bff;color:#fff;text-decoration:none;font-weight:700;padding:13px;border-radius:12px;margin-top:14px;">Voir mes idées →</a>
      <div style="font-size:12px;color:#6b7aa0;margin-top:18px;text-align:center;">Tu reçois cet email car tu as activé les idées quotidiennes dans Skillora.</div>
    </div>
  </div>`;
}

async function generateIdeas(ctx, key) {
  const system = `Tu es le moteur d'idéation Skillora pour créateurs (clips / faceless).
Tu tutoies l'utilisateur. Zéro emoji, zéro blabla. Chaque idée EXÉCUTABLE aujourd'hui par un débutant.
RÈGLE ABSOLUE : TOUTES les idées STRICTEMENT dans la niche indiquée.
Produis 4 idées NOUVELLES. "viral_score" = potentiel 1-10 (la plupart 6-9).
Réponds en FRANÇAIS. JSON STRICT :
{"ideas":[{"title":"..","viral_score":<1-10>,"hook":"..","angle":"..","structure":["..","..","..",".."],"source":"..","hashtags":[".."],"format":"TikTok|Reels|Shorts"}]}`;
  const userMsg = `Plateforme: ${ctx.platform}
NICHE (obligatoire): ${ctx.niche || "(déduire)"}
Visage: ${ctx.face || "(non précisé)"}
Format: ${ctx.contentType || "(inconnu)"}
Mots-clés: ${ctx.profTags || "(aucun)"}
Vidéos qui marchent:
${ctx.best || "(aucune)"}
Formule: ${ctx.formula || "(aucune)"}
Leviers: ${ctx.patterns || "(aucun)"}

Donne 4 idées prêtes-à-tourner, STRICTEMENT dans la niche, avec score de viralité.`;
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01" },
    body: JSON.stringify({ model: MODEL, max_tokens: 2000, system, messages: [{ role: "user", content: userMsg }] }),
  });
  if (!r.ok) throw new Error(`Anthropic ${r.status}`);
  const d = await r.json();
  let t = "";
  if (Array.isArray(d.content)) for (const b of d.content) if (b.type === "text") t += b.text;
  t = t.replace(/```json/g, "").replace(/```/g, "").trim();
  const a = t.indexOf("{"), b = t.lastIndexOf("}");
  const parsed = JSON.parse(a >= 0 && b > a ? t.slice(a, b + 1) : t);
  const ideas = Array.isArray(parsed) ? parsed : (parsed.ideas || []);
  return ideas.slice(0, 6);
}
