/** Quax is dark-first: the brand colors of each network pop better on a deep background. */
export const Colors = {
  background: '#0B0B12',
  surface: '#15151F',
  surfaceRaised: '#1E1E2B',
  border: '#2A2A3A',
  text: '#F5F5FA',
  textSecondary: '#9A9AB0',
  textMuted: '#62627A',
  accent: '#7C5CFF',
  accentSoft: 'rgba(124, 92, 255, 0.16)',
  success: '#2EE59D',
  danger: '#FF4D6D',
  warning: '#FFB547',
} as const;

/** Gradient used for Quax-branded surfaces (AI, primary buttons). */
export const QuaxGradient = ['#7C5CFF', '#C04DFF', '#FF5CA8'] as const;

export const Spacing = {
  half: 2,
  one: 4,
  two: 8,
  three: 16,
  four: 24,
  five: 32,
  six: 64,
} as const;

export const Radius = {
  sm: 10,
  md: 16,
  lg: 24,
  pill: 999,
} as const;

/** Height reserved at the bottom of scroll views so content clears the floating tab bar. */
export const TabBarSpace = 110;
