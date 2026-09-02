import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import * as Location from 'expo-location';
import { useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import {
  ActivityIndicator,
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
import MapView, { Marker, type LatLng } from 'react-native-maps';

import { toErrorMessage } from '@/api/client';
import { createLocation } from '@/api/locations';
import { PrimaryButton } from '@/components/primary-button';
import { DEFAULT_REGION } from '@/constants/config';
import { Brand, MarkerColors, Spacing } from '@/constants/theme';
import { useLocations } from '@/context/LocationsContext';

/**
 * 역지오코딩 결과를 한 줄 주소로 조합한다.
 * formattedAddress는 안드로이드에서만 내려와서, iOS에서는 조각을 직접 이어 붙인다.
 */
function composeAddress(place: Location.LocationGeocodedAddress): string {
  if (place.formattedAddress) {
    return place.formattedAddress;
  }

  // 도로명주소 순서: 시/도 → 시군구 → 도로명 → 건물번호, 법정동은 끝에 괄호로.
  const composed: string[] = [];
  for (const part of [place.region, place.city, place.subregion, place.street, place.streetNumber]) {
    const value = part?.trim();
    // 시/도와 시가 똑같이 내려오거나, 도로명에 번지가 이미 붙어 있는 경우를 걸러낸다.
    if (!value || composed.some((existing) => existing.includes(value))) {
      continue;
    }
    composed.push(value);
  }

  const road = composed.join(' ');
  const dong = place.district?.trim();

  if (dong && !road.includes(dong)) {
    return `${road} (${dong})`;
  }
  return road;
}

export default function AddLocationScreen() {
  const router = useRouter();
  const { refresh } = useLocations();

  const [pin, setPin] = useState<LatLng>({
    latitude: DEFAULT_REGION.latitude,
    longitude: DEFAULT_REGION.longitude,
  });
  const [buildingName, setBuildingName] = useState('');
  const [address, setAddress] = useState('');
  const [isAddressLoading, setIsAddressLoading] = useState(false);
  const [detailText, setDetailText] = useState('');
  const [photoUri, setPhotoUri] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  /** 핀 위치가 정해질 때마다 그 지점의 주소를 자동으로 채운다. */
  const movePin = useCallback(async (next: LatLng) => {
    setPin(next);
    setIsAddressLoading(true);

    try {
      const places = await Location.reverseGeocodeAsync({
        latitude: next.latitude,
        longitude: next.longitude,
      });
      const composed = places.length > 0 ? composeAddress(places[0]) : '';
      if (composed) {
        setAddress(composed);
      }
    } catch {
      // 주소를 못 찾아도 등록은 가능하다. 직접 입력하면 된다.
    } finally {
      setIsAddressLoading(false);
    }
  }, []);

  async function useCurrentPosition() {
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('위치 권한이 필요합니다', '설정에서 위치 접근을 허용해주세요.');
        return;
      }

      const position = await Location.getCurrentPositionAsync({});
      await movePin({ latitude: position.coords.latitude, longitude: position.coords.longitude });
    } catch {
      Alert.alert('현재 위치를 가져오지 못했습니다', '지도를 눌러 직접 핀을 찍어주세요.');
    }
  }

  async function pickPhoto(from: 'camera' | 'library') {
    const permission =
      from === 'camera'
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();

    if (!permission.granted) {
      Alert.alert(
        from === 'camera' ? '카메라 권한이 필요합니다' : '사진 접근 권한이 필요합니다',
        '설정에서 권한을 허용해주세요.',
      );
      return;
    }

    const options: ImagePicker.ImagePickerOptions = {
      mediaTypes: ['images'],
      allowsEditing: true,
      quality: 0.6,
    };

    const result =
      from === 'camera'
        ? await ImagePicker.launchCameraAsync(options)
        : await ImagePicker.launchImageLibraryAsync(options);

    if (!result.canceled && result.assets.length > 0) {
      setPhotoUri(result.assets[0].uri);
    }
  }

  function choosePhotoSource() {
    // 시뮬레이터에는 카메라가 없어 앨범 선택이 기본 경로다.
    Alert.alert('사진 추가', '세척기와 주변이 함께 보이는 사진이 좋아요.', [
      { text: '사진 촬영', onPress: () => pickPhoto('camera') },
      { text: '앨범에서 선택', onPress: () => pickPhoto('library') },
      { text: '취소', style: 'cancel' },
    ]);
  }

  async function submit() {
    if (!buildingName.trim()) {
      Alert.alert('건물/장소명을 입력해주세요.');
      return;
    }

    setIsSubmitting(true);
    try {
      await createLocation({
        lat: pin.latitude,
        lng: pin.longitude,
        building_name: buildingName.trim(),
        address: address.trim(),
        detail_text: detailText.trim(),
        photoUri,
      });
      await refresh();
      Alert.alert('등록 완료', '지도에 새 위치가 추가되었습니다.');
      router.back();
    } catch (error) {
      Alert.alert('등록 실패', toErrorMessage(error));
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
          <Text style={styles.label}>1. 위치 찍기</Text>
          <Text style={styles.help}>지도를 눌러 세척기가 있는 지점에 핀을 놓아주세요.</Text>
          <View style={styles.mapWrapper}>
            <MapView
              style={styles.map}
              initialRegion={DEFAULT_REGION}
              onPress={(event) => movePin(event.nativeEvent.coordinate)}>
              <Marker
                coordinate={pin}
                pinColor={MarkerColors.user}
                draggable
                onDragEnd={(event) => movePin(event.nativeEvent.coordinate)}
              />
            </MapView>
          </View>
          <Pressable onPress={useCurrentPosition} style={styles.linkButton}>
            <Text style={styles.linkText}>📍 현재 내 위치 사용</Text>
          </Pressable>
        </View>

        <View style={styles.field}>
          <View style={styles.labelRow}>
            <Text style={styles.label}>2. 주소</Text>
            {isAddressLoading && <ActivityIndicator size="small" color={Brand.primary} />}
          </View>
          <Text style={styles.help}>핀을 찍으면 자동으로 채워집니다. 직접 고쳐도 됩니다.</Text>
          <TextInput
            value={address}
            onChangeText={setAddress}
            placeholder="예: 서울특별시 마포구 양화로 165"
            placeholderTextColor="#9CA3AF"
            style={styles.input}
            maxLength={200}
          />
        </View>

        <View style={styles.field}>
          <Text style={styles.label}>3. 건물/장소명</Text>
          <TextInput
            value={buildingName}
            onChangeText={setBuildingName}
            placeholder="예: 마포구청 별관"
            placeholderTextColor="#9CA3AF"
            style={styles.input}
            maxLength={100}
          />
        </View>

        <View style={styles.field}>
          <Text style={styles.label}>4. 사진 (선택)</Text>
          {/*
            세척기만 확대해 찍은 사진은 '있다'는 것만 알려줄 뿐, 정작 찾아갈 때 도움이 안 된다.
            주변이 함께 나와야 다음 사람이 그 자리를 찾는다.
          */}
          <Text style={styles.help}>
            세척기와 주변이 함께 보이게 찍어주세요. 옆에 있는 기둥·간판·출입구가 같이 나오면
            다른 사람이 찾기 훨씬 쉬워요. 지금 찍기 어렵다면 비워두셔도 됩니다.
          </Text>
          {photoUri ? (
            <Pressable onPress={choosePhotoSource}>
              <Image source={{ uri: photoUri }} style={styles.preview} contentFit="cover" />
              <Text style={styles.help}>사진을 눌러 다시 선택할 수 있습니다.</Text>
            </Pressable>
          ) : (
            <Pressable onPress={choosePhotoSource} style={styles.photoButton}>
              <Text style={styles.photoButtonText}>＋ 사진 촬영 / 앨범에서 선택</Text>
            </Pressable>
          )}
        </View>

        <View style={styles.field}>
          <Text style={styles.label}>5. 상세 위치 설명 (선택)</Text>
          <Text style={styles.help}>
            적어두면 다음 사람이 찾기 쉬워요. 사진으로 충분하다면 비워두셔도 됩니다.
          </Text>
          <TextInput
            value={detailText}
            onChangeText={setDetailText}
            placeholder="예: 1층 픽업대 옆, 정수기와 나란히 있어요."
            placeholderTextColor="#9CA3AF"
            style={[styles.input, styles.textArea]}
            multiline
            maxLength={300}
          />
        </View>

        <PrimaryButton label="등록하기" onPress={submit} loading={isSubmitting} />
        <Text style={styles.footnote}>
          등록된 위치는 &lsquo;미확인&rsquo; 상태로 표시되며, 다른 사용자의 리뷰가 쌓이면 신뢰도가
          올라갑니다.
        </Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  content: { padding: Spacing.three, gap: Spacing.four, paddingBottom: Spacing.six },
  field: { gap: Spacing.two },
  labelRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two },
  label: { fontSize: 16, fontWeight: '800', color: '#111827' },
  help: { fontSize: 13, color: Brand.muted },
  mapWrapper: { height: 220, borderRadius: 16, overflow: 'hidden', backgroundColor: '#F3F4F6' },
  map: { flex: 1 },
  linkButton: { alignSelf: 'flex-start', paddingVertical: Spacing.one },
  linkText: { fontSize: 15, fontWeight: '700', color: Brand.primary },
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
  photoButton: {
    borderWidth: 1,
    borderColor: Brand.border,
    borderStyle: 'dashed',
    borderRadius: 16,
    paddingVertical: Spacing.five,
    alignItems: 'center',
    backgroundColor: '#FAFAFA',
  },
  photoButtonText: { fontSize: 15, fontWeight: '700', color: Brand.primary },
  preview: { width: '100%', height: 200, borderRadius: 16, backgroundColor: '#F3F4F6' },
  footnote: { fontSize: 13, color: Brand.muted, lineHeight: 20 },
});
