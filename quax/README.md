# Quax — social media management

Application mobile (iOS / Android, + web) pour piloter tous ses réseaux sociaux au même endroit :
statistiques, publication instantanée ou programmée, publication « au meilleur moment » et un assistant IA.

Construite avec **Expo (React Native) + Expo Router + TypeScript**.

## Fonctionnalités

| Écran | Ce qu'on y fait |
| --- | --- |
| **Accueil** | Vue globale (audience totale, vues, likes, courbe 30 j, prochain meilleur moment) puis **swipe gauche/droite** pour passer d'un réseau à l'autre. Chaque page réseau = un « profil amélioré » : logo et nom du réseau, photo de profil, pseudo, bio, abonnés / likes / vues avec leur évolution, graphique, meilleur moment, top contenus — le tout aux **couleurs du réseau** fusionnées avec le fond. |
| **Stats** | Filtre par réseau, période 7 / 30 jours, nouveaux abonnés, vues par jour, engagement, carte de chaleur de l'activité de l'audience, répartition de l'audience, top contenus. |
| **Publier (+)** | Photo/vidéo + légende (avec « Écrire avec l'IA »), choix des réseaux, puis **Maintenant**, **Programmer** (jour + heure) ou **Meilleur moment** (calculé automatiquement). |
| **Planning** | Publications à venir (annulables) et historique, semaine en un coup d'œil. |
| **Quax AI** | Chat en temps réel (réponse en streaming) qui connaît les stats de l'utilisateur. |
| **Mes comptes** | Connexion / retrait d'Instagram, TikTok, YouTube, X, Facebook, LinkedIn, Threads, Snapchat, Pinterest. |

## Lancer l'app

```bash
cd quax
npm install
npx expo start        # puis scanner le QR code avec Expo Go, ou touche "w" pour le web
```

Sans configuration, l'app tourne en **mode démo** (badge « DÉMO ») : comptes, stats, publication et IA
sont simulés localement. On peut donc tout designer et tester sans payer d'API.

Vérifications : `npm run typecheck` et `npm run lint`.

## Architecture

```
quax/
├── src/
│   ├── app/                  # écrans (Expo Router)
│   │   ├── (tabs)/           # Accueil, Stats, Publier, Planning, Quax AI
│   │   └── accounts.tsx      # connexion des réseaux (modal)
│   ├── components/           # page profil, graphiques, barre d'onglets…
│   ├── constants/            # thème + définition des réseaux (couleurs, logos)
│   ├── lib/                  # types, formatage FR, moteur « meilleur moment », données démo
│   ├── services/             # api.ts = seul point de contact avec le backend (ou la démo)
│   └── store/                # état global (comptes, posts, chat)
└── supabase/functions/       # backend : garde les clés API secrètes
    ├── quax-social/          # comptes connectés + stats (Post for Me + SociaVault)
    ├── quax-publish/         # connexion OAuth, publication, programmation (Post for Me)
    └── quax-ai/              # chat IA en streaming (Claude)
```

Les clés API ne sont **jamais** dans l'app : le téléphone appelle les Edge Functions, qui appellent les API.

### « Meilleur moment »

`src/lib/best-time.ts` : pour chaque compte, on a une matrice 7 jours × 24 h de l'engagement moyen
(calculée côté serveur à partir des posts récents : likes + commentaires + partages rapportés aux vues,
selon le jour/l'heure de publication). Les comptes choisis sont combinés (pondérés par taille d'audience)
et on prend le créneau le plus fort des 7 prochains jours, en favorisant légèrement les créneaux proches.

## Brancher les vraies API (quand tu auras les clés)

1. Créer un projet Supabase dédié à Quax, puis depuis `quax/` :
   ```bash
   supabase link --project-ref <ref-quax>
   supabase secrets set ANTHROPIC_API_KEY=... POSTFORME_API_KEY=... SOCIAVAULT_API_KEY=...
   supabase functions deploy quax-ai quax-publish quax-social
   ```
2. Copier `.env.example` en `.env.local` et remplir `EXPO_PUBLIC_QUAX_API_URL`
   (`https://<ref>.supabase.co/functions/v1`) et `EXPO_PUBLIC_QUAX_ANON_KEY`.
3. Relancer `npx expo start` : le badge « DÉMO » disparaît.

| Service | Rôle | Fichier à ajuster si leur API diffère |
| --- | --- | --- |
| **Post for Me** | Connexion des comptes (OAuth), publication, programmation | `supabase/functions/_shared/postforme.ts` |
| **SociaVault** | Scraping des profils et des posts (abonnés, vues, likes) | `supabase/functions/_shared/sociavault.ts` |
| **Claude (Anthropic)** | Quax AI (modèle `claude-opus-5`, réponses en streaming) | `supabase/functions/quax-ai/index.ts` |

> Les endpoints Post for Me / SociaVault ont été écrits d'après leur documentation publique mais
> n'ont pas pu être testés sans clé : à vérifier au moment du branchement (tout est isolé dans ces 2 fichiers).

## Prochaines étapes

- **Comptes utilisateurs** (Supabase Auth) pour que chaque utilisateur ait ses propres réseaux.
- **Historique des abonnés** : un job quotidien (cron Supabase) qui enregistre les stats de chaque compte
  dans une table, pour de vraies courbes d'évolution (le scraping ne donne que l'instant présent).
- **Upload des médias** vers Supabase Storage pour les envoyer à Post for Me (URL publique).
- Persistance locale (brouillons, historique du chat) et notifications push quand un post est publié.
- Build des apps store avec EAS (`npx eas-cli@latest build`).
