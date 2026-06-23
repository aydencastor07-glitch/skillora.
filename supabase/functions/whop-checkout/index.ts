// SKILLORA — whop-checkout : crée une session de paiement Whop (mensuel OU annuel)
// Mirroir de create-checkout (Stripe), mais via l'API Whop (Merchant of Record).
// Doc : POST https://api.whop.com/api/v2/checkout_sessions
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

// ── Plans Whop (plan_*) ──────────────────────────────────────────────────────
// À REMPLIR une fois les produits créés dans le dashboard Whop
// (Produits → un produit par plan → Pricing → un plan mensuel + un plan annuel).
// Ce sont des IDs PUBLICS (pas des secrets) : on peut les mettre directement ici.
const WHOP_PLANS: Record<string, { m: string; y: string }> = {
  starter: { m: "plan_oDCfFU7lLws8B", y: "plan_ecJbjbjlfxXOi" },
  growth:  { m: "plan_PJc5IYlQNCBBs", y: "plan_KZunBJm7YjLzC" },
  elite:   { m: "plan_L776Rw5hJcIin", y: "plan_JePPrOlGknPbM" },
};

function isYearly(billing: string): boolean {
  return billing === "yearly" || billing === "annual" || billing === "year";
}

function planFor(plan: string, billing: string): string {
  const e = WHOP_PLANS[plan];
  if (!e) return "";
  const id = isYearly(billing) ? e.y : e.m;
  // tant que ce n'est pas un vrai plan_xxx, on considère "non configuré"
  return id.startsWith("plan_") ? id : "";
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const WHOP_API_KEY = Deno.env.get("WHOP_API_KEY");
    if (!WHOP_API_KEY) return j({ error: "Whop non configuré (clé API manquante)." }, 500);

    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_ANON_KEY")!,
      { global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } } },
    );
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return j({ error: "Non authentifié." }, 401);

    const body = await req.json().catch(() => ({}));
    const plan = (body.plan ?? "").toLowerCase().trim();
    const billing = (body.billing ?? "monthly").toLowerCase().trim();
    const planId = planFor(plan, billing);
    if (!planId) {
      return j({ error: "Plan/période invalide ou non configuré: " + plan + " / " + billing }, 400);
    }

    const origin = req.headers.get("origin") ?? "https://skillora.me";

    // Crée la session de checkout Whop avec les métadonnées qui relient
    // le futur abonnement à cet utilisateur Skillora.
    const res = await fetch("https://api.whop.com/api/v2/checkout_sessions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${WHOP_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        plan_id: planId,
        redirect_url: `${origin}/app.html?checkout=success`,
        metadata: {
          user_id: user.id,
          plan: plan,
          billing: isYearly(billing) ? "yearly" : "monthly",
          email: user.email ?? "",
        },
      }),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      return j({ error: "Whop checkout: " + (data?.message || data?.error || `HTTP ${res.status}`) }, 500);
    }

    const url = data.purchase_url || (data.id ? `https://whop.com/checkout/${data.id}` : "");
    if (!url) return j({ error: "Whop: URL de paiement introuvable." }, 500);

    return j({ success: true, url }, 200);
  } catch (e) {
    return j({ error: "Erreur serveur: " + (e?.message ?? String(e)) }, 500);
  }
});

function j(o: unknown, s = 200) {
  return new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });
}
