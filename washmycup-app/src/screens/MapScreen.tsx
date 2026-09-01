import * as Location from 'expo-location';
import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import MapView, { Marker, type Region } from 'react-native-maps';
import { SafeAreaView } from 'react-native-safe-area-context';

import { DEFAULT_REGION } from '@/constants/config';
import { Brand, MarkerColors, Spacing } from '@/constants/theme';
import { useLocations } from '@/context/LocationsContext';
import type { WashLocation } from '@/types';

/**
 * 한 번에 그릴 마커 수 상한.
 * 수백 개를 동시에 올리면 iOS에서 앱이 강제 종료될 만큼 메모리를 먹는다.
 */
const MAX_MARKERS = 120;

/** 마커 색: 확인된 곳은 파란색, 사용자 등록은 초록색, 신고로 검토중이면 주황색. */
function markerColor(location: WashLocation): string {
  if (location.status === 'reviewing') return MarkerColors.reviewing;
  if (location.source === 'user') return MarkerColors.user;
  return MarkerColors.confirmed;
}

/** 지금 화면에 보이는 범위의 마커만, 화면 중심에 가까운 것부터 추린다. */
function visibleMarkers(locations: WashLocation[], region: Region): WashLocation[] {
  const latPad = region.latitudeDelta * 0.65;
  const lngPad = region.longitudeDelta * 0.65;

  const inView = locations.filter(
    (location) =>
      Math.abs(location.lat - region.latitude) <= latPad &&
      Math.abs(location.lng - region.longitude) <= lngPad,
  );

  if (inView.length <= MAX_MARKERS) {
    return inView;
  }

  return inView
    .map((location) => ({
      location,
      distance:
        (location.lat - region.latitude) ** 2 + (location.lng - region.longitude) ** 2,
    }))
    .sort((a, b) => a.distance - b.distance)
    .slice(0, MAX_MARKERS)
    .map((item) => item.location);
}

export default function MapScreen() {
  const router = useRouter();
  const { locations, isLoading, isMock, refresh } = useLocations();
  const mapRef = useRef<MapView>(null);
  const [region, setRegion] = useState<Region>(DEFAULT_REGION);

  const markers = useMemo(() => visibleMarkers(locations, region), [locations, region]);
  const hiddenCount = locations.length - markers.length;

  // 다른 화면에서 등록/리뷰를 마치고 돌아오면 목록을 다시 불러온다.
  useFocusEffect(
    useCallback(() => {
      refresh();
    }, [refresh]),
  );

  useEffect(() => {
    let cancelled = false;

    async function moveToCurrentPosition() {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted' || cancelled) return;

      const position = await Location.getCurrentPositionAsync({});
      if (cancelled) return;

      mapRef.current?.animateToRegion({
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        latitudeDelta: 0.03,
        longitudeDelta: 0.03,
      });
    }

    moveToCurrentPosition().catch(() => {
      // 권한 거부나 위치 조회 실패는 기본 지역(서울 시청)을 그대로 쓰면 되므로 무시한다.
    });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <View style={styles.container}>
      <MapView
        ref={mapRef}
        style={StyleSheet.absoluteFill}
        initialRegion={DEFAULT_REGION}
        onRegionChangeComplete={setRegion}
        showsUserLocation
        showsMyLocationButton={false}>
        {markers.map((location) => (
          <Marker
            key={location.id}
            coordinate={{ latitude: location.lat, longitude: location.lng }}
            pinColor={markerColor(location)}
            title={`${location.status === 'unconfirmed' ? '⚠️ ' : ''}${location.building_name}`}
            description={location.address || location.detail_text}
            onCalloutPress={() => router.push(`/location/${location.id}`)}
          />
        ))}
      </MapView>

      <SafeAreaView style={styles.overlay} pointerEvents="box-none" edges={['top']}>
        <View style={styles.header} pointerEvents="none">
          <Text style={styles.title}>CupPit</Text>
          <Text style={styles.subtitle}>가까운 텀블러 세척기를 찾아보세요</Text>
        </View>

        {isMock && (
          <View style={styles.banner} pointerEvents="none">
            <Text style={styles.bannerText}>
              백엔드에 연결하지 못해 샘플 데이터를 표시 중입니다.
            </Text>
          </View>
        )}

        {hiddenCount > 0 && (
          <View style={styles.infoBanner} pointerEvents="none">
            <Text style={styles.infoBannerText}>
              이 화면에 {markers.length}곳 표시 중 · 지도를 움직이면 주변 세척기가 더 나타납니다
            </Text>
          </View>
        )}

        {isLoading && locations.length === 0 && (
          <View style={styles.loading} pointerEvents="none">
            <ActivityIndicator color={Brand.primary} />
          </View>
        )}
      </SafeAreaView>

      <SafeAreaView style={styles.footer} pointerEvents="box-none" edges={['bottom']}>
        <View style={styles.legend}>
          <LegendDot color={MarkerColors.confirmed} label="확인됨" />
          <LegendDot color={MarkerColors.user} label="사용자 등록" />
          <LegendDot color={MarkerColors.reviewing} label="검토중" />
        </View>

        <Pressable
          accessibilityRole="button"
          accessibilityLabel="위치 등록"
          onPress={() => router.push('/add-location')}
          style={({ pressed }) => [styles.fab, pressed && styles.fabPressed]}>
          <Text style={styles.fabText}>+ 위치 등록</Text>
        </Pressable>
      </SafeAreaView>
    </View>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <View style={styles.legendItem}>
      <View style={[styles.legendDot, { backgroundColor: color }]} />
      <Text style={styles.legendLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  overlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    gap: Spacing.two,
    padding: Spacing.three,
  },
  header: {
    backgroundColor: 'rgba(255,255,255,0.94)',
    borderRadius: 16,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOpacity: 0.12,
        shadowRadius: 10,
        shadowOffset: { width: 0, height: 4 },
      },
      android: { elevation: 4 },
    }),
  },
  title: { fontSize: 24, fontWeight: '800', color: Brand.primary },
  subtitle: { fontSize: 13, color: Brand.muted, marginTop: 2 },
  banner: {
    backgroundColor: '#FDF3E2',
    borderRadius: 12,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
  },
  bannerText: { fontSize: 13, color: '#8A5A00' },
  infoBanner: {
    backgroundColor: 'rgba(255,255,255,0.94)',
    borderRadius: 12,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
  },
  infoBannerText: { fontSize: 12, color: Brand.muted },
  loading: { alignItems: 'center', paddingTop: Spacing.three },
  footer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    padding: Spacing.three,
    gap: Spacing.two,
    alignItems: 'flex-end',
  },
  legend: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    gap: Spacing.three,
    backgroundColor: 'rgba(255,255,255,0.94)',
    borderRadius: 999,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
  },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendLabel: { fontSize: 12, color: '#374151', fontWeight: '600' },
  fab: {
    backgroundColor: Brand.primary,
    borderRadius: 999,
    paddingHorizontal: Spacing.four,
    paddingVertical: Spacing.three,
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOpacity: 0.2,
        shadowRadius: 12,
        shadowOffset: { width: 0, height: 6 },
      },
      android: { elevation: 6 },
    }),
  },
  fabPressed: { opacity: 0.8 },
  fabText: { color: '#FFFFFF', fontSize: 16, fontWeight: '800' },
});
