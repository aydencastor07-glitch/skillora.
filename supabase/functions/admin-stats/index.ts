// SKILLORA — poste de pilotage du proprietaire.
// ============================================
// Une seule porte d'entree pour tout l'espace dev : vue d'ensemble, liste des
// membres, entonnoir publicitaire, gestion des liens de campagne.
//
// SECURITE : l'email du jeton doit figurer dans OWNERS. Tout est ensuite lu
// avec la cle de service — jamais depuis le navigateur, ou n'importe qui
// pourrait recuperer la liste des membres.
//
// Les agregats lourds sont calcules EN BASE (fonctions admin_*) : a mille
// membres, tout telecharger pour compter en JavaScript deviendrait lent.
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const OWNERS = ["aydencastor07@gmail.com", "aydencastor1020@gmail.com"];
const PRIX_MENSUEL = 30;   // USD — l'offre unique

function json(o: unknown, s = 200) {
  return new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });
}

/* Bornes de la periode demandee. « mois » accepte « 2026-07 » pour revenir
   sur un mois precis. */
function periode(p: Record<string, unknown>) {
  const now = new Date();
  const t = String(p.periode || "30j");
  if (t === "mois" && /^\d{4}-\d{2}$/.test(String(p.mois || ""))) {
    const [a, m] = String(p.mois).split("-").map(Number);
    return { from: new Date(Date.UTC(a, m - 1, 1)), to: new Date(Date.UTC(a, m, 1)) };
  }
  const fin = new Date(now.getTime() + 86400000);
  if (t === "tout") return { from: new Date("2020-01-01"), to: fin };
  const jours: Record<string, number> = { "auj": 1, "7j": 7, "30j": 30, "90j": 90, "365j": 365 };
  const n = jours[t] ?? 30;
  const deb = new Date(now); deb.setUTCHours(0, 0, 0, 0);
  deb.setUTCDate(deb.getUTCDate() - (n - 1));
  return { from: deb, to: fin };
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
    const jwt = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "").trim();
    const { data: u } = await admin.auth.getUser(jwt);
    const email = (u?.user?.email || "").toLowerCase();
    if (!OWNERS.includes(email)) return json({ success: false, error: "Réservé au propriétaire." }, 403);

    const body = await req.json().catch(() => ({} as Record<string, unknown>));
    const action = String(body.action || "tableau");
    const { from, to } = periode(body);

    // ── Creer un lien publicitaire ────────────────────────────────────────
    if (action === "pub_creer") {
      const code = String(body.code || "").trim().toLowerCase().slice(0, 60);
      if (!/^[a-z0-9._-]{2,60}$/.test(code)) {
        return json({ success: false, error: "Le code ne peut contenir que des lettres, chiffres, tirets et points." }, 400);
      }
      const { data, error } = await admin.from("ad_campaigns").insert({
        code,
        name: String(body.nom || code).slice(0, 120),
        platform: String(body.plateforme || "other").slice(0, 30),
        destination: String(body.destination || "/").slice(0, 120),
        // Le CIBLAGE fait partie du lien : meme plateforme mais pays ou age
        // different = lien different. C'est la seule facon de savoir quel
        // ciblage fonctionne, et pas seulement quelle plateforme.
        country: body.pays ? String(body.pays).slice(0, 60) : null,
        age_min: body.age_min != null ? Number(body.age_min) : null,
        age_max: body.age_max != null ? Number(body.age_max) : null,
        creative_type: body.creatif ? String(body.creatif).slice(0, 10) : null,
        creative_url: body.creatif_url ? String(body.creatif_url).slice(0, 400) : null,
        note: body.note ? String(body.note).slice(0, 500) : null,
      }).select("id, code").single();
      if (error) {
        const dup = String(error.message || "").includes("duplicate");
        return json({ success: false, error: dup ? "Ce code existe déjà — choisis-en un autre." : error.message }, 400);
      }
      return json({ success: true, campagne: data });
    }

    if (action === "pub_maj") {
      const patch: Record<string, unknown> = {};
      if (body.nom !== undefined) patch.name = String(body.nom).slice(0, 120);
      if (body.plateforme !== undefined) patch.platform = String(body.plateforme).slice(0, 30);
      if (body.note !== undefined) patch.note = String(body.note).slice(0, 500);
      if (body.pays !== undefined) patch.country = body.pays ? String(body.pays).slice(0, 60) : null;
      if (body.age_min !== undefined) patch.age_min = body.age_min != null ? Number(body.age_min) : null;
      if (body.age_max !== undefined) patch.age_max = body.age_max != null ? Number(body.age_max) : null;
      if (body.creatif !== undefined) patch.creative_type = body.creatif ? String(body.creatif).slice(0, 10) : null;
      if (body.creatif_url !== undefined) patch.creative_url = body.creatif_url ? String(body.creatif_url).slice(0, 400) : null;
      if (body.archive !== undefined) patch.archived = !!body.archive;
      if (!Object.keys(patch).length) return json({ success: false, error: "Rien à modifier." }, 400);
      const { error } = await admin.from("ad_campaigns").update(patch).eq("id", String(body.id));
      if (error) return json({ success: false, error: error.message }, 400);
      return json({ success: true });
    }

    if (action === "pub_supprimer") {
      const { error } = await admin.from("ad_campaigns").delete().eq("id", String(body.id));
      if (error) return json({ success: false, error: error.message }, 400);
      return json({ success: true });
    }

    // ── Liste des membres (paginee, filtrable) ────────────────────────────
    if (action === "membres") {
      const { data, error } = await admin.rpc("admin_membres", {
        p_limit: Number(body.limite) || 50,
        p_offset: Number(body.decalage) || 0,
        p_q: body.recherche ? String(body.recherche).slice(0, 80) : null,
        p_plan: String(body.plan || "tous"),
      });
      if (error) return json({ success: false, error: error.message }, 500);
      return json({ success: true, ...(data as Record<string, unknown>) });
    }

    // ── Tableau de bord complet ───────────────────────────────────────────
    const [apercu, pubs, membres] = await Promise.all([
      admin.rpc("admin_overview", { p_from: from.toISOString(), p_to: to.toISOString() }),
      admin.rpc("admin_pubs", { p_from: from.toISOString(), p_to: to.toISOString() }),
      admin.rpc("admin_membres", { p_limit: 12, p_offset: 0, p_q: null, p_plan: "tous" }),
    ]);
    if (apercu.error) return json({ success: false, error: apercu.error.message }, 500);

    // PAS DE DEPENSE ICI. Skillora ne peut pas connaitre ce qui a ete depense
    // sur Meta ou Google — l'inventer donnerait un « retour sur
    // investissement » faux, donc pire que pas de chiffre du tout. On s'en
    // tient a ce qu'on MESURE vraiment : clics, inscrits, payants, revenu.
    const campagnes = ((pubs.data as Record<string, unknown>[]) || []).map((c) => {
      const clics = Number(c.clics) || 0;
      const inscrits = Number(c.inscrits) || 0;
      const payants = Number(c.payants) || 0;
      return {
        ...c,
        revenu: payants * PRIX_MENSUEL,
        // Sur 100 clics, combien creent un compte.
        taux_inscription: clics ? +(inscrits * 100 / clics).toFixed(1) : 0,
        // Sur 100 inscrits, combien passent Pro.
        taux_paiement: inscrits ? +(payants * 100 / inscrits).toFixed(1) : 0,
      };
    });

    return json({
      success: true,
      periode: { debut: from.toISOString(), fin: to.toISOString(), type: String(body.periode || "30j") },
      apercu: apercu.data,
      campagnes,
      derniers: (membres.data as Record<string, unknown>)?.lignes || [],
      prix_mensuel: PRIX_MENSUEL,
      genere_le: new Date().toISOString(),
    });
  } catch (e) {
    return json({ success: false, error: String((e as Error)?.message || e) }, 500);
  }
});
