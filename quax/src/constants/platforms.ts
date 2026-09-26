export type PlatformId =
  | 'instagram'
  | 'tiktok'
  | 'youtube'
  | 'x'
  | 'facebook'
  | 'linkedin'
  | 'threads'
  | 'snapchat'
  | 'pinterest';

export type Platform = {
  id: PlatformId;
  name: string;
  /** FontAwesome 6 brand glyph. */
  icon: string;
  /** Main brand color, used for accents (buttons, chart lines, badges). */
  color: string;
  /** Color used on top of `color` (e.g. Snapchat yellow needs dark text). */
  onColor: string;
  /** Background gradient of the profile page — the brand color fused into the dark app background. */
  gradient: readonly [string, string, ...string[]];
  /** Wording each network uses for its main reach metric. */
  viewsLabel: string;
};

export const PLATFORMS: Record<PlatformId, Platform> = {
  instagram: {
    id: 'instagram',
    name: 'Instagram',
    icon: 'instagram',
    color: '#E1306C',
    onColor: '#FFFFFF',
    gradient: ['#FEDA75', '#FA7E1E', '#D62976', '#962FBF', '#4F5BD5'],
    viewsLabel: 'Vues',
  },
  tiktok: {
    id: 'tiktok',
    name: 'TikTok',
    icon: 'tiktok',
    color: '#FE2C55',
    onColor: '#FFFFFF',
    gradient: ['#25F4EE', '#111118', '#FE2C55'],
    viewsLabel: 'Vues',
  },
  youtube: {
    id: 'youtube',
    name: 'YouTube',
    icon: 'youtube',
    color: '#FF0033',
    onColor: '#FFFFFF',
    gradient: ['#FF0033', '#B0001F', '#3D000B'],
    viewsLabel: 'Vues',
  },
  x: {
    id: 'x',
    name: 'X (Twitter)',
    icon: 'x-twitter',
    color: '#E7E9EA',
    onColor: '#000000',
    gradient: ['#3A3A3A', '#16181C', '#000000'],
    viewsLabel: 'Impressions',
  },
  facebook: {
    id: 'facebook',
    name: 'Facebook',
    icon: 'facebook',
    color: '#1877F2',
    onColor: '#FFFFFF',
    gradient: ['#4A9BFF', '#1877F2', '#0A3D91'],
    viewsLabel: 'Portée',
  },
  linkedin: {
    id: 'linkedin',
    name: 'LinkedIn',
    icon: 'linkedin',
    color: '#0A66C2',
    onColor: '#FFFFFF',
    gradient: ['#3D8FE0', '#0A66C2', '#063C73'],
    viewsLabel: 'Impressions',
  },
  threads: {
    id: 'threads',
    name: 'Threads',
    icon: 'threads',
    color: '#FFFFFF',
    onColor: '#000000',
    gradient: ['#5A5A5A', '#1C1C1C', '#000000'],
    viewsLabel: 'Vues',
  },
  snapchat: {
    id: 'snapchat',
    name: 'Snapchat',
    icon: 'snapchat',
    color: '#FFFC00',
    onColor: '#111111',
    gradient: ['#FFFC00', '#C9B800', '#3D3800'],
    viewsLabel: 'Vues',
  },
  pinterest: {
    id: 'pinterest',
    name: 'Pinterest',
    icon: 'pinterest',
    color: '#E60023',
    onColor: '#FFFFFF',
    gradient: ['#FF4D6A', '#E60023', '#5C000E'],
    viewsLabel: 'Impressions',
  },
};

export const PLATFORM_ORDER: PlatformId[] = [
  'instagram',
  'tiktok',
  'youtube',
  'x',
  'facebook',
  'linkedin',
  'threads',
  'snapchat',
  'pinterest',
];
