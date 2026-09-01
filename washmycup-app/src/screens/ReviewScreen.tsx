import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { toErrorMessage } from '@/api/client';
import { createReview } from '@/api/locations';
import { PrimaryButton } from '@/components/primary-button';
import { FREE_TEXT_MAX_LENGTH, REVIEW_TAGS } from '@/constants/tags';
import { Brand, Spacing } from '@/constants/theme';
import type { ReviewType } from '@/types';

export default function ReviewScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const locationId = Number(id);
  const router = useRouter();

  const [type, setType] = useState<ReviewType | null>(null);
  const [tags, setTags] = useState<string[]>([]);
  const [freeText, setFreeText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  function selectType(next: ReviewType) {
    // 👍/👎에 따라 태그 목록이 다르므로 태그 선택만 초기화한다.
    // 적어둔 의견은 그대로 두어 다시 쓰게 만들지 않는다.
    setType(next);
    setTags([]);
  }

  function toggleTag(tag: string) {
    setTags((current) =>
      current.includes(tag) ? current.filter((item) => item !== tag) : [...current, tag],
    );
  }

  async function submit() {
    if (!type) {
      Alert.alert('👍 또는 👎를 먼저 선택해주세요.');
      return;
    }
    if (tags.length === 0 && !freeText.trim()) {
      Alert.alert('태그를 하나 이상 고르거나 의견을 입력해주세요.');
      return;
    }

    setIsSubmitting(true);
    try {
      await createReview(locationId, { type, tags, free_text: freeText.trim() });
      Alert.alert('리뷰가 등록되었습니다', '소중한 후기 감사합니다!');
      router.back();
    } catch (error) {
      Alert.alert('리뷰 등록 실패', toErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <View style={styles.field}>
          <Text style={styles.label}>이 세척기, 어떠셨나요?</Text>
          <View style={styles.verdictRow}>
            <VerdictButton
              emoji="👍"
              label="좋아요"
              selected={type === 'up'}
              tone="up"
              onPress={() => selectType('up')}
            />
            <VerdictButton
              emoji="👎"
              label="별로예요"
              selected={type === 'down'}
              tone="down"
              onPress={() => selectType('down')}
            />
          </View>
        </View>

        {type && (
          <View style={styles.field}>
            <Text style={styles.label}>어떤 점이 그랬나요?</Text>
            <Text style={styles.help}>해당하는 걸 모두 골라주세요.</Text>
            <View style={styles.tagRow}>
              {REVIEW_TAGS[type].map((tag) => {
                const selected = tags.includes(tag);
                return (
                  <Pressable
                    key={tag}
                    onPress={() => toggleTag(tag)}
                    accessibilityRole="checkbox"
                    accessibilityState={{ checked: selected }}
                    style={[styles.tag, selected && styles.tagSelected]}>
                    <Text style={[styles.tagText, selected && styles.tagTextSelected]}>{tag}</Text>
                  </Pressable>
                );
              })}
            </View>
          </View>
        )}

        {type && (
          <View style={styles.field}>
            <TextInput
              value={freeText}
              onChangeText={setFreeText}
              placeholder={`${FREE_TEXT_MAX_LENGTH}자 이내로 적어주세요 (선택)`}
              placeholderTextColor="#9CA3AF"
              style={[styles.input, styles.textArea]}
              multiline
              maxLength={FREE_TEXT_MAX_LENGTH}
            />
            <Text style={styles.counter}>
              {freeText.length} / {FREE_TEXT_MAX_LENGTH}
            </Text>
          </View>
        )}

        <PrimaryButton label="리뷰 등록" onPress={submit} loading={isSubmitting} />
        <Text style={styles.footnote}>
          남겨주신 리뷰는 AI 신뢰도 리포트에 반영되어 다음 사용자에게 &lsquo;지금 이용
          가능한지&rsquo;를 알려줍니다.
        </Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function VerdictButton({
  emoji,
  label,
  selected,
  tone,
  onPress,
}: {
  emoji: string;
  label: string;
  selected: boolean;
  tone: 'up' | 'down';
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="radio"
      accessibilityState={{ selected }}
      style={[
        styles.verdict,
        selected && (tone === 'up' ? styles.verdictUpSelected : styles.verdictDownSelected),
      ]}>
      <Text style={styles.verdictEmoji}>{emoji}</Text>
      <Text
        style={[
          styles.verdictLabel,
          selected && (tone === 'up' ? styles.verdictLabelUp : styles.verdictLabelDown),
        ]}>
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  content: { padding: Spacing.three, gap: Spacing.four, paddingBottom: Spacing.six },
  field: { gap: Spacing.two },
  label: { fontSize: 16, fontWeight: '800', color: '#111827' },
  help: { fontSize: 13, color: Brand.muted },
  verdictRow: { flexDirection: 'row', gap: Spacing.two },
  verdict: {
    flex: 1,
    alignItems: 'center',
    gap: Spacing.one,
    paddingVertical: Spacing.four,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: Brand.border,
    backgroundColor: '#FAFAFA',
  },
  verdictUpSelected: { borderColor: Brand.primary, backgroundColor: Brand.primarySoft },
  verdictDownSelected: { borderColor: Brand.danger, backgroundColor: Brand.dangerSoft },
  verdictEmoji: { fontSize: 32 },
  verdictLabel: { fontSize: 15, fontWeight: '700', color: Brand.muted },
  verdictLabelUp: { color: Brand.primaryDark },
  verdictLabelDown: { color: Brand.danger },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two },
  tag: {
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: Brand.border,
    backgroundColor: '#FFFFFF',
  },
  tagSelected: { borderColor: Brand.primary, backgroundColor: Brand.primarySoft },
  tagText: { fontSize: 15, fontWeight: '600', color: '#374151' },
  tagTextSelected: { color: Brand.primaryDark },
  input: {
    borderWidth: 1,
    borderColor: Brand.border,
    borderRadius: 12,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.three,
    fontSize: 16,
    color: '#111827',
  },
  textArea: { minHeight: 96, textAlignVertical: 'top' },
  counter: { alignSelf: 'flex-end', fontSize: 13, color: Brand.muted },
  footnote: { fontSize: 13, color: Brand.muted, lineHeight: 20 },
});
