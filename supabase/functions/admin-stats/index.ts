// SKILLORA — statistiques business (mode dev). Réservé au propriétaire :
// vérifie l'email du JWT puis lit tout avec le service-role.
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const OWNERS = ["aydencastor07@gmail.com", "aydencastor1020@gmail.com"];
// Prix mensuels ($) ; l'annuel est ramené au mois (250/12…)
const PRICE_M: Record<string, number> = { starter: 25, growth: 49, elite: 89 };
const PRICE_Y: Record<string, number> = { starter: 250, growth: 490, elite: 890 };

function json(o: unknown, s = 200) {
  return new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
    const jwt = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "").trim();
    const { data: u } = await admin.auth.getUser(jwt);
    const email = (u?.user?.email || "").toLowerCase();
    if (!OWNERS.includes(email)) return json({ success: false, error: "Réservé au propriétaire." }, 403);

    const now = new Date();
    const dayMs = 86400000;
    const d1 = new Date(now.getTime() - dayMs).toISOString();
    const d7 = new Date(now.getTime() - 7 * dayMs).toISOString();
    const d30 = new Date(now.getTime() - 30 * dayMs).toISOString();

    // ── Membres ──────────────────────────────────────────────────────────────
    const { count: usersTotal } = await admin.from("profiles").select("id", { count: "exact", head: true });
    const { count: users24h } = await admin.from("profiles").select("id", { count: "exact", head: true }).gte("created_at", d1);
    const { count: users7d } = await admin.from("profiles").select("id", { count: "exact", head: true }).gte("created_at", d7);

    const { data: recent } = await admin.from("profiles")
      .select("id,email,created_at,ref_source,country")
      .order("created_at", { ascending: false }).limit(12);

    // Inscriptions / jour (30 j)
    const { data: p30 } = await admin.from("profiles").select("created_at").gte("created_at", d30);
    const byDay: Record<string, number> = {};
    for (let i = 29; i >= 0; i--) byDay[new Date(now.getTime() - i * dayMs).toISOString().slice(0, 10)] = 0;
    (p30 || []).forEach((r) => { const k = String(r.created_at).slice(0, 10); if (k in byDay) byDay[k]++; });

    // ── Abonnements / revenus ────────────────────────────────────────────────
    const { data: subs } = await admin.from("subscriptions")
      .select("user_id,plan,billing,status,created_at,current_period_end");
    const active = (subs || []).filter((s) =>
      ["active", "trialing", "completed"].includes(String(s.status || "").toLowerCase()) &&
      (!s.current_period_end || new Date(s.current_period_end) > now));
    let mrr = 0;
    const byPlan: Record<string, number> = {};
    const paidUsers = new Set<string>();
    for (const s of active) {
      const p = String(s.plan || "").toLowerCase();
      const yearly = String(s.billing || "").toLowerCase().startsWith("ann") || String(s.billing || "").toLowerCase() === "y";
      mrr += yearly ? (PRICE_Y[p] || 0) / 12 : (PRICE_M[p] || 0);
      byPlan[p] = (byPlan[p] || 0) + 1;
      if (s.user_id) paidUsers.add(String(s.user_id));
    }
    const newSubs24h = (subs || []).filter((s) => s.created_at >= d1).length;
    const newSubs7d = (subs || []).filter((s) => s.created_at >= d7).length;

    // ── Canaux marketing (clics / inscrits / payants par ?src=) ─────────────
    const { data: clicks } = await admin.from("marketing_clicks").select("ref,created_at").gte("created_at", d30);
    const { data: srcProfiles } = await admin.from("profiles").select("id,ref_source").not("ref_source", "is", null);
    const channels: Record<string, { clicks: number; clicks7d: number; signups: number; paying: number }> = {};
    const ch = (k: string) => channels[k] || (channels[k] = { clicks: 0, clicks7d: 0, signups: 0, paying: 0 });
    (clicks || []).forEach((c) => { const e = ch(String(c.ref)); e.clicks++; if (c.created_at >= d7) e.clicks7d++; });
    (srcProfiles || []).forEach((p) => {
      const e = ch(String(p.ref_source)); e.signups++;
      if (paidUsers.has(String(p.id))) e.paying++;
    });

    return json({
      success: true,
      generated_at: now.toISOString(),
      users: { total: usersTotal || 0, last24h: users24h || 0, last7d: users7d || 0, by_day: byDay },
      revenue: {
        mrr: Math.round(mrr * 100) / 100,
        arr: Math.round(mrr * 12 * 100) / 100,
        active_subs: active.length, by_plan: byPlan,
        new_subs_24h: newSubs24h, new_subs_7d: newSubs7d,
      },
      channels,
      recent: recent || [],
    });
  } catch (e) {
    return json({ success: false, error: String((e as Error)?.message || e) }, 500);
  }
});
