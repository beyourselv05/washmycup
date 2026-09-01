import { StyleSheet, Text, View } from 'react-native';

import { Brand, Spacing } from '@/constants/theme';
import type { Review } from '@/types';

export function ReviewItem({ review }: { review: Review }) {
  const isUp = review.type === 'up';

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.verdict}>{isUp ? '👍 좋아요' : '👎 별로예요'}</Text>
        <Text style={styles.date}>{formatDate(review.created_at)}</Text>
      </View>

      {review.tags.length > 0 && (
        <View style={styles.tagRow}>
          {review.tags.map((tag) => (
            <View key={tag} style={[styles.tag, isUp ? styles.tagUp : styles.tagDown]}>
              <Text style={[styles.tagText, isUp ? styles.tagTextUp : styles.tagTextDown]}>
                {tag}
              </Text>
            </View>
          ))}
        </View>
      )}

      {review.free_text.length > 0 && <Text style={styles.freeText}>{review.free_text}</Text>}
    </View>
  );
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return `${date.getMonth() + 1}월 ${date.getDate()}일`;
}

const styles = StyleSheet.create({
  container: {
    paddingVertical: Spacing.three,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Brand.border,
    gap: Spacing.two,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  verdict: { fontSize: 15, fontWeight: '700', color: '#111827' },
  date: { fontSize: 13, color: Brand.muted },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.one },
  tag: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999 },
  tagUp: { backgroundColor: Brand.primarySoft },
  tagDown: { backgroundColor: Brand.dangerSoft },
  tagText: { fontSize: 13, fontWeight: '600' },
  tagTextUp: { color: Brand.primaryDark },
  tagTextDown: { color: Brand.danger },
  freeText: { fontSize: 15, lineHeight: 22, color: '#374151' },
});
