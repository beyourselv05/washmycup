import { Image } from 'expo-image';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { toErrorMessage } from '@/api/client';
import { createReport, fetchLocationDetail, fetchReliability } from '@/api/locations';
import { PrimaryButton } from '@/components/primary-button';
import { ReliabilityCard } from '@/components/reliability-card';
import { ReviewItem } from '@/components/review-item';
import { Brand, Spacing } from '@/constants/theme';
import type { ReliabilityReport, WashLocationDetail } from '@/types';

// 백엔드 Location.Status와 같은 값이다. 문구는 앱에서 읽기 좋게 다듬었다.
const STATUS_LABELS: Record<string, string> = {
  confirmed: '✅ 운영진이 확인한 위치',
  unconfirmed: '⚠️ 운영진 확인 전',
  reviewing: '🔍 신고가 접수되어 검토 중',
  removed: '숨김 처리된 위치',
};

export default function LocationDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const locationId = Number(id);
  const router = useRouter();

  const [location, setLocation] = useState<WashLocationDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [report, setReport] = useState<ReliabilityReport | null>(null);
  const [isReportLoading, setIsReportLoading] = useState(true);
  const [reportError, setReportError] = useState<string | null>(null);

  const [isReporting, setIsReporting] = useState(false);

  /** AI 요약만 다시 불러온다. 카드의 '다시 시도' 버튼에서도 쓴다. */
  const loadReliability = useCallback(async () => {
    setIsReportLoading(true);
    try {
      const reliability = await fetchReliability(locationId);
      setReport(reliability);
      setReportError(null);
    } catch (error) {
      setReportError(toErrorMessage(error, 'AI 요약을 불러오지 못했습니다.'));
    } finally {
      setIsReportLoading(false);
    }
  }, [locationId]);

  // 리뷰를 쓰고 돌아오면 상세와 AI 요약을 모두 다시 불러온다.
  useFocusEffect(
    useCallback(() => {
      let cancelled = false;

      async function load() {
        setIsLoading(true);
        setIsReportLoading(true);

        try {
          const detail = await fetchLocationDetail(locationId);
          if (!cancelled) {
            setLocation(detail);
            setLoadError(null);
          }
        } catch (error) {
          if (!cancelled) setLoadError(toErrorMessage(error, '위치 정보를 불러오지 못했습니다.'));
        } finally {
          if (!cancelled) setIsLoading(false);
        }

        try {
          const reliability = await fetchReliability(locationId);
          if (!cancelled) {
            setReport(reliability);
            setReportError(null);
          }
        } catch (error) {
          if (!cancelled) setReportError(toErrorMessage(error, 'AI 요약을 불러오지 못했습니다.'));
        } finally {
          if (!cancelled) setIsReportLoading(false);
        }
      }

      if (Number.isFinite(locationId)) {
        load();
      } else {
        setLoadError('잘못된 위치입니다.');
        setIsLoading(false);
        setIsReportLoading(false);
      }

      return () => {
        cancelled = true;
      };
    }, [locationId]),
  );

  function handleReport() {
    // Alert.prompt는 iOS 전용이라 안드로이드에서는 확인만 받고 기본 사유로 보낸다.
    if (Platform.OS === 'ios') {
      Alert.prompt(
        '신고하기',
        '어떤 문제가 있나요? (예: 실제로 세척기가 없어요)',
        [
          { text: '취소', style: 'cancel' },
          {
            text: '신고',
            style: 'destructive',
            onPress: (reason?: string) => submitReport(reason ?? ''),
          },
        ],
        'plain-text',
      );
      return;
    }

    Alert.alert('신고하기', '이 위치에 문제가 있다고 신고할까요?', [
      { text: '취소', style: 'cancel' },
      {
        text: '신고',
        style: 'destructive',
        onPress: () => submitReport('앱에서 접수된 신고입니다.'),
      },
    ]);
  }

  async function submitReport(reason: string) {
    const trimmed = reason.trim();
    if (!trimmed) {
      Alert.alert('신고 사유를 입력해주세요.');
      return;
    }

    setIsReporting(true);
    try {
      await createReport(locationId, trimmed);
      Alert.alert('신고가 접수되었습니다', '관리자가 확인 후 처리합니다.');
    } catch (error) {
      Alert.alert('신고 실패', toErrorMessage(error));
    } finally {
      setIsReporting(false);
    }
  }

  if (isLoading && !location) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={Brand.primary} />
      </View>
    );
  }

  if (loadError || !location) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{loadError ?? '위치를 찾을 수 없습니다.'}</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {location.photo ? (
        <Image source={{ uri: location.photo }} style={styles.photo} contentFit="cover" />
      ) : (
        <View style={[styles.photo, styles.photoPlaceholder]}>
          <Text style={styles.photoPlaceholderText}>등록된 사진이 없습니다</Text>
        </View>
      )}

      <View style={styles.section}>
        <Text style={styles.status}>{STATUS_LABELS[location.status] ?? location.status}</Text>
        <Text style={styles.buildingName}>{location.building_name}</Text>
        {location.address.length > 0 && <Text style={styles.address}>{location.address}</Text>}
        {location.detail_text.length > 0 && (
          <Text style={styles.detailText}>{location.detail_text}</Text>
        )}
        <Text style={styles.counts}>
          👍 {location.up_count} · 👎 {location.down_count}
        </Text>
      </View>

      <ReliabilityCard
        report={report}
        isLoading={isReportLoading}
        error={reportError}
        onRetry={loadReliability}
      />

      <View style={styles.actions}>
        <PrimaryButton
          label="리뷰 작성"
          onPress={() => router.push(`/review/${location.id}`)}
          style={styles.actionButton}
        />
        <PrimaryButton
          label="신고하기"
          variant="danger"
          loading={isReporting}
          onPress={handleReport}
          style={styles.actionButton}
        />
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>리뷰 {location.reviews.length}개</Text>
        {location.reviews.length === 0 ? (
          <Text style={styles.emptyText}>
            아직 리뷰가 없습니다. 첫 리뷰를 남겨 다음 사용자를 도와주세요.
          </Text>
        ) : (
          location.reviews.map((review) => <ReviewItem key={review.id} review={review} />)
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  content: { padding: Spacing.three, gap: Spacing.three, paddingBottom: Spacing.six },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: Spacing.four },
  errorText: { fontSize: 15, color: Brand.danger, textAlign: 'center' },
  photo: { width: '100%', height: 200, borderRadius: 16, backgroundColor: '#F3F4F6' },
  photoPlaceholder: { alignItems: 'center', justifyContent: 'center' },
  photoPlaceholderText: { color: Brand.muted, fontSize: 14 },
  section: { gap: Spacing.two },
  buildingName: { fontSize: 24, fontWeight: '800', color: '#111827' },
  address: { fontSize: 13, color: Brand.muted, lineHeight: 18, marginTop: -4 },
  status: { fontSize: 14, fontWeight: '600', color: Brand.muted, marginBottom: -4 },
  detailText: { fontSize: 16, lineHeight: 24, fontWeight: '600', color: '#111827', marginVertical: Spacing.one },
  counts: { fontSize: 15, color: '#374151', fontWeight: '600' },
  actions: { flexDirection: 'row', gap: Spacing.two },
  actionButton: { flex: 1 },
  sectionTitle: { fontSize: 18, fontWeight: '800', color: '#111827' },
  emptyText: { fontSize: 15, color: Brand.muted, lineHeight: 22 },
});
