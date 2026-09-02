import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { toErrorMessage } from '@/api/client';
import { deleteUsage, fetchUsageReport, fetchUsages } from '@/api/locations';
import { PrimaryButton } from '@/components/primary-button';
import { Brand, Spacing } from '@/constants/theme';
import type { Usage, UsageBucket, UsageReport } from '@/types';

/** 막대 그래프의 최대 높이(px). 가장 많이 쓴 칸이 이 높이가 된다. */
const CHART_HEIGHT = 72;

export default function MyReportScreen() {
  const router = useRouter();
  const [report, setReport] = useState<UsageReport | null>(null);
  const [usages, setUsages] = useState<Usage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      // 리포트(AI 호출 포함)와 기록 목록을 함께 받는다.
      const [nextReport, nextUsages] = await Promise.all([fetchUsageReport(), fetchUsages()]);
      setReport(nextReport);
      setUsages(nextUsages);
      setError(null);
    } catch (err) {
      setError(toErrorMessage(err, '리포트를 불러오지 못했습니다.'));
    } finally {
      setIsLoading(false);
    }
  }, []);

  /** 잘못 남긴 기록 지우기. 통계가 바뀌므로 리포트도 다시 불러온다. */
  function confirmDelete(usage: Usage) {
    Alert.alert(
      '이 기록을 지울까요?',
      `${usage.location_name}\n${formatUsedAt(usage.used_at)}${usage.note ? ` · ${usage.note}` : ''}`,
      [
        { text: '취소', style: 'cancel' },
        {
          text: '지우기',
          style: 'destructive',
          onPress: async () => {
            try {
              await deleteUsage(usage.id);
              await load();
            } catch (err) {
              Alert.alert('지우지 못했습니다', toErrorMessage(err));
            }
          },
        },
      ],
    );
  }

  // 세척기 상세에서 기록을 남기고 돌아오면 리포트를 다시 불러온다.
  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  if (isLoading && !report) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={Brand.primary} />
        <Text style={styles.loadingText}>기록을 정리하는 중…</Text>
      </View>
    );
  }

  if (error || !report) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error ?? '리포트를 불러오지 못했습니다.'}</Text>
        <PrimaryButton label="다시 시도" variant="secondary" onPress={load} />
      </View>
    );
  }

  const { stats, narrative } = report;

  // 기록이 하나도 없으면 그래프와 통계는 전부 0이라 보여줄 게 없다.
  // 대신 무엇을 하면 되는지만 안내한다.
  if (stats.total_count === 0) {
    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <View style={styles.narrativeCard}>
          <Text style={styles.narrativeBadge}>AI 습관 리포트</Text>
          <Text style={styles.headline}>{narrative.headline}</Text>
          <Text style={styles.message}>{narrative.message}</Text>
        </View>
        <PrimaryButton label="지도에서 세척기 찾기" onPress={() => router.replace('/')} />
      </ScrollView>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.narrativeCard}>
        <Text style={styles.narrativeBadge}>AI 습관 리포트</Text>
        <Text style={styles.headline}>{narrative.headline}</Text>
        <Text style={styles.message}>{narrative.message}</Text>
        {narrative.tip.length > 0 && (
          <View style={styles.tip}>
            <Text style={styles.tipText}>💡 {narrative.tip}</Text>
          </View>
        )}
      </View>

      <View style={styles.tiles}>
        <StatTile value={`${stats.total_count}회`} label="총 사용" />
        <StatTile value={`${stats.location_count}곳`} label="다녀온 장소" />
        <StatTile value={`${stats.recent_count}회`} label="최근 4주" />
        <StatTile value={`${stats.streak_weeks}주`} label="연속 사용" />
      </View>

      <View style={styles.savedCard}>
        <Text style={styles.savedTitle}>내가 아낀 것</Text>
        <Text style={styles.savedValue}>일회용 컵 약 {stats.saved_cups}개</Text>
        <Text style={styles.savedValue}>온실가스 약 {formatCo2(stats.saved_co2_grams)}</Text>
        <Text style={styles.savedNote}>
          세척기를 한 번 쓸 때마다 일회용 컵 한 개를 대신했다고 보고 계산한 어림값입니다.
        </Text>
      </View>

      <Section title="요일별 사용">
        <BarChart data={stats.weekday_counts} highlight={stats.busiest_weekday} />
      </Section>

      <Section title="시간대별 사용">
        <BarChart data={stats.time_buckets} highlight={stats.busiest_time} />
      </Section>

      <Section title="최근 4주 추이">
        <BarChart data={stats.weekly_trend} />
      </Section>

      {stats.top_contexts.length > 0 && (
        <Section title="자주 적은 상황">
          {stats.top_contexts.map((item) => (
            <View key={item.label} style={styles.contextRow}>
              <Text style={styles.contextLabel} numberOfLines={1}>
                {item.label}
              </Text>
              <Text style={styles.contextCount}>{item.count}회</Text>
            </View>
          ))}
        </Section>
      )}

      {stats.place_categories.length > 0 && (
        <Section title="어떤 곳에서 씻었나">
          <BarChart data={stats.place_categories} highlight={stats.place_categories[0].label} />
          <Text style={styles.sectionNote}>장소 이름으로 추정한 값입니다.</Text>
        </Section>
      )}

      {stats.top_locations.length > 0 && (
        <Section title="자주 가는 곳">
          {stats.top_locations.map((place, index) => (
            <Pressable
              key={place.id}
              accessibilityRole="button"
              onPress={() => router.push(`/location/${place.id}`)}
              style={({ pressed }) => [styles.placeRow, pressed && styles.placeRowPressed]}>
              <Text style={styles.placeRank}>{index + 1}</Text>
              <Text style={styles.placeName} numberOfLines={1}>
                {place.name}
              </Text>
              <Text style={styles.placeCount}>{place.count}회</Text>
            </Pressable>
          ))}
        </Section>
      )}

      {usages.length > 0 && (
        <Section title="최근 기록">
          <Text style={styles.sectionNote}>잘못 남긴 기록은 눌러서 지울 수 있습니다.</Text>
          {usages.slice(0, 10).map((usage) => (
            <Pressable
              key={usage.id}
              accessibilityRole="button"
              accessibilityHint="눌러서 이 기록을 지웁니다"
              onPress={() => confirmDelete(usage)}
              style={({ pressed }) => [styles.usageRow, pressed && styles.placeRowPressed]}>
              <View style={styles.usageTexts}>
                <Text style={styles.usageName} numberOfLines={1}>
                  {usage.location_name}
                </Text>
                <Text style={styles.usageDate}>
                  {formatUsedAt(usage.used_at)}
                  {usage.note ? ` · ${usage.note}` : ''}
                </Text>
              </View>
              <Text style={styles.usageDelete}>지우기</Text>
            </Pressable>
          ))}
        </Section>
      )}
    </ScrollView>
  );
}

/** '9월 2일 (수) 오후 1:20' 형태로 읽기 좋게. */
function formatUsedAt(iso: string): string {
  return new Date(iso).toLocaleString('ko-KR', {
    month: 'long',
    day: 'numeric',
    weekday: 'short',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function StatTile({ value, label }: { value: string; label: string }) {
  return (
    <View style={styles.tile}>
      <Text style={styles.tileValue}>{value}</Text>
      <Text style={styles.tileLabel}>{label}</Text>
    </View>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {children}
    </View>
  );
}

/**
 * 세로 막대 그래프.
 *
 * 가장 큰 값을 기준으로 높이를 나눈다. 0인 칸도 자리를 지켜야 '이 요일엔 안 갔구나'가
 * 읽히므로, 막대를 지우지 않고 아주 낮게 남겨둔다.
 */
function BarChart({ data, highlight }: { data: UsageBucket[]; highlight?: string | null }) {
  const max = Math.max(...data.map((item) => item.count), 1);

  return (
    <View style={styles.chart}>
      {data.map((item) => {
        const isHighlighted = highlight === item.label;
        return (
          <View key={item.label} style={styles.chartColumn}>
            <Text style={[styles.chartCount, isHighlighted && styles.chartCountStrong]}>
              {item.count}
            </Text>
            <View style={styles.chartTrack}>
              <View
                style={[
                  styles.chartBar,
                  { height: Math.max(3, (item.count / max) * CHART_HEIGHT) },
                  isHighlighted && styles.chartBarStrong,
                ]}
              />
            </View>
            <Text style={[styles.chartLabel, isHighlighted && styles.chartLabelStrong]}>
              {item.label}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

/** 그램이 커지면 킬로그램으로 바꿔 읽기 쉽게 한다. */
function formatCo2(grams: number): string {
  if (grams < 1000) return `${grams}g`;
  return `${(grams / 1000).toFixed(1)}kg`;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  content: { padding: Spacing.three, gap: Spacing.three, paddingBottom: Spacing.six },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.four,
    gap: Spacing.three,
  },
  loadingText: { fontSize: 14, color: Brand.muted },
  errorText: { fontSize: 15, color: Brand.danger, textAlign: 'center' },

  narrativeCard: {
    backgroundColor: Brand.primarySoft,
    borderRadius: 16,
    padding: Spacing.three,
    gap: Spacing.two,
  },
  narrativeBadge: { fontSize: 12, fontWeight: '700', color: Brand.primaryDark, letterSpacing: 0.5 },
  headline: { fontSize: 22, fontWeight: '800', color: Brand.primaryDark, lineHeight: 30 },
  message: { fontSize: 15, lineHeight: 23, color: '#1F2937' },
  tip: {
    backgroundColor: 'rgba(255,255,255,0.75)',
    borderRadius: 12,
    padding: Spacing.two,
  },
  tipText: { fontSize: 14, lineHeight: 21, color: Brand.primaryDark, fontWeight: '600' },

  tiles: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two },
  tile: {
    flexGrow: 1,
    flexBasis: '46%',
    backgroundColor: '#F3F4F6',
    borderRadius: 14,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.three,
    gap: 2,
  },
  tileValue: { fontSize: 22, fontWeight: '800', color: '#111827' },
  tileLabel: { fontSize: 13, color: Brand.muted, fontWeight: '600' },

  savedCard: {
    borderRadius: 16,
    borderWidth: 1,
    borderColor: Brand.border,
    padding: Spacing.three,
    gap: Spacing.one,
  },
  savedTitle: { fontSize: 13, fontWeight: '700', color: Brand.muted, marginBottom: Spacing.one },
  savedValue: { fontSize: 17, fontWeight: '700', color: Brand.primary },
  savedNote: { fontSize: 12, lineHeight: 18, color: Brand.muted, marginTop: Spacing.one },

  section: { gap: Spacing.two },
  sectionTitle: { fontSize: 17, fontWeight: '800', color: '#111827' },

  chart: { flexDirection: 'row', alignItems: 'flex-end', gap: Spacing.one },
  chartColumn: { flex: 1, alignItems: 'center', gap: Spacing.one },
  chartCount: { fontSize: 12, color: Brand.muted, fontWeight: '600' },
  chartCountStrong: { color: Brand.primary },
  chartTrack: { height: CHART_HEIGHT, justifyContent: 'flex-end' },
  chartBar: {
    width: 22,
    borderRadius: 6,
    backgroundColor: '#D6E9E3',
  },
  chartBarStrong: { backgroundColor: Brand.primary },
  chartLabel: { fontSize: 12, color: Brand.muted, fontWeight: '600' },
  chartLabelStrong: { color: Brand.primary },

  placeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    paddingVertical: Spacing.two,
  },
  placeRowPressed: { opacity: 0.6 },
  placeRank: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: Brand.primarySoft,
    color: Brand.primaryDark,
    fontSize: 12,
    fontWeight: '800',
    textAlign: 'center',
    lineHeight: 22,
  },
  placeName: { flex: 1, fontSize: 15, fontWeight: '600', color: '#111827' },
  sectionNote: { fontSize: 12, color: Brand.muted, lineHeight: 18 },
  contextRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    paddingVertical: Spacing.one,
  },
  contextLabel: { flex: 1, fontSize: 15, color: '#111827', fontWeight: '600' },
  contextCount: { fontSize: 14, color: Brand.muted, fontWeight: '700' },
  usageRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    paddingVertical: Spacing.two,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Brand.border,
  },
  usageTexts: { flex: 1, gap: 2 },
  usageName: { fontSize: 15, fontWeight: '600', color: '#111827' },
  usageDate: { fontSize: 13, color: Brand.muted },
  usageDelete: { fontSize: 13, fontWeight: '700', color: Brand.danger },
  placeCount: { fontSize: 14, color: Brand.muted, fontWeight: '700' },
});
