// Endpoint de diagnostic désactivé (neutralisé après usage). Ne renvoie rien.
Deno.serve(() => new Response("gone", { status: 410 }));
