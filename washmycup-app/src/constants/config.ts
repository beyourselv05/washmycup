import Constants from 'expo-constants';

/**
 * 백엔드 주소.
 *
 * 시뮬레이터는 localhost로 맥에 붙지만, 실물 폰은 맥의 LAN IP로 붙어야 한다.
 * Expo 개발 서버가 알려주는 호스트(hostUri)에서 IP를 그대로 뽑아 쓰기 때문에
 * 시뮬레이터든 실물 폰이든 주소를 직접 고칠 필요가 없다.
 *
 * 다른 주소를 쓰고 싶으면 .env에 EXPO_PUBLIC_API_BASE_URL을 넣으면 그 값이 우선한다.
 */

const BACKEND_PORT = 8000;

function resolveHost(): string {
  // 예: "192.168.0.12:8081" 또는 "localhost:8081"
  const hostUri = Constants.expoConfig?.hostUri ?? '';
  const host = hostUri.split(':')[0];
  return host || 'localhost';
}

export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? `http://${resolveHost()}:${BACKEND_PORT}/api`;

/** 서울 시청 근처. 위치 권한이 없을 때 지도의 초기 중심으로 쓴다. */
export const DEFAULT_REGION = {
  latitude: 37.5326,
  longitude: 126.9905,
  latitudeDelta: 0.12,
  longitudeDelta: 0.12,
};
