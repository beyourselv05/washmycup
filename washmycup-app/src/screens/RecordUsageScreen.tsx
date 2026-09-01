import DateTimePicker from '@react-native-community/datetimepicker';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
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
import { deleteUsage, fetchUsageNotes, recordUsage } from '@/api/locations';
import { PrimaryButton } from '@/components/primary-button';
import { Brand, Spacing } from '@/constants/theme';
import { useLocations } from '@/context/LocationsContext';

/** 백엔드 Usage.note의 max_length와 맞춘다. */
const NOTE_MAX_LENGTH = 40;

/** 서버가 받아주는 최대 소급 기간(1년)과 맞춘다. */
const MAX_BACKDATE_DAYS = 365;

/**
 * 아직 아무것도 안 적어본 사람에게만 보여주는 예시.
 *
 * 평소에는 사용자가 전에 쓴 말을 칩으로 띄우지만, 첫 기록에는 그럴 재료가 없어
 * 빈 입력창만 남는다. 그 순간이 제일 그냥 넘기기 쉬운 지점이라 첫 삽만 떠준다.
 * 자기 문구가 하나라도 생기면 이 예시는 다시 나오지 않는다. (chips 계산 참고)
 */
const EXAMPLE_NOTES = ['점심 먹고', '출근길에', '수업 끝나고', '운동 가기 전'];

export default function RecordUsageScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const locationId = Number(id);
  const router = useRouter();

  // 목록은 이미 받아둔 게 있어 상세를 다시 부르지 않는다.
  const { locations } = useLocations();
  const location = locations.find((item) => item.id === locationId);

  const [usedAt, setUsedAt] = useState(() => new Date());
  const [note, setNote] = useState('');
  const [recentNotes, setRecentNotes] = useState<string[]>([]);
  // 목록을 받기 전에 예시를 먼저 그리면 잠깐 떴다가 바뀌어 어수선하다.
  const [notesLoaded, setNotesLoaded] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  // 안드로이드는 달력을 화면에 펼칠 수 없어 눌렀을 때만 시스템 다이얼로그를 띄운다.
  const [androidPicker, setAndroidPicker] = useState<'date' | 'time' | null>(null);

  // 전에 쓴 문구를 다시 쓰기 쉽게 불러온다. 실패해도 직접 입력하면 되므로 조용히 넘긴다.
  useEffect(() => {
    fetchUsageNotes()
      .then(setRecentNotes)
      .catch(() => setRecentNotes([]))
      .finally(() => setNotesLoaded(true));
  }, []);

  // 내가 쓴 말이 하나라도 있으면 그것만 보여준다. 없을 때만 예시로 대신한다.
  const hasOwnNotes = recentNotes.length > 0;
  const chips = hasOwnNotes ? recentNotes : EXAMPLE_NOTES;

  const now = new Date();
  const minimumDate = new Date(now.getTime() - MAX_BACKDATE_DAYS * 24 * 60 * 60 * 1000);

  async function handleSave() {
    setIsSaving(true);
    try {
      const usage = await recordUsage(locationId, { usedAt, note: note.trim() });
      Alert.alert(
        '기록했어요',
        `${formatUsedAt(usage.used_at)}\n지금까지 ${usage.total_count}번째입니다.`,
        [
          { text: '실행 취소', style: 'destructive', onPress: () => undo(usage.id) },
          { text: '내 기록 보기', onPress: () => router.replace('/my-report') },
          { text: '완료', onPress: () => router.back() },
        ],
      );
    } catch (error) {
      Alert.alert('기록하지 못했습니다', toErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }

  async function undo(usageId: number) {
    try {
      await deleteUsage(usageId);
      Alert.alert('취소했어요', '방금 남긴 기록을 지웠습니다.');
    } catch (error) {
      Alert.alert('취소하지 못했습니다', toErrorMessage(error));
    }
  }

  /** 달력에서 날짜만 바꾸고 시각은 유지한다(그 반대도 마찬가지). */
  function mergeDate(next: Date) {
    const merged = new Date(usedAt);
    merged.setFullYear(next.getFullYear(), next.getMonth(), next.getDate());
    setUsedAt(merged > new Date() ? new Date() : merged);
  }

  function mergeTime(next: Date) {
    const merged = new Date(usedAt);
    merged.setHours(next.getHours(), next.getMinutes());
    setUsedAt(merged > new Date() ? new Date() : merged);
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <View style={styles.placeCard}>
          <Text style={styles.placeLabel}>장소</Text>
          <Text style={styles.placeName}>{location?.building_name ?? '선택한 세척기'}</Text>
          {location?.address ? <Text style={styles.placeAddress}>{location.address}</Text> : null}
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>언제 씻으셨나요?</Text>
          <Text style={styles.sectionNote}>{formatUsedAt(usedAt.toISOString())}</Text>

          {Platform.OS === 'ios' ? (
            <DateTimePicker
              value={usedAt}
              mode="datetime"
              display="inline"
              maximumDate={now}
              minimumDate={minimumDate}
              locale="ko-KR"
              onChange={(_, selected) => selected && setUsedAt(selected)}
              style={styles.picker}
            />
          ) : (
            <View style={styles.androidRow}>
              <Pressable
                onPress={() => setAndroidPicker('date')}
                style={({ pressed }) => [styles.androidButton, pressed && styles.pressed]}>
                <Text style={styles.androidButtonText}>날짜 고르기</Text>
              </Pressable>
              <Pressable
                onPress={() => setAndroidPicker('time')}
                style={({ pressed }) => [styles.androidButton, pressed && styles.pressed]}>
                <Text style={styles.androidButtonText}>시간 고르기</Text>
              </Pressable>
            </View>
          )}

          {androidPicker && (
            <DateTimePicker
              value={usedAt}
              mode={androidPicker}
              maximumDate={androidPicker === 'date' ? now : undefined}
              minimumDate={androidPicker === 'date' ? minimumDate : undefined}
              onChange={(event, selected) => {
                const step = androidPicker;
                setAndroidPicker(null);
                if (event.type === 'dismissed' || !selected) return;
                if (step === 'date') mergeDate(selected);
                else mergeTime(selected);
              }}
            />
          )}
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>어떤 상황이었나요?</Text>
          <Text style={styles.sectionNote}>
            안 적어도 됩니다. 적어두면 내 기록에서 흐름이 더 잘 보여요.
          </Text>

          <TextInput
            value={note}
            onChangeText={setNote}
            placeholder="예: 점심 먹고, 출근길에"
            placeholderTextColor="#9CA3AF"
            maxLength={NOTE_MAX_LENGTH}
            style={styles.input}
            returnKeyType="done"
          />
          <Text style={styles.counter}>
            {note.length}/{NOTE_MAX_LENGTH}
          </Text>

          {/*
            고정된 선택지 대신 '내가 전에 쓴 말'을 보여준다.
            맥락은 사람마다 달라서 목록을 정해두면 대부분 안 맞는다.
          */}
          {notesLoaded && (
            <>
              <Text style={styles.chipsLabel}>
                {hasOwnNotes ? '전에 적었던 상황' : '이런 식으로 적으면 됩니다'}
              </Text>
              <View style={styles.chips}>
                {chips.map((item) => {
                  const isSelected = note.trim() === item;
                  return (
                    <Pressable
                      key={item}
                      accessibilityRole="button"
                      onPress={() => setNote(isSelected ? '' : item)}
                      style={({ pressed }) => [
                        styles.chip,
                        !hasOwnNotes && styles.chipExample,
                        isSelected && styles.chipSelected,
                        pressed && styles.pressed,
                      ]}>
                      <Text style={[styles.chipText, isSelected && styles.chipTextSelected]}>
                        {item}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </>
          )}
        </View>

        <PrimaryButton label="기록 저장" loading={isSaving} onPress={handleSave} />
      </ScrollView>
    </KeyboardAvoidingView>
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

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  content: { padding: Spacing.three, gap: Spacing.four, paddingBottom: Spacing.six },

  placeCard: { backgroundColor: Brand.primarySoft, borderRadius: 14, padding: Spacing.three, gap: 2 },
  placeLabel: { fontSize: 12, fontWeight: '700', color: Brand.primaryDark, letterSpacing: 0.5 },
  placeName: { fontSize: 18, fontWeight: '800', color: '#111827' },
  placeAddress: { fontSize: 13, color: Brand.muted },

  section: { gap: Spacing.two },
  sectionTitle: { fontSize: 17, fontWeight: '800', color: '#111827' },
  sectionNote: { fontSize: 13, color: Brand.muted, lineHeight: 19 },
  picker: { alignSelf: 'stretch' },

  androidRow: { flexDirection: 'row', gap: Spacing.two },
  androidButton: {
    flex: 1,
    backgroundColor: Brand.primarySoft,
    borderRadius: 12,
    paddingVertical: Spacing.three,
    alignItems: 'center',
  },
  androidButtonText: { fontSize: 15, fontWeight: '700', color: Brand.primaryDark },

  input: {
    borderWidth: 1,
    borderColor: Brand.border,
    borderRadius: 12,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.three,
    fontSize: 16,
    color: '#111827',
  },
  counter: { fontSize: 12, color: Brand.muted, textAlign: 'right', marginTop: -Spacing.one },

  chipsLabel: { fontSize: 13, color: Brand.muted, fontWeight: '600', marginTop: Spacing.two },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two },
  chip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: Brand.border,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
  },
  // 예시는 내 기록이 아니라는 걸 옅은 배경으로 구분한다.
  chipExample: { backgroundColor: '#F9FAFB', borderStyle: 'dashed' },
  chipSelected: { backgroundColor: Brand.primary, borderColor: Brand.primary },
  chipText: { fontSize: 14, color: '#374151', fontWeight: '600' },
  chipTextSelected: { color: '#FFFFFF' },
  pressed: { opacity: 0.7 },
});
