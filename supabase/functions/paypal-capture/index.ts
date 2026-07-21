// SKILLORA — capture le paiement PayPal au retour, vérifie qu'il est payé,
// et active l'abonnement (période mensuelle ou annuelle) dans Supabase.
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
function json(o: unknown, s = 200) {
  return new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });
}
function apiBase() {
  return (Deno.env.get("PAYPAL_ENV") || "live").toLowerCase() === "sandbox"
    ? "https://api-m.sandbox.paypal.com" : "https://api-m.paypal.com";
}
async function token() {
  const id = Deno.env.get("PAYPAL_CLIENT_ID"), sec = Deno.env.get("PAYPAL_SECRET");
  if (!id || !sec) throw new Error("PayPal non configuré.");
  const r = await fetch(apiBase() + "/v1/oauth2/token", {
    method: "POST",
    headers: { "Authorization": "Basic " + btoa(id + ":" + sec), "Content-Type": "application/x-www-form-urlencoded" },
    body: "grant_type=client_credentials",
  });
  const d = await r.json();
  if (!d.access_token) throw new Error("Auth PayPal échouée.");
  return d.access_token;
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
    const jwt = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "").trim();
    const { data: u } = await admin.auth.getUser(jwt);
    if (!u?.user) return json({ success: false, error: "Non authentifié." }, 401);
    const uid = u.user.id;

    const body = await req.json().catch(() => ({}));
    const orderId = String(body.order_id || "").trim();
    if (!orderId) return json({ success: false, error: "Commande manquante." }, 400);

    const at = await token();
    // Statut d'abord (idempotent : si déjà capturé, /capture renverrait une erreur)
    const g = await fetch(apiBase() + "/v2/checkout/orders/" + orderId, {
      headers: { "Authorization": "Bearer " + at },
    });
    const gd = await g.json();
    let od = gd;
    if (gd.status !== "COMPLETED") {
      const c = await fetch(apiBase() + "/v2/checkout/orders/" + orderId + "/capture", {
        method: "POST",
        headers: { "Authorization": "Bearer " + at, "Content-Type": "application/json" },
      });
      od = await c.json();
    }
    if (od.status !== "COMPLETED") {
      return json({ success: false, error: "Paiement non finalisé (" + (od.status || "?") + ")." }, 402);
    }

    const pu = (od.purchase_units || [])[0] || {};
    const custom = pu.custom_id || (pu.payments?.captures?.[0]?.custom_id) || "";
    const [cuid, plan, billing] = String(custom).split("|");
    if (cuid !== uid || !plan) return json({ success: false, error: "Paiement non reconnu." }, 400);
    const paid = pu.amount?.value || pu.payments?.captures?.[0]?.amount?.value || "";
    if (plan === "test") {
      return json({ success: true, test: true, amount: paid });
    }

    // Fin de période : +1 mois ou +1 an
    const now = new Date();
    const end = new Date(now);
    if (billing === "yearly") end.setFullYear(end.getFullYear() + 1);
    else end.setMonth(end.getMonth() + 1);

    const row = {
      plan, billing, status: "active", provider: "paypal",
      currency: "USD", cancel_at_period_end: false,
      current_period_end: end.toISOString(), updated_at: now.toISOString(),
    };
    const { data: ex } = await admin.from("subscriptions").select("id").eq("user_id", uid).limit(1);
    if (ex && ex.length) await admin.from("subscriptions").update(row).eq("user_id", uid);
    else await admin.from("subscriptions").insert({ user_id: uid, ...row });

    return json({ success: true, plan, billing, current_period_end: row.current_period_end });
  } catch (e) {
    return json({ success: false, error: String((e as Error)?.message || e) }, 500);
  }
});
