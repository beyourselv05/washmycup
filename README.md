# CupPit (가제)

> 텀블러를 안 쓰는 이유는 깜빡해서가 아니라, 씻는 게 귀찮아서다.
흩어진 텀블러 세척기 위치를 지도로 모으고, AI가 지금 이용 가능한지 알려주는 앱.
> 

---

## 프로젝트 소개 (바이브톤 해커톤)

- **행사**: 멋쟁이사자처럼 AI 바이브톤 (2026.9.3)
- **주제**: 불편함을 해결하는 AI 서비스 (환경 카테고리)
- **팀**: 7조, 5인 (발표 2인, 개발 3인)

<!-- 여기에 앱 스크린샷/데모 GIF 넣기 -->

---

## 문제 정의

텀블러 사용을 권장하는 캠페인은 많지만, 실제로 사람들이 텀블러를 안 쓰는 가장 흔한 이유는 세척이 번거로워서다.

LG전자의 무료 세척기 마이컵(myCup)이 이미 설치되어 있지만:

- 설치 위치가 흩어져 있고, LG전자 이외의 타 브랜드 등 통합된 정보가 없다.
- 대표 브랜드 앱을 찾아봐도 안 나오는 세척기가 실제로 존재한다

**CupPit은 "어디에 세척기가 있고, 지금 쓸만한지"를 알려주는 정보 레이어를 채운다.**

---

## 핵심 기능

1. **통합 지도** — 파악된 세척기 위치 + 사용자 등록 위치를 함께 표시
2. **위치 등록** — 사진 필수 업로드 + 상세 위치 설명으로 크라우드소싱
3. **리뷰 (👍/👎 + 태그)** — 실사용자 피드백 축적
4. **AI 신뢰도 리포트** — 리뷰 텍스트를 Gemini가 요약해 "지금 이용 가능 확률" 제공
5. **신고 & 관리** — Django Admin에서 허위/부적절 등록 검토·삭제
6. **인프라 공백 리포트** — 사용자 동선 대비 세척기 부족 지역 데이터화 (지자체 제안 자료로 확장 가능)

---

## 기술 스택

**Frontend**: React Native (Expo), TypeScript, React Navigation, react-native-maps, expo-image-picker

**Backend**: Django, Django REST Framework, SQLite, django-cors-headers

**AI**: Google Gemini 3.6 Flash (리뷰 요약 · 신뢰도 판단)

---

## 시스템 아키텍처

```
[Expo 앱] --REST API--> [Django/DRF] --읽기/쓰기--> [SQLite DB]
                              │                          ↑
                              │                     [Django Admin]
                              └──온디맨드 호출──> [Gemini 3.6 Flash]
```

리뷰 요약이 필요할 때만 Gemini API를 호출하는 온디맨드 구조. 신고 관리는 별도 화면 없이 Django Admin으로 처리.

---

## AI를 어디에 쓰고, 어디엔 안 쓰는가

| 기능 | AI 사용 | 이유 |
| --- | --- | --- |
| 지도 표시 | ❌ | 단순 데이터 시각화 |
| 위치 등록 | ❌ | 사용자 직접 입력 |
| **리뷰 요약 + 신뢰도 판단** | ✅ | 정형 태그로 못 잡는 패턴을 자연어에서 추출 |
| **인프라 공백 리포트** | ✅ | 동선 데이터와 위치 데이터의 교차 패턴 분석 |
| 신고 처리 | ❌ (의도적) | 최종 삭제는 관리자가 판단 |

---

## 실행 방법 (로컬)

### 요구 사항

- Python 3.12 이상
- Node.js 18 이상
- uv (파이썬 패키지 매니저)

### Backend
```bash
cd washmycup-backend
uv venv --python 3.12 venv
source venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env              # GEMINI_API_KEY, DJANGO_SECRET_KEY 채우기
python manage.py migrate
python manage.py seed_locations --with-reviews   # 초기 시드 데이터 + 데모용 리뷰
python manage.py createsuperuser  # Django Admin 계정
python manage.py runserver
```

- API: http://127.0.0.1:8000/api/locations/
- 관리자(신고 목록): http://127.0.0.1:8000/admin/locations/report/

### Frontend
```bash
cd washmycup-app
npm install
npx expo start
# 폰의 Expo Go 앱으로 터미널의 QR 코드 스캔 (맥과 같은 와이파이)
```

> **Expo SDK 54 고정** — 앱스토어/플레이스토어의 Expo Go가 SDK 54에 머물러 있어서,
> 스토어에서 받은 Expo Go로 QR을 찍으려면 프로젝트도 SDK 54여야 합니다.
> Expo Go의 제작사는 `650 Industries, Inc.`입니다. 설치 시 확인하세요.
>
> ⚠️ **모르는 사람이 보낸 Expo Go QR/링크는 절대 열지 마세요.** Expo Go는 QR이 가리키는
> 코드를 그대로 실행하는 도구라, 이를 악용해 연락처·사진을 빼가는 피싱 수법이 있습니다.
> 내 개발 서버가 띄운 QR을 찍는 것은 안전합니다.

백엔드 주소는 Expo 개발 서버 주소에서 자동으로 유도되므로(`src/constants/config.ts`),
시뮬레이터든 실물 폰이든 따로 고칠 필요가 없습니다.

`.env` 파일에 `GEMINI_API_KEY` 설정 필요 (`.env.example` 참고)

---

## API 엔드포인트

| Method | 경로 | 설명 |
| --- | --- | --- |
| GET | `/api/locations/` | 위치 목록 (삭제됨 제외, 👍/👎 집계 포함) |
| POST | `/api/locations/` | 위치 등록 (multipart, 사진·상세설명 필수) |
| GET | `/api/locations/{id}/` | 위치 상세 + 리뷰 목록 |
| GET·POST | `/api/locations/{id}/reviews/` | 리뷰 조회 / 작성 |
| GET | `/api/locations/{id}/reliability/` | AI 신뢰도 리포트 `{score, summary}` |
| POST | `/api/locations/{id}/report/` | 신고 등록 (처리는 Django Admin) |

신고가 접수되면 해당 위치는 `reviewing` 상태로 바뀌고, 관리자가 Admin에서 `removed`로 바꾸면 목록 API에서 사라진다.

---

## 향후 확장 방향

- 카본페이 참여기업 등록을 통한 실제 포인트 연동
- 인프라 공백 리포트를 지자체 세척기 설치 제안 근거자료로 활용
- 데이터 소스 확대