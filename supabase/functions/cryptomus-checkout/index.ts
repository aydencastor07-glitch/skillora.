// SKILLORA — crée un paiement Cryptomus (carte ≥30$ ou crypto) pour le plan Pro.
// Le client paie par carte/crypto, Skillora encaisse en crypto sur le wallet.
// Renvoie l'URL de la page de paiement Cryptomus (redirection).
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import md5 from "https://esm.sh/js-md5@0.8.3";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const APP_URL = "https://skillora.me/app.html";
const PLAN_PRICE: Record<string, number> = { pro: 30 };  // un seul plan pour l'instant

function json(o: unknown, s = 200) {
  return new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });
}
function b64(str: string) {
  const bytes = new TextEncoder().encode(str);
  let bin = "";
  bytes.forEach((b) => (bin += String.fromCharCode(b)));
  return btoa(bin);
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
    const jwt = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "").trim();
    const { data: u } = await admin.auth.getUser(jwt);
    if (!u?.user) return json({ success: false, error: "Non authentifié." }, 401);

    const merchant = Deno.env.get("CRYPTOMUS_MERCHANT");
    const key = Deno.env.get("CRYPTOMUS_API_KEY");
    if (!merchant || !key) return json({ success: false, error: "Paiement pas encore configuré." }, 500);

    const OWNERS = ["aydencastor07@gmail.com", "aydencastor1020@gmail.com"];
    const email = (u.user.email || "").toLowerCase();
    const body = await req.json().catch(() => ({}));

    let plan: string, amount: number;
    if (body.test === true) {
      if (!OWNERS.includes(email)) return json({ success: false, error: "Test réservé au propriétaire." }, 403);
      plan = "test";
      amount = Math.min(50, Math.max(1, Number(body.amount) || 1));
    } else {
      plan = String(body.plan || "pro").toLowerCase().trim();
      const p = PLAN_PRICE[plan];
      if (!p) return json({ success: false, error: "Plan invalide." }, 400);
      amount = p;
    }

    const orderId = u.user.id + "|" + plan + "|" + Date.now();
    const payload = {
      amount: amount.toFixed(2),
      currency: "USD",
      order_id: orderId,
      url_return: APP_URL + "?cmreturn=1",
      url_success: APP_URL + "?cmreturn=1",
      url_callback: Deno.env.get("SUPABASE_URL") + "/functions/v1/cryptomus-webhook",
      lifetime: 3600,
      subtract: "0",
    };
    const jsonBody = JSON.stringify(payload);
    const sign = md5(b64(jsonBody) + key);

    const r = await fetch("https://api.cryptomus.com/v1/payment", {
      method: "POST",
      headers: { "merchant": merchant, "sign": sign, "Content-Type": "application/json" },
      body: jsonBody,
    });
    const d = await r.json();
    if (d.state !== 0 || !d.result?.url) {
      return json({ success: false, error: "Cryptomus: " + (d.message || JSON.stringify(d.errors || d)) }, 502);
    }
    return json({ success: true, url: d.result.url });
  } catch (e) {
    return json({ success: false, error: String((e as Error)?.message || e) }, 500);
  }
});
