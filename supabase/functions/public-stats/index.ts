// SKILLORA — statistiques consultables SANS CONNEXION, par un lien secret.
// ========================================================================
// La page /stats/ envoie la cle du lien ; seule son empreinte SHA-256 est ici,
// donc lire ce code ne suffit pas pour ouvrir les chiffres. Aucune donnee
// personnelle n'est renvoyee : ni email, ni nom — seulement des totaux.
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const EMPREINTE = "bdc6b46cb6a4b4e49b656f0e807106375b4975fd88ebe742fc02583536589873";
const PRIX_MENSUEL = 30;

function json(o: unknown, s = 200) {
  return new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });
}
async function sha(s: string) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
/* Meme decoupage des periodes que l'espace dev (admin-stats). */
function periode(p: Record<string, unknown>) {
  const now = new Date();
  const t = String(p.periode || "30j");
  const fin = new Date(now); fin.setUTCHours(0, 0, 0, 0); fin.setUTCDate(fin.getUTCDate() + 1);
  if (t === "tout") return { from: new Date("2020-01-01"), to: fin };
  const jours: Record<string, number> = { "auj": 1, "7j": 7, "30j": 30, "90j": 90, "365j": 365 };
  const n = jours[t] ?? 30;
  const deb = new Date(now); deb.setUTCHours(0, 0, 0, 0); deb.setUTCDate(deb.getUTCDate() - (n - 1));
  return { from: deb, to: fin };
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const body = JSON.parse(await req.text() || "{}");
    if (await sha(String(body.k || "")) !== EMPREINTE) return json({ success: false, error: "Lien invalide." }, 403);
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
    const { from, to } = periode(body);
    const f = from.toISOString(), t = to.toISOString();
    const [site, ebook, pubs] = await Promise.all([
      admin.rpc("admin_overview", { p_from: f, p_to: t }),
      admin.rpc("admin_ebook", { p_product: "gesetzbuch", p_from: f, p_to: t }),
      admin.rpc("admin_pubs", { p_from: f, p_to: t }),
    ]);
    if (site.error) return json({ success: false, error: site.error.message }, 500);
    const campagnes = ((pubs.data as Record<string, unknown>[]) || []).map((c) => ({
      nom: c.nom || c.code, plateforme: c.plateforme, clics: Number(c.clics) || 0,
      inscrits: Number(c.inscrits) || 0, payants: Number(c.payants) || 0,
    }));
    return json({
      success: true, periode: { debut: f, fin: t, type: String(body.periode || "30j") },
      site: site.data, ebook: ebook.data || null, campagnes, prix_mensuel: PRIX_MENSUEL,
      genere_le: new Date().toISOString(),
    });
  } catch (e) {
    return json({ success: false, error: String((e as Error)?.message || e) }, 500);
  }
});
