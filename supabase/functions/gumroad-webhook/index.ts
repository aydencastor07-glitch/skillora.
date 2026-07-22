// SKILLORA — webhook Gumroad (Ping). À chaque vente/remboursement, Gumroad
// POST ici (form-encoded). On sécurise par un token secret dans l'URL, on
// identifie l'utilisateur via url_params[skillora_uid] (sinon l'email), et on
// active/désactive l'abonnement. Le client paie par carte sur Gumroad ;
// Skillora est payé sur son PayPal Finlande.
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// Token partagé : présent dans l'URL du Ping configurée dans Gumroad.
const PING_TOKEN = "gr_sk_9f3k2m7qz8x";

serve(async (req) => {
  try {
    const url = new URL(req.url);
    if (url.searchParams.get("token") !== PING_TOKEN) {
      return new Response("forbidden", { status: 200 }); // 200 pour ne pas révéler
    }

    const raw = await req.text();
    const p = new URLSearchParams(raw);
    const email = (p.get("email") || "").trim().toLowerCase();
    const uid = (p.get("url_params[skillora_uid]") || p.get("skillora_uid") || "").trim();
    const refunded = (p.get("refunded") === "true") || (p.get("dispute") === "true");
    const cancelled = p.get("cancelled") === "true";

    if (!uid && !email) return new Response("no-user", { status: 200 });

    const admin = createClient(
      Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
      { auth: { persistSession: false } });

    // Retrouver l'utilisateur (priorité à l'uid passé au checkout)
    let userId = uid;
    if (!userId && email) {
      const { data } = await admin.from("profiles").select("id").eq("email", email).limit(1);
      if (data && data.length) userId = data[0].id;
    }
    if (!userId) return new Response("user-not-found", { status: 200 });

    const now = new Date();
    if (refunded || cancelled) {
      await admin.from("subscriptions")
        .update({ status: "canceled", cancel_at_period_end: true, updated_at: now.toISOString() })
        .eq("user_id", userId);
      return new Response("ok-cancel", { status: 200 });
    }

    // Vente : active le plan Pro pour +1 mois
    const end = new Date(now); end.setMonth(end.getMonth() + 1);
    const row = {
      plan: "pro", billing: "monthly", status: "active", provider: "gumroad",
      currency: "USD", cancel_at_period_end: false,
      current_period_end: end.toISOString(), updated_at: now.toISOString(),
    };
    const { data: ex } = await admin.from("subscriptions").select("id").eq("user_id", userId).limit(1);
    if (ex && ex.length) await admin.from("subscriptions").update(row).eq("user_id", userId);
    else await admin.from("subscriptions").insert({ user_id: userId, ...row });

    return new Response("ok", { status: 200 });
  } catch (e) {
    return new Response("err:" + String((e as Error)?.message || e), { status: 200 });
  }
});
