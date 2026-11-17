// Design tokens of the final Figma design ("Lumière v2" variables and text styles).
import { TextStyle } from 'react-native';

export const colors = {
  canvas: '#FFF8F6',
  surface: '#FFFFFF',
  tint: '#FCEDEF',
  tintStrong: '#F7D5DD',
  roseStrong: '#F4B9C8',
  accent: '#BF3F68',
  accentDeep: '#9E2F53',
  ink: '#2A1E22',
  ink2: '#6E5E63',
  ink3: '#A39499',
  line: '#F0E3E4',
  good: '#356B4E',
  goodTint: '#DCF2E5',
  caution: '#8A5A00',
  cautionTint: '#FBF0DE',
  flag: '#B83A3A',
  flagTint: '#FBE7E5',
  night: '#191214',
  white: '#FFFFFF',
  // pastel family: each pastel has its ink colour for text and icons on it
  peach: '#FFE7DA',
  peachInk: '#9A4521',
  butter: '#FFF2C7',
  butterInk: '#735400',
  mint: '#DCF2E5',
  mintInk: '#2C6447',
  lilac: '#EEE6FA',
  lilacInk: '#634594',
  sky: '#E0EDFB',
  skyInk: '#2A5A88',
} as const;

export const pastel = {
  rose: { bg: colors.tint, ink: colors.accentDeep },
  peach: { bg: colors.peach, ink: colors.peachInk },
  butter: { bg: colors.butter, ink: colors.butterInk },
  mint: { bg: colors.mint, ink: colors.mintInk },
  lilac: { bg: colors.lilac, ink: colors.lilacInk },
  sky: { bg: colors.sky, ink: colors.skyInk },
} as const;

export type PastelName = keyof typeof pastel;

export const fonts = {
  serif: 'YoungSerif_400Regular',
  regular: 'HankenGrotesk_400Regular',
  medium: 'HankenGrotesk_500Medium',
  semibold: 'HankenGrotesk_600SemiBold',
} as const;

export const type = {
  display: { fontFamily: fonts.serif, fontSize: 32, lineHeight: 38, color: colors.ink },
  title: { fontFamily: fonts.serif, fontSize: 26, lineHeight: 32, color: colors.ink },
  headline: { fontFamily: fonts.serif, fontSize: 20, lineHeight: 26, color: colors.ink },
  figure: { fontFamily: fonts.serif, fontSize: 28, lineHeight: 32 },
  bodyL: { fontFamily: fonts.regular, fontSize: 17, lineHeight: 24, color: colors.ink2 },
  body: { fontFamily: fonts.regular, fontSize: 15, lineHeight: 22, color: colors.ink },
  bodyStrong: { fontFamily: fonts.semibold, fontSize: 15, lineHeight: 22, color: colors.ink },
  label: { fontFamily: fonts.medium, fontSize: 13, lineHeight: 18, color: colors.ink2 },
  section: { fontFamily: fonts.semibold, fontSize: 13, lineHeight: 18, color: colors.ink2 },
  caption: { fontFamily: fonts.regular, fontSize: 12, lineHeight: 16, color: colors.ink2 },
  button: { fontFamily: fonts.semibold, fontSize: 16, lineHeight: 20 },
  tab: { fontFamily: fonts.medium, fontSize: 10, lineHeight: 12 },
} satisfies Record<string, TextStyle>;

export const space = { s4: 4, s8: 8, s12: 12, s16: 16, s20: 20, s24: 24, s28: 28, s32: 32 } as const;
export const radius = { sm: 10, md: 14, lg: 20, xl: 28, pill: 99 } as const;
