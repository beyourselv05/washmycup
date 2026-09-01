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
      </Stack>
    </LocationsProvider>
  );
}
