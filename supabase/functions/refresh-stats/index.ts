// SKILLORA — refresh-stats v5 : ZÉRO scrape SociaVault (0 crédit).
// Avant : re-scrapait TOUS les comptes connectés (profil + 2 pages vidéos chacun) à chaque chargement
// du tableau de bord -> un seul "Actualiser" brûlait des crédits sur tous les comptes.
// Maintenant : on enregistre le point de courbe du jour À PARTIR DE LA DERNIÈRE ANALYSE déjà payée
// (réutilisation pure des données en base), puis on renvoie l'historique. Aucun appel externe payant.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_ANON_KEY")!,
      { global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } } },
    );
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return j({ error: "Non authentifié." }, 401);

    const today = new Date().toISOString().slice(0, 10);

    // Dernières analyses de l'utilisateur (déjà payées). On écrit le relevé du jour SANS rien re-scraper.
    const { data: analyses } = await supabase.from("analyses")
      .select("platform,username,summary,account_id,created_at")
      .eq("user_id", user.id)
      .order("created_at", { ascending: false })
      .limit(50);

    const seen = new Set();
    const refreshed = [];
    for (const a of (analyses ?? [])) {
      const s = a?.summary;
      if (!s || s.owner !== "self" || !a.username) continue;
      const uname = String(a.username).replace(/^@/, "");
      const key = (a.platform || "tiktok") + "|" + uname.toLowerCase();
      if (seen.has(key)) continue;        // une seule fois par compte = la PLUS RÉCENTE analyse
      seen.add(key);

      const hasData = (Number(s.total_views) > 0) || (Number(s.video_count) > 0) || (Number(s.audience) > 0);
      if (!hasData) continue;             // pas de chiffres exploitables -> on n'écrit pas de point vide

      const snap = {
        user_id: user.id, account_id: a.account_id ?? null, platform: a.platform, username: uname,
        followers: s.audience ?? 0,
        total_videos: s.total_published ?? s.video_count ?? 0,
        total_likes: s.profile?.total_likes ?? 0,
        total_views: s.total_views ?? 0,
        snapshot_date: today,
      };
      // Un seul point par compte et par jour : on met à jour s'il existe déjà (chiffres les plus frais), sinon on insère.
      const { data: existing } = await supabase.from("account_snapshots")
        .select("id").eq("user_id", user.id).eq("platform", a.platform)
        .ilike("username", uname).eq("snapshot_date", today).maybeSingle();
      if (existing) await supabase.from("account_snapshots").update(snap).eq("id", existing.id);
      else await supabase.from("account_snapshots").insert(snap);
      refreshed.push(uname);
    }

    // Historique 1 an pour permettre tous les filtres de période côté client.
    const { data: history } = await supabase.from("account_snapshots")
      .select("platform,username,followers,total_videos,total_likes,total_views,snapshot_date")
      .eq("user_id", user.id)
      .gte("snapshot_date", new Date(Date.now() - 365 * 864e5).toISOString().slice(0, 10))
      .order("snapshot_date", { ascending: true });

    return j({ success: true, refreshed, history: history ?? [] }, 200);
  } catch (e) {
    return j({ error: "Erreur: " + (e?.message ?? String(e)) }, 500);
  }
});

function j(o, s = 200) {
  return new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });
}
