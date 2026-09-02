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

/**
 * 마커를 그리는 순서(겹칠 때 누가 위로 오는지).
 *
 * 목록이 최신순이라 그냥 두면 방금 등록한 위치가 제일 먼저 그려져 오래된 마커에 덮인다.
 * 아직 확인 안 된 곳일수록 눈에 띄어야 하므로 위로 올린다.
 */
function markerZIndex(location: WashLocation): number {
  if (location.status === 'unconfirmed' || location.status === 'reviewing') return 2;
  if (location.source === 'user') return 1;
  return 0;
}

/**
 * 마커 색 규칙.
 * 아직 믿고 갈 수 없는 곳(미확인·신고 검토중)은 먼저 노랑으로 걸러내고,
 * 확인이 끝난 곳만 출처에 따라 파랑(공식)/초록(사용자 등록)으로 나눈다.
 */
function markerColor(location: WashLocation): string {
  if (location.status === 'unconfirmed' || location.status === 'reviewing') {
    return MarkerColors.reviewing;
  }
  if (location.source === 'user') return MarkerColors.user;
  return MarkerColors.official;
}

/**
 * 마커 말풍선에 넣을 한 줄 설명.
 *
 * iOS 기본 말풍선은 설명을 한 줄로 잘라내기 때문에, 줄바꿈을 쓰면 뒷부분이 통째로 가려진다.
 * 그래서 여러 줄을 ' · '로 펴서 잇고, 지도에서 더 중요한 상세 안내('임직원 전용' 등)를
 * 주소보다 앞에 둔다. 주소 전문은 상세 화면에서 볼 수 있다.
 */
function calloutText(location: WashLocation): string {
  return [...location.detail_text.split('\n'), location.address]
    .map((line) => line.trim())
    .filter(Boolean)
    .join(' · ');
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
            zIndex={markerZIndex(location)}
            title={`${location.status === 'unconfirmed' ? '⚠️ ' : ''}${location.building_name}`}
            description={calloutText(location)}
            onCalloutPress={() => router.push(`/location/${location.id}`)}
          />
        ))}
      </MapView>

      <SafeAreaView style={styles.overlay} pointerEvents="box-none" edges={['top']}>
        <View style={styles.header}>
          <View pointerEvents="none">
            <Text style={styles.title}>CupPit</Text>
            <Text style={styles.subtitle}>가까운 텀블러 세척기를 찾아보세요</Text>
          </View>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="내 텀블러 기록"
            onPress={() => router.push('/my-report')}
            style={({ pressed }) => [styles.reportButton, pressed && styles.reportButtonPressed]}>
            <Text style={styles.reportButtonText}>내 기록</Text>
          </Pressable>
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
          <LegendDot color={MarkerColors.official} label="공식 등록" />
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
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Spacing.two,
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
  reportButton: {
    backgroundColor: Brand.primarySoft,
    borderRadius: 999,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
  },
  reportButtonPressed: { opacity: 0.7 },
  reportButtonText: { fontSize: 13, fontWeight: '800', color: Brand.primaryDark },
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
    flexDirection: 'column',
    gap: Spacing.one,
    backgroundColor: 'rgba(255,255,255,0.94)',
    borderRadius: 16,
    padding: Spacing.two,
  },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: Spacing.one },
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
