// SKILLORA — crée un paiement PayPal (carte ou compte PayPal) pour un plan.
// Paiement PAR PÉRIODE (1 mois ou 1 an) : la carte en invité fonctionne
// (contrairement aux abonnements auto-renouvelés de PayPal). Renvoie l'URL
// de la page de paiement PayPal (redirection).
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const PRICE: Record<string, Record<string, number>> = {
  monthly: { starter: 25, growth: 49, elite: 89 },
  yearly: { starter: 250, growth: 490, elite: 890 },
};
const APP_URL = "https://skillora.me/app.html";

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

    const OWNERS = ["aydencastor07@gmail.com", "aydencastor1020@gmail.com"];
    const email = (u.user.email || "").toLowerCase();
    const body = await req.json().catch(() => ({}));

    let plan: string, billing: string, amount: number;
    if (body.test === true) {
      if (!OWNERS.includes(email)) return json({ success: false, error: "Test réservé au propriétaire." }, 403);
      plan = "test"; billing = "monthly";
      amount = Math.min(5, Math.max(0.10, Number(body.amount) || 0.10));
    } else {
      plan = String(body.plan || "").toLowerCase().trim();
      billing = String(body.billing || "monthly").toLowerCase().trim();
      if (billing === "annual") billing = "yearly";
      const a = PRICE[billing]?.[plan];
      if (!a) return json({ success: false, error: "Plan ou période invalide." }, 400);
      amount = a;
    }

    const at = await token();
    const order = await fetch(apiBase() + "/v2/checkout/orders", {
      method: "POST",
      headers: { "Authorization": "Bearer " + at, "Content-Type": "application/json" },
      body: JSON.stringify({
        intent: "CAPTURE",
        purchase_units: [{
          amount: { currency_code: "USD", value: amount.toFixed(2) },
          custom_id: u.user.id + "|" + plan + "|" + billing,
          description: plan === "test" ? "Skillora — test de paiement" : ("Skillora " + plan + " (" + (billing === "yearly" ? "annuel" : "mensuel") + ")"),
        }],
        application_context: {
          brand_name: "Skillora",
          user_action: "PAY_NOW",
          shipping_preference: "NO_SHIPPING",
          return_url: APP_URL + "?paypalcap=1",
          cancel_url: APP_URL + "?paypalcancel=1",
        },
      }),
    });
    const od = await order.json();
    if (!od.id) return json({ success: false, error: "Création du paiement impossible." }, 502);
    const link = (od.links || []).find((l: { rel: string; href: string }) => l.rel === "payer-action" || l.rel === "approve");
    if (!link) return json({ success: false, error: "Lien de paiement introuvable." }, 502);
    return json({ success: true, url: link.href });
  } catch (e) {
    return json({ success: false, error: String((e as Error)?.message || e) }, 500);
  }
});
