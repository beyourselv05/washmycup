import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { Brand } from '@/constants/theme';
import { LocationsProvider } from '@/context/LocationsContext';

export default function RootLayout() {
  return (
    <LocationsProvider>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerTintColor: Brand.primary,
          headerTitleStyle: { color: '#111827', fontWeight: '700' },
          headerBackButtonDisplayMode: 'minimal',
        }}>
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="location/[id]" options={{ title: '세척기 상세' }} />
        <Stack.Screen name="add-location" options={{ title: '위치 등록', presentation: 'modal' }} />
        <Stack.Screen name="review/[id]" options={{ title: '리뷰 작성', presentation: 'modal' }} />
        <Stack.Screen name="my-report" options={{ title: '내 텀블러 기록' }} />
        <Stack.Screen name="record/[id]" options={{ title: '사용 기록 남기기' }} />
      </Stack>
    </LocationsProvider>
  );
}
