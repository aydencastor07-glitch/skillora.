/**
 * POST { action: 'accounts', timezoneOffset } → { accounts: Account[] }
 * Connected accounts come from Post for Me; their stats from SociaVault.
 */
import { error, json, serve } from '../_shared/http.ts';
import { listAccounts, toQuaxPlatform } from '../_shared/postforme.ts';
import { fetchAccount } from '../_shared/sociavault.ts';

serve(async (body) => {
  if (body.action !== 'accounts') return error('Action inconnue');

  const timezoneOffset = Number(body.timezoneOffset ?? 0) || 0;
  const connected = await listAccounts();
  const results = await Promise.allSettled(
    connected.map((a) => {
      const platform = toQuaxPlatform(a.platform);
      if (!platform || !a.username) return Promise.reject(new Error(`Compte ${a.id} ignoré`));
      return fetchAccount(platform, a.username, a.id, timezoneOffset);
    }),
  );
  for (const r of results) if (r.status === 'rejected') console.warn(r.reason);

  return json({ accounts: results.flatMap((r) => (r.status === 'fulfilled' ? [r.value] : [])) });
});
