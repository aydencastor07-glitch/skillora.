export const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
};

export function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  });
}

export function error(message: string, status = 400): Response {
  return json({ error: message }, status);
}

export function requireEnv(name: string): string {
  const value = Deno.env.get(name);
  if (!value) throw new Error(`Secret manquant : ${name} (supabase secrets set ${name}=...)`);
  return value;
}

/** Wraps a handler with CORS preflight + JSON error handling. */
export function serve(handler: (body: Record<string, unknown>) => Promise<Response>) {
  Deno.serve(async (req) => {
    if (req.method === 'OPTIONS') return new Response('ok', { headers: corsHeaders });
    if (req.method !== 'POST') return error('Méthode non autorisée', 405);
    try {
      const body = (await req.json().catch(() => ({}))) as Record<string, unknown>;
      return await handler(body);
    } catch (e) {
      console.error(e);
      return error(e instanceof Error ? e.message : String(e), 500);
    }
  });
}
