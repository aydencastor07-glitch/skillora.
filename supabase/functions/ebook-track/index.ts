// Enregistre ce qui se passe sur la page de vente d'un E-BOOK.
// ============================================================
// Appelee par la page du livre (gesetze/index.html), jamais bloquante :
//   view       a chaque ouverture de la page (une vue = une ouverture)
//   buy_click  clic sur un bouton « Acheter »
//   leave      le visiteur quitte la page : on ecrit le temps passe sur SA vue
// Le corps arrive en texte brut (navigator.sendBeacon ne peut pas envoyer
// d'en-tetes), d'ou le JSON.parse a la main.
// Aucun email, aucun nom, aucune adresse IP n'est stocke.
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const PRODUITS = ["gesetzbuch"];   // seuls ces livres sont comptes : personne ne peut inventer un produit
const ROBOTS = /bot|crawl|spider|slurp|preview|facebookexternalhit|whatsapp|telegram|discord|headless|lighthouse/i;

function json(o: unknown, s = 200) {
  return new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });
}

/* Le pays vient du reseau, pas du navigateur : impossible a maquiller par
   un simple reglage de langue. Supabase passe derriere Cloudflare, qui
   ajoute cf-ipcountry ; les autres en-tetes sont des filets. */
function pays(req: Request): string | null {
  for (const h of ["cf-ipcountry", "x-vercel-ip-country", "x-country-code", "x-geo-country"]) {
    const v = req.headers.get(h);
    if (v && v.length === 2 && v !== "XX") return v.toUpperCase();
  }
  return null;
}

function ville(req: Request): string | null {
  const v = req.headers.get("cf-ipcity") || req.headers.get("x-vercel-ip-city");
  return v ? decodeURIComponent(v).slice(0, 60) : null;
}

/* Appareil, systeme et navigateur, lus dans la signature du navigateur. */
function appareil(ua: string) {
  const u = (ua || "").toLowerCase();
  const tablette = /ipad|tablet|playbook|silk|(android(?!.*mobi))/.test(u);
  const mobile = /iphone|ipod|android.*mobi|windows phone|blackberry|opera mini/.test(u);
  const device = tablette ? "tablette" : mobile ? "mobile" : "desktop";
  const os = /iphone|ipad|ipod|ios/.test(u) ? "iOS"
    : /android/.test(u) ? "Android"
    : /windows/.test(u) ? "Windows"
    : /mac os|macintosh/.test(u) ? "macOS"
    : /linux/.test(u) ? "Linux" : null;
  const browser = /edg\//.test(u) ? "Edge"
    : /opr\/|opera/.test(u) ? "Opera"
    : /chrome|crios/.test(u) ? "Chrome"
    : /firefox|fxios/.test(u) ? "Firefox"
    : /safari/.test(u) ? "Safari" : null;
  return { device, os, browser };
}

/* D'ou vient le visiteur. Les navigateurs integres de TikTok et Instagram
   n'envoient souvent AUCUN referent : leur signature les trahit quand meme. */
function source(ua: string, ref: string, utm: string): string {
  if (utm) {   // ?utm_source=tiktok et le navigateur TikTok doivent tomber dans la meme case
    const k = utm.toLowerCase();
    for (const n of ["TikTok", "Instagram", "YouTube", "Facebook", "Google", "Snapchat"]) if (k.includes(n.toLowerCase())) return n;
    return utm.slice(0, 40);
  }
  const u = ua.toLowerCase();
  if (/musical_ly|bytedance|tiktok/.test(u)) return "TikTok";
  if (/instagram/.test(u)) return "Instagram";
  if (/fban|fbav|fb_iab/.test(u)) return "Facebook";
  if (/snapchat/.test(u)) return "Snapchat";
  try {
    const h = new URL(ref).hostname.replace(/^www\./, "").replace(/^(l|m|lm)\./, "");
    if (!h || h.endsWith("skillora.me")) return "direct";
    if (h.includes("tiktok")) return "TikTok";
    if (h.includes("instagram")) return "Instagram";
    if (h.includes("youtube") || h === "youtu.be") return "YouTube";
    if (h.includes("facebook")) return "Facebook";
    if (h.includes("google")) return "Google";
    return h.slice(0, 40);
  } catch { return "direct"; }
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const b = JSON.parse(await req.text() || "{}");
    const product = String(b.product || "");
    const type = String(b.type || "");
    const session = String(b.session || "").slice(0, 64);
    if (!PRODUITS.includes(product) || !session) return json({ success: false }, 400);
    const ua = req.headers.get("user-agent") || "";
    if (ROBOTS.test(ua)) return json({ success: true, bot: true });

    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });

    if (type === "leave") {
      // Temps plafonne a 30 min : un onglet oublie ne doit pas fausser la moyenne.
      const s = Math.max(0, Math.min(1800, Math.round(Number(b.seconds) || 0)));
      await admin.from("ebook_events").update({ seconds: s })
        .eq("session", session).eq("product", product).eq("type", "view");
      return json({ success: true });
    }
    if (type !== "view" && type !== "buy_click") return json({ success: false }, 400);

    const { device, os, browser } = appareil(ua);
    const referrer = String(b.referrer || "").slice(0, 300);
    await admin.from("ebook_events").insert({
      product, type, session,
      visitor: String(b.visitor || "").slice(0, 64) || null,
      country: pays(req), city: ville(req), device, os, browser,
      referrer: referrer || null,
      source: source(ua, referrer, String(b.utm || "")),
      lang: String(b.lang || "").slice(0, 12) || null,
    });
    return json({ success: true });
  } catch (e) {
    console.log("ebook-track:", String((e as Error)?.message || e));
    return json({ success: false }, 200);
  }
});
