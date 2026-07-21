// SKILLORA — webhook Cryptomus. À chaque notification, on RE-VÉRIFIE le
// paiement via l'API Cryptomus (avec notre clé) pour ne pas faire confiance
// aveuglément au callback, puis on active l'abonnement si c'est payé.
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import md5 from "https://esm.sh/js-md5@0.8.3";

function b64(str: string) {
  const bytes = new TextEncoder().encode(str);
  let bin = "";
  bytes.forEach((b) => (bin += String.fromCharCode(b)));
  return btoa(bin);
}

serve(async (req) => {
  try {
    const merchant = Deno.env.get("CRYPTOMUS_MERCHANT");
    const key = Deno.env.get("CRYPTOMUS_API_KEY");
    if (!merchant || !key) return new Response("not configured", { status: 200 });

    const data = await req.json().catch(() => ({}));
    const orderId = String(data.order_id || "");
    const uuid = String(data.uuid || "");
    if (!orderId && !uuid) return new Response("ignored", { status: 200 });

    // Re-vérification côté serveur (source de vérité)
    const infoBody = JSON.stringify(uuid ? { uuid } : { order_id: orderId });
    const sign = md5(b64(infoBody) + key);
    const r = await fetch("https://api.cryptomus.com/v1/payment/info", {
      method: "POST",
      headers: { "merchant": merchant, "sign": sign, "Content-Type": "application/json" },
      body: infoBody,
    });
    const info = await r.json();
    const status = String(info?.result?.status || "");
    const realOrder = String(info?.result?.order_id || orderId);

    const PAID = ["paid", "paid_over"];
    if (!PAID.includes(status)) return new Response("pending:" + status, { status: 200 });

    const [uid, plan] = realOrder.split("|");
    if (!uid || !plan || plan === "test") return new Response("ok", { status: 200 });

    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
    const now = new Date();
    const end = new Date(now);
    end.setMonth(end.getMonth() + 1); // plan mensuel
    const row = {
      plan, billing: "monthly", status: "active", provider: "cryptomus",
      currency: "USD", cancel_at_period_end: false,
      current_period_end: end.toISOString(), updated_at: now.toISOString(),
    };
    const { data: ex } = await admin.from("subscriptions").select("id").eq("user_id", uid).limit(1);
    if (ex && ex.length) await admin.from("subscriptions").update(row).eq("user_id", uid);
    else await admin.from("subscriptions").insert({ user_id: uid, ...row });

    return new Response("ok", { status: 200 });
  } catch (e) {
    return new Response("err:" + String((e as Error)?.message || e), { status: 200 });
  }
});
