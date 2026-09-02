/**
 * Below are the colors that are used in the app. The colors are defined in the light and dark mode.
 * There are many other ways to style your app. For example, [Nativewind](https://www.nativewind.dev/), [Tamagui](https://tamagui.dev/), [unistyles](https://reactnativeunistyles.vercel.app), etc.
 */

import '@/global.css';

import { Platform } from 'react-native';

export const Colors = {
  light: {
    text: '#000000',
    background: '#ffffff',
    backgroundElement: '#F0F0F3',
    backgroundSelected: '#E0E1E6',
    textSecondary: '#60646C',
  },
  dark: {
    text: '#ffffff',
    background: '#000000',
    backgroundElement: '#212225',
    backgroundSelected: '#2E3135',
    textSecondary: '#B0B4BA',
  },
} as const;

export type ThemeColor = keyof typeof Colors.light & keyof typeof Colors.dark;

export const Fonts = Platform.select({
  ios: {
    /** iOS `UIFontDescriptorSystemDesignDefault` */
    sans: 'system-ui',
    /** iOS `UIFontDescriptorSystemDesignSerif` */
    serif: 'ui-serif',
    /** iOS `UIFontDescriptorSystemDesignRounded` */
    rounded: 'ui-rounded',
    /** iOS `UIFontDescriptorSystemDesignMonospaced` */
    mono: 'ui-monospace',
  },
  default: {
    sans: 'normal',
    serif: 'serif',
    rounded: 'normal',
    mono: 'monospace',
  },
  web: {
    sans: 'var(--font-display)',
    serif: 'var(--font-serif)',
    rounded: 'var(--font-rounded)',
    mono: 'var(--font-mono)',
  },
});

export const Spacing = {
  half: 2,
  one: 4,
  two: 8,
  three: 16,
  four: 24,
  five: 32,
  six: 64,
} as const;

export const BottomTabInset = Platform.select({ ios: 50, android: 80 }) ?? 0;
export const MaxContentWidth = 800;

/** CupPit 브랜드 색상. */
export const Brand = {
  primary: '#0E7C66',
  primaryDark: '#0A5A4A',
  primarySoft: '#E3F2EE',
  accent: '#F2A93B',
  danger: '#D24B3E',
  dangerSoft: '#FBE9E7',
  border: '#E3E5E8',
  muted: '#6B7280',
} as const;

/** 지도 마커 색상: 출처가 기준이다. 공식 등록은 파란색, 사용자 등록은 초록색, 신고로 검토중이면 주황색. */
export const MarkerColors = {
  official: '#2B7FFF',
  user: '#18A957',
  reviewing: '#F2A93B',
} as const;

/** AI 신뢰도 점수별 표시 색상과 라벨. */
export const ReliabilityStyles = {
  high: { color: '#18A957', background: '#E7F7EE', label: '이용 가능성 높음', emoji: '🟢' },
  medium: { color: '#C77700', background: '#FDF3E2', label: '이용 가능성 보통', emoji: '🟡' },
  low: { color: '#D24B3E', background: '#FBE9E7', label: '이용 가능성 낮음', emoji: '🔴' },
} as const;
