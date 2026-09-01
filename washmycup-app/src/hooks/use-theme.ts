/**
 * Learn more about light and dark modes:
 * https://docs.expo.dev/guides/color-schemes/
 */

import { Colors } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';

export function useTheme() {
  const scheme = useColorScheme();
  // 색상 모드를 못 읽는 경우(null/undefined)가 있어 밝은 테마를 기본으로 쓴다.
  return Colors[scheme ?? 'light'];
}
