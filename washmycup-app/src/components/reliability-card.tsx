import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { Brand, ReliabilityStyles, Spacing } from '@/constants/theme';
import type { ReliabilityReport } from '@/types';

interface ReliabilityCardProps {
  report: ReliabilityReport | null;
  isLoading: boolean;
  error?: string | null;
  onRetry?: () => void;
}

/** 리뷰를 AI가 요약한 '지금 이용 가능 확률' 카드. */
export function ReliabilityCard({ report, isLoading, error, onRetry }: ReliabilityCardProps) {
  if (isLoading) {
    return (
      <View style={[styles.card, styles.neutralRow]}>
        <ActivityIndicator color={Brand.primary} />
        <Text style={styles.loadingText}>AI가 리뷰를 요약하는 중…</Text>
      </View>
    );
  }

  if (error || !report) {
    return (
      <View style={[styles.card, styles.neutral]}>
        <Text style={styles.badge}>AI 신뢰도 리포트</Text>
        <Text style={styles.summary}>{error ?? '요약을 불러오지 못했습니다.'}</Text>
        {onRetry && (
          <Pressable onPress={onRetry} accessibilityRole="button" style={styles.retryButton}>
            <Text style={styles.retryText}>다시 시도</Text>
          </Pressable>
        )}
      </View>
    );
  }

  const tone = ReliabilityStyles[report.score];
  // 리뷰에서 언급된 항목만 내려오므로 개수가 매번 다르다.
  // 응답에 아예 없을 수도 있어(옛 캐시 등) 기본값을 둔다. 없다고 화면이 죽으면 안 된다.
  const aspects = Object.entries(report.aspects ?? {});
  const notes = report.notes ?? [];

  return (
    <View style={[styles.card, { backgroundColor: tone.background }]}>
      <Text style={styles.badge}>AI 신뢰도 리포트</Text>
      <Text style={[styles.headline, { color: tone.color }]}>
        {tone.emoji} {tone.label}
      </Text>
      <Text style={styles.summary}>{report.summary}</Text>

      {aspects.length > 0 && (
        <View style={styles.aspects}>
          {aspects.map(([label, score]) => (
            <View key={label} style={styles.aspectRow}>
              <Text style={styles.aspectLabel}>{label}</Text>
              <Text style={[styles.aspectStars, { color: tone.color }]}>
                {'★'.repeat(score)}
                <Text style={styles.aspectStarsEmpty}>{'★'.repeat(5 - score)}</Text>
              </Text>
            </View>
          ))}
        </View>
      )}

      {notes.length > 0 && (
        <View style={styles.notes}>
          {notes.map((note) => (
            <Text key={note} style={styles.note}>
              · {note}
            </Text>
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    padding: Spacing.three,
    gap: Spacing.two,
  },
  neutral: {
    backgroundColor: '#F3F4F6',
  },
  neutralRow: {
    backgroundColor: '#F3F4F6',
    alignItems: 'center',
    flexDirection: 'row',
    gap: Spacing.two,
  },
  retryButton: {
    alignSelf: 'flex-start',
    paddingVertical: Spacing.one,
    paddingHorizontal: Spacing.two,
    borderRadius: 8,
    backgroundColor: Brand.primarySoft,
  },
  retryText: { fontSize: 14, fontWeight: '700', color: Brand.primaryDark },
  badge: {
    fontSize: 12,
    fontWeight: '700',
    color: Brand.muted,
    letterSpacing: 0.5,
  },
  headline: {
    fontSize: 18,
    fontWeight: '800',
  },
  summary: {
    fontSize: 15,
    lineHeight: 22,
    color: '#374151',
  },
  aspects: {
    gap: Spacing.one,
    paddingTop: Spacing.two,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'rgba(0,0,0,0.12)',
  },
  aspectRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two },
  aspectLabel: { fontSize: 14, color: '#374151', width: 68 },
  aspectStars: { fontSize: 15, letterSpacing: 1 },
  aspectStarsEmpty: { color: 'rgba(0,0,0,0.15)' },
  notes: {
    gap: Spacing.one,
    paddingTop: Spacing.two,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'rgba(0,0,0,0.12)',
  },
  note: { fontSize: 14, lineHeight: 20, color: '#374151' },
  loadingText: {
    fontSize: 14,
    color: Brand.muted,
  },
});
