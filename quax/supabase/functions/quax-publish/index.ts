/**
 * POST { action: 'connect', platform }                   → { url }   (OAuth page of the network)
 * POST { action: 'disconnect', accountId }               → { ok }
 * POST { action: 'post', caption, accountIds, mediaUrls?, scheduledAt? } → { id }
 */
import { error, json, serve } from '../_shared/http.ts';
import { authUrl, createPost, disconnect } from '../_shared/postforme.ts';
import type { PlatformId } from '../_shared/types.ts';

serve(async (body) => {
  switch (body.action) {
    case 'connect':
      return json({ url: await authUrl(body.platform as PlatformId) });

    case 'disconnect':
      await disconnect(String(body.accountId));
      return json({ ok: true });

    case 'post': {
      const accountIds = (body.accountIds as string[] | undefined) ?? [];
      if (accountIds.length === 0) return error('Choisis au moins un compte.');
      const scheduledAt = body.scheduledAt ? String(body.scheduledAt) : undefined;
      if (scheduledAt && isNaN(Date.parse(scheduledAt))) return error('Date de programmation invalide.');
      return json(
        await createPost({
          caption: String(body.caption ?? ''),
          accountIds,
          mediaUrls: body.mediaUrls as string[] | undefined,
          scheduledAt,
        }),
      );
    }

    default:
      return error('Action inconnue');
  }
});
