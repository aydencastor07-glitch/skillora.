// SKILLORA — notify-published : envoie un email quand la vidéo est en ligne.
// Appelé par un cron toutes les 2 min. Pour chaque post 'publishing'/'scheduled'
// dont l'heure de publication est passée et pas encore notifié, on envoie un email
// de confirmation + un bouton « Voir sur <réseau> » PAR plateforme (permaliens Post for Me),
// + les actions à faire pour pousser l'algo, puis on marque emailed.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const APP_URL = "https://skillora.me/app.html";
const PFM_BASE = "https://api.postforme.dev";

const PLAT_NAME: Record<string, string> = { tiktok: "TikTok", instagram: "Instagram", youtube: "YouTube", facebook: "Facebook", x: "X", linkedin: "LinkedIn" };
const PLAT_HOME: Record<string, string> = { tiktok: "https://www.tiktok.com", instagram: "https://www.instagram.com", youtube: "https://www.youtube.com", facebook: "https://www.facebook.com", x: "https://x.com", linkedin: "https://www.linkedin.com" };
const PLAT_COLOR: Record<string, string> = { tiktok: "#111827", instagram: "#c13584", youtube: "#ff0000", facebook: "#1877f2", x: "#111827", linkedin: "#0a66c2" };

async function pfmFetch(path: string, key: string, init: RequestInit = {}) {
  const base = (init.headers as Record<string, string>) || {};
  let res = await fetch(PFM_BASE + path, { ...init, headers: { "Content-Type": "application/json", "x-post-for-me-api-key": key, ...base } });
  if (res.status === 401 || res.status === 403) {
    res = await fetch(PFM_BASE + path, { ...init, headers: { "Content-Type": "application/json", "Authorization": "Bearer " + key, ...base } });
  }
  return res;
}
function plat(s: unknown) { return String(s ?? "").toLowerCase().replace("_business", "").trim(); }
function extractResults(post: any): Array<{ platform: string; url: string | null }> {
  if (!post || typeof post !== "object") return [];
  const arr = post.results ?? post.social_posts ?? post.posts ?? post.platforms ?? post.items ?? post.targets ?? post.data ?? [];
  const list = Array.isArray(arr) ? arr : [];
  const out: Array<{ platform: string; url: string | null }> = [];
  for (const r of list) {
    if (!r || typeof r !== "object") continue;
    const p = plat(r.platform ?? r.provider ?? r.type ?? r.social_account?.platform ?? r.account?.platform);
    if (!p) continue;
    const url = r.platform_url ?? r.url ?? r.permalink ?? r.post_url ?? r.link ?? (r.data && (r.data.url ?? r.data.permalink ?? r.data.platform_url)) ?? null;
    out.push({ platform: p, url: url ? String(url) : null });
  }
  return out;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok");
  if (req.method !== "POST") return new Response("Method not allowed", { status: 405 });
  try {
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
    const given = req.headers.get("x-cron-secret") ?? "";
    const { data: cfg } = await admin.from("cron_config").select("secret").eq("name", "send_daily_ideas").maybeSingle();
    if (!cfg || !given || given !== cfg.secret) return new Response("forbidden", { status: 403 });

    const RESEND = Deno.env.get("RESEND_API_KEY");
    const FROM = Deno.env.get("EMAIL_FROM") || "Skillora <idees@skillora.me>";
    const PFM_KEY = Deno.env.get("POSTFORME_API_KEY") || "";
    if (!RESEND) return new Response(JSON.stringify({ ok: false, error: "RESEND_API_KEY manquante" }), { status: 500 });

    const nowMs = Date.now();
    const { data: rows } = await admin.from("scheduled_posts")
      .select("*").eq("emailed", false).in("status", ["publishing", "scheduled"]).limit(50);

    let sent = 0, skipped = 0;

    async function mark(id: string, results: unknown) {
      const patch: Record<string, unknown> = { emailed: true, status: "published", published_at: new Date().toISOString() };
      if (Array.isArray(results) && results.length) patch.results = results;
      await admin.from("scheduled_posts").update(patch).eq("id", id);
    }

    for (const p of (rows || [])) {
      const createdMs = p.created_at ? Date.parse(p.created_at) : nowMs;
      const dueMs = p.scheduled_at ? Date.parse(p.scheduled_at) : (createdMs + 120000);
      if (dueMs > nowMs) { skipped++; continue; }

      // Permaliens par plateforme (réutilisés par la cloche 🔔 in-app via la colonne results).
      let results: Array<{ platform: string; url: string | null }> = Array.isArray(p.results) ? p.results : [];
      if (PFM_KEY && p.pfm_post_id && !(results.length && results.every((r) => r.url))) {
        try {
          const rr = await pfmFetch("/v1/social-posts/" + p.pfm_post_id, PFM_KEY, { method: "GET" });
          const d = await rr.json().catch(() => ({}));
          const fresh = extractResults(d.data ?? d);
          if (fresh.length) results = fresh;
        } catch (_e) { /* réseau : on garde ce qu'on a */ }
      }

      let email: string | null = null;
      try { const { data: ud } = await admin.auth.admin.getUserById(p.user_id); email = ud?.user?.email ?? null; } catch (_e) { /* ignore */ }
      if (!email) { await mark(p.id, results); skipped++; continue; }

      const r = await fetch("https://api.resend.com/emails", {
        method: "POST",
        headers: { "Authorization": `Bearer ${RESEND}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          from: FROM,
          to: [email],
          subject: "✅ Ta vidéo est en ligne — voici exactement quoi faire",
          html: publishedHtml(p, results),
        }),
      });
      if (r.ok) { await mark(p.id, results); sent++; } else { skipped++; }
    }

    return new Response(JSON.stringify({ ok: true, sent, skipped }), { headers: { "Content-Type": "application/json" } });
  } catch (e) {
    return new Response("err: " + ((e as Error)?.message ?? String(e)), { status: 500 });
  }
});

function esc(x: unknown) { return String(x == null ? "" : x).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

function platLabel(platforms: unknown) {
  const arr = Array.isArray(platforms) ? platforms : [];
  return arr.map((p) => PLAT_NAME[plat(p)] || String(p)).join(", ") || "tes réseaux";
}

// Un bouton « Voir sur <réseau> » par plateforme : on prend le permalien réel si dispo,
// sinon on retombe sur l'accueil du réseau (l'utilisateur a toujours un bouton qui marche).
function viewButtons(platforms: unknown, results: Array<{ platform: string; url: string | null }>) {
  const byPlat: Record<string, string | null> = {};
  (results || []).forEach((r) => { if (r && r.platform) byPlat[plat(r.platform)] = r.url; });
  const arr = Array.isArray(platforms) ? platforms : [];
  const keys = arr.length ? arr.map(plat) : Object.keys(byPlat);
  const seen: Record<string, boolean> = {};
  const btns = keys.filter((k) => { if (!k || seen[k]) return false; seen[k] = true; return true; }).map((k) => {
    const url = byPlat[k] || PLAT_HOME[k] || "https://skillora.me";
    const name = PLAT_NAME[k] || k;
    const color = PLAT_COLOR[k] || "#2f7bff";
    return `<a href="${esc(url)}" style="display:block;text-align:center;background:${color};color:#fff;text-decoration:none;font-weight:700;padding:13px;border-radius:12px;font-size:15px;margin-bottom:10px;">Voir sur ${esc(name)} →</a>`;
  });
  return btns.join("") || `<a href="${APP_URL}" style="display:block;text-align:center;background:#2f7bff;color:#fff;text-decoration:none;font-weight:700;padding:14px;border-radius:12px;font-size:15px;">Ouvrir l'app →</a>`;
}

function publishedHtml(p: any, results: Array<{ platform: string; url: string | null }>) {
  const wasScheduled = !!p.scheduled_at;
  const plats = platLabel(p.platforms);
  const intro = wasScheduled
    ? `Ta vidéo a été publiée <b style="color:#fff;">au bon moment</b> sur ${esc(plats)} — pile quand ton audience est la plus active.`
    : `Ta vidéo vient d'être publiée sur <b style="color:#fff;">${esc(plats)}</b>.`;
  return `
  <div style="font-family:Arial,Helvetica,sans-serif;background:#070d1f;padding:28px 24px;color:#cdd6f4;">
    <div style="max-width:540px;margin:0 auto;">
      <div style="text-align:center;font-size:42px;line-height:1;">🚀</div>
      <div style="text-align:center;font-size:23px;font-weight:800;color:#fff;margin:10px 0 6px;">Ta vidéo est en ligne !</div>
      <div style="text-align:center;font-size:15px;color:#9fb0d6;line-height:1.6;margin-bottom:22px;">${intro}</div>

      <div style="background:#0f1830;border:1px solid #1e2a4a;border-radius:14px;padding:18px;margin-bottom:18px;">
        <div style="font-size:16px;font-weight:800;color:#fff;margin-bottom:4px;">Fais ces 4 actions tout de suite</div>
        <div style="font-size:13px;color:#9fb0d6;margin-bottom:14px;">(dans les 30 premières minutes — c'est ce qui décide si ta vidéo perce)</div>

        <table style="width:100%;border-collapse:collapse;">
          <tr><td style="padding:8px 0;vertical-align:top;width:30px;font-size:18px;">1️⃣</td><td style="padding:8px 0;font-size:15px;color:#fff;"><b>Ouvre ta vidéo et regarde-la en entier</b>, jusqu'à la dernière seconde.</td></tr>
          <tr><td style="padding:8px 0;vertical-align:top;font-size:18px;">2️⃣</td><td style="padding:8px 0;font-size:15px;color:#fff;"><b>Mets un like</b> sur ta vidéo.</td></tr>
          <tr><td style="padding:8px 0;vertical-align:top;font-size:18px;">3️⃣</td><td style="padding:8px 0;font-size:15px;color:#fff;"><b>Écris un commentaire</b> sous ta vidéo.</td></tr>
          <tr><td style="padding:8px 0;vertical-align:top;font-size:18px;">4️⃣</td><td style="padding:8px 0;font-size:15px;color:#fff;"><b>Enregistre ta vidéo</b> (l'icône « Enregistrer » / signet).</td></tr>
        </table>

        <div style="font-size:13px;color:#7aa2ff;margin-top:14px;">Ces 4 signaux disent à l'algorithme de montrer ta vidéo à beaucoup plus de monde.</div>
      </div>

      ${viewButtons(p.platforms, results)}
      <div style="text-align:center;font-size:12px;color:#6b7aa0;margin-top:22px;">Publié automatiquement par Skillora · <a href="${APP_URL}" style="color:#7aa2ff;">Ouvrir l'app</a></div>
    </div>
  </div>`;
}
