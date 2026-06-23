// SKILLORA — whop-webhook : active/désactive l'abonnement selon les events Whop.
// verify_jwt = false : Whop appelle sans token Supabase. Sécurité = signature Whop
// (Standard Webhooks spec : headers webhook-id / webhook-timestamp / webhook-signature).
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const REFERRAL_PCT: Record<string, number> = { starter: 0.20, growth: 0.25, elite: 0.30 };

// Mapping plan Whop (plan_*) -> plan Skillora, utilisé seulement si metadata.plan
// est absent. À remplir avec les mêmes IDs que dans whop-checkout (facultatif).
const PLAN_BY_WHOP_ID: Record<string, { plan: string; billing: string }> = {
  "plan_oDCfFU7lLws8B": { plan: "starter", billing: "monthly" },
  "plan_ecJbjbjlfxXOi": { plan: "starter", billing: "yearly"  },
  "plan_PJc5IYlQNCBBs": { plan: "growth",  billing: "monthly" },
  "plan_KZunBJm7YjLzC": { plan: "growth",  billing: "yearly"  },
  "plan_L776Rw5hJcIin": { plan: "elite",   billing: "monthly" },
  "plan_JePPrOlGknPbM": { plan: "elite",   billing: "yearly"  },
};

Deno.serve(async (req) => {
  if (req.method !== "POST") return new Response("Method not allowed", { status: 405 });
  try {
    const SECRET = Deno.env.get("WHOP_WEBHOOK_SECRET");
    if (!SECRET) return new Response("Webhook non configuré", { status: 500 });

    const rawBody = await req.text();
    const ok = await verifyWhopSignature(req.headers, rawBody, SECRET);
    if (!ok) { console.log("[whop] signature invalide"); return new Response("Signature invalide", { status: 400 }); }

    const event = JSON.parse(rawBody);
    const action = (event.action || event.type || "").toString();
    const data = event.data || {};
    console.log("[whop] reçu:", action);

    const admin = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    const meta = data.metadata || {};
    const planId = data.plan_id || data.plan || "";
    const mapped = PLAN_BY_WHOP_ID[planId];
    const plan = (meta.plan || mapped?.plan || "").toString().toLowerCase();
    const billing = (meta.billing || mapped?.billing || "monthly").toString().toLowerCase();
    const membershipId = data.id || data.membership_id || null;
    const whopUserId = data.user_id || (typeof data.user === "string" ? data.user : data.user?.id) || null;

    async function resolveUserId(): Promise<string | null> {
      if (meta.user_id) return meta.user_id;
      if (membershipId) {
        const { data: row } = await admin.from("subscriptions")
          .select("user_id").eq("whop_membership_id", membershipId).maybeSingle();
        if (row?.user_id) return row.user_id;
      }
      const email = meta.email || data.email || data.user?.email;
      if (email) {
        const { data: p } = await admin.from("profiles").select("id").eq("email", email).maybeSingle();
        if (p?.id) return p.id;
      }
      return null;
    }

    // Noms d'events selon la version d'API Whop (V1 = underscores, V2 = points)
    const VALID = [
      "membership.went_valid", "membership_activated", "membership_went_valid",
      "membership.metadata_updated", "membership_metadata_updated",
      "payment.succeeded", "payment_succeeded",
    ];
    const INVALID = [
      "membership.went_invalid", "membership_deactivated", "membership_went_invalid",
      "membership.cancelled", "membership_canceled", "membership_cancelled",
      "membership.expired", "membership_expired", "membership.deleted", "membership_deleted",
    ];

    if (VALID.includes(action)) {
      const userId = await resolveUserId();
      if (userId) {
        await admin.from("subscriptions").upsert({
          user_id: userId,
          plan: plan || "starter",
          billing,
          status: "active",
          currency: "usd",
          whop_membership_id: membershipId,
          whop_user_id: whopUserId,
          updated_at: new Date().toISOString(),
        }, { onConflict: "user_id" });
        console.log("[whop]", action, "-> plan", plan, "user", userId);
        await recordReferral(admin, userId, plan || "starter");
      } else {
        console.log("[whop]", action, "SANS user (membership:", membershipId, ")");
      }
    }
    else if (INVALID.includes(action)) {
      const userId = await resolveUserId();
      const patch = { plan: "none", status: "canceled", updated_at: new Date().toISOString() };
      if (userId) await admin.from("subscriptions").update(patch).eq("user_id", userId);
      else if (membershipId) await admin.from("subscriptions").update(patch).eq("whop_membership_id", membershipId);
      console.log("[whop]", action, membershipId);
    }

    return new Response(JSON.stringify({ received: true }), {
      status: 200, headers: { "Content-Type": "application/json" },
    });
  } catch (e) {
    console.log("[whop] erreur:", e?.message ?? String(e));
    return new Response("Erreur: " + (e?.message ?? String(e)), { status: 400 });
  }
});

// Parrainage : marque la conversion au 1er paiement du filleul.
// (Le crédit monétaire se fait via Whop ; on enregistre la conversion ici.)
async function recordReferral(admin: any, referredUserId: string, plan: string) {
  try {
    const { data: ref } = await admin.from("referrals")
      .select("*").eq("referred_id", referredUserId).eq("rewarded", false).maybeSingle();
    if (!ref || !ref.referrer_id || ref.referrer_id === referredUserId) return;
    const pct = REFERRAL_PCT[(plan || "").toLowerCase()] ?? 0.20;
    await admin.from("referrals").update({
      status: "converted",
      plan,
      reward_cents: null,
      rewarded: false,
      converted_at: new Date().toISOString(),
    }).eq("id", ref.id);
    console.log("[whop] parrainage converti (crédit Whop manuel) pct", Math.round(pct * 100));
  } catch (e) { console.log("[whop] referral err:", e?.message ?? String(e)); }
}

// ── Vérification de signature (Standard Webhooks + fallback legacy) ───────────
async function verifyWhopSignature(headers: Headers, payload: string, secret: string): Promise<boolean> {
  try {
    const id = headers.get("webhook-id");
    const ts = headers.get("webhook-timestamp");
    const sigHeader = headers.get("webhook-signature");
    if (id && ts && sigHeader) {
      const keyB64 = secret.startsWith("whsec_") ? secret.slice(6) : secret;
      const keyBytes = Uint8Array.from(atob(keyB64), (c) => c.charCodeAt(0));
      const enc = new TextEncoder();
      const key = await crypto.subtle.importKey("raw", keyBytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
      const signed = `${id}.${ts}.${payload}`;
      const buf = await crypto.subtle.sign("HMAC", key, enc.encode(signed));
      const expected = btoa(String.fromCharCode(...new Uint8Array(buf)));
      const sigs = sigHeader.split(" ").map((s) => (s.includes(",") ? s.split(",")[1] : s));
      return sigs.some((s) => timingSafeEqual(s, expected));
    }
    // Legacy : header X-Whop-Signature = HMAC-SHA256(raw body) en hex.
    const legacy = headers.get("x-whop-signature");
    if (legacy) {
      const enc = new TextEncoder();
      const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
      const buf = await crypto.subtle.sign("HMAC", key, enc.encode(payload));
      const expected = Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
      return timingSafeEqual(legacy.replace(/^sha256=/, ""), expected);
    }
    return false;
  } catch (e) { console.log("[whop] verif err:", e?.message ?? String(e)); return false; }
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}
