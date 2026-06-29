// Endpoint de diagnostic TEMPORAIRE (à supprimer après). Liste les comptes Post for Me
// d'un external_id donné, gardé par un token. Ne renvoie AUCUN secret/token d'accès.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
const PFM_BASE = "https://api.postforme.dev";
const DEBUG_TOKEN = "sk_dbg_9f3a2c7b1e";
async function pfmFetch(path: string, key: string) {
  let res = await fetch(PFM_BASE + path, { headers: { "Content-Type": "application/json", "x-post-for-me-api-key": key } });
  if (res.status === 401 || res.status === 403) res = await fetch(PFM_BASE + path, { headers: { "Content-Type": "application/json", "Authorization": "Bearer " + key } });
  return res;
}
Deno.serve(async (req) => {
  const url = new URL(req.url);
  if (url.searchParams.get("token") !== DEBUG_TOKEN) return new Response("forbidden", { status: 403 });
  const KEY = Deno.env.get("POSTFORME_API_KEY") || "";
  const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
  const email = url.searchParams.get("email");
  let uid = url.searchParams.get("uid");
  if (!uid && email) {
    try { const { data } = await admin.auth.admin.listUsers(); const u = (data?.users || []).find((x: any) => x.email === email); uid = u?.id || null; } catch (_e) { /* */ }
  }
  if (!uid) return new Response(JSON.stringify({ error: "no uid" }), { status: 400, headers: { "Content-Type": "application/json" } });
  const out: any = { uid };
  try {
    const r = await pfmFetch("/v1/social-accounts?external_id=" + encodeURIComponent(uid), KEY);
    const d = await r.json().catch(() => ({}));
    const listRaw = Array.isArray(d) ? d : (d.data || d.accounts || []);
    out.pfm_status = r.status;
    out.pfm_count = Array.isArray(listRaw) ? listRaw.length : 0;
    out.accounts = (listRaw || []).map((a: any) => ({ id: a.id, platform: a.platform, status: a.status, username: a.username, external_id: a.external_id, has_user_id: !!a.user_id }));
  } catch (e) { out.error = String(e); }
  return new Response(JSON.stringify(out, null, 2), { headers: { "Content-Type": "application/json" } });
});
