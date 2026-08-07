# Core Service API

`core-service`에 구현된 API 목록입니다. Swagger UI(`/swagger-ui.html`)에서도 동일한 내용을 확인할 수 있습니다.

## 공통 사항

### 인증

- 로그인/토큰 재발급으로 발급받은 `accessToken`을 `Authorization: Bearer {accessToken}` 헤더로 전달합니다.
- `accessToken` 만료 시간: 30분 (`1800000ms`)
- `refreshToken` 만료 시간: 14일 (`1209600000ms`)
- 인증이 필요 없는 경로: `/api/auth/**`, `/oauth2/**`, `/login/**`, `/actuator/**`, `/swagger-ui/**`, `/v3/api-docs/**`
- 그 외 모든 경로는 인증이 필요합니다.

### 공통 에러 응답

```json
{
  "message": "에러 메시지",
  "timestamp": "2026-07-30T12:00:00"
}
```

| 상태 코드 | 설명 |
|---|---|
| 400 | 요청 값 검증 실패, 잘못된 참조 값, 잘못된 요청 본문/경로 변수 |
| 401 | 인증 실패, 잘못되거나 만료된 토큰, 미인증 요청 |
| 403 | 비활성화(차단/탈퇴)된 사용자 |
| 404 | 리소스를 찾을 수 없음 (또는 본인 소유가 아님) |
| 409 | 중복된 리소스, 현재 상태에서 허용되지 않는 요청 |
| 413 | 업로드 파일 크기 초과 (최대 50MB) |
| 415 | 지원하지 않는 Content-Type |
| 500 | 서버 내부 오류 |
| 502 | analysis-service 호출 실패 |

---

## Auth API

### 회원가입

```
POST /api/auth/signup
```

로컬 계정(이메일/비밀번호)으로 회원가입하고 accessToken/refreshToken을 즉시 발급받습니다.

**Request Body**

| 필드 | 타입 | 제약 |
|---|---|---|
| email | string | 필수, 이메일 형식 |
| password | string | 필수, 8~64자 |
| nickname | string | 필수, 최대 50자 |

```json
{
  "email": "user@example.com",
  "password": "password123",
  "nickname": "닉네임"
}
```

**Response** `201 Created`

- `Location: /api/users/{userId}`

```json
{
  "userId": 1,
  "name": "닉네임",
  "email": "user@example.com",
  "accessToken": "eyJhbGciOi...",
  "refreshToken": "raw-refresh-token"
}
```

**에러**
- `409` — 이미 사용 중인 이메일

---

### 로그인

```
POST /api/auth/login
```

로컬 계정 이메일/비밀번호로 로그인하고 토큰을 발급받습니다.

**Request Body**

| 필드 | 타입 | 제약 |
|---|---|---|
| email | string | 필수, 이메일 형식 |
| password | string | 필수 |

**Response** `200 OK`

```json
{
  "userId": 1,
  "name": "닉네임",
  "email": "user@example.com",
  "accessToken": "eyJhbGciOi...",
  "refreshToken": "raw-refresh-token"
}
```

**에러**
- `401` — 이메일 또는 비밀번호 불일치

---

### 소셜 로그인 (Google / Kakao)

```
GET /oauth2/authorization/google
GET /oauth2/authorization/kakao
```

1. 클라이언트가 위 경로로 브라우저를 리다이렉트시켜 소셜 로그인 플로우를 시작합니다.
2. 로그인 성공 시 서버가 프론트엔드로 1회용 `code`를 붙여 리다이렉트합니다: `{FRONTEND_OAUTH_REDIRECT_BASE}?code={code}` (`code`는 60초 내 1회만 사용 가능)
3. 프론트엔드는 아래 코드 교환 API로 `code`를 실제 토큰으로 교환합니다.
4. 로그인 실패 시 `{FRONTEND_OAUTH_REDIRECT_BASE}?error=...` 로 리다이렉트됩니다.

지원 provider: `google`, `kakao`, `apple`(스키마상 예약, 미구현)

---

### 소셜 로그인 코드 교환

```
POST /api/auth/oauth/exchange
```

**Request Body**

| 필드 | 타입 | 제약 |
|---|---|---|
| code | string | 필수, 소셜 로그인 리다이렉트로 받은 1회용 코드 |

**Response** `200 OK` — 회원가입/로그인과 동일한 `AuthResponse` (userId/name/email/accessToken/refreshToken)

---

### 토큰 재발급

```
POST /api/auth/reissue
```

`refreshToken`으로 새 토큰 쌍을 발급받습니다. 기존 `refreshToken`은 즉시 폐기됩니다.

**Request Body**

| 필드 | 타입 | 제약 |
|---|---|---|
| refreshToken | string | 필수 |

**Response** `200 OK` — `TokenResponse`

**에러**
- `401` — 유효하지 않거나 만료/폐기된 refreshToken

---

### 로그아웃

```
POST /api/auth/logout
```

전달한 `refreshToken` 하나만 폐기합니다. 다른 기기의 세션에는 영향이 없습니다.

**Request Body**

| 필드 | 타입 | 제약 |
|---|---|---|
| refreshToken | string | 필수 |

**Response** `204 No Content`

---

## Practice Type API

> 인증 필요 (`Authorization: Bearer {accessToken}`)

### 발표 유형 목록 조회

```
GET /api/practice-types
```

활성화된 발표 유형 목록을 정렬 순서대로 조회합니다.

**Response** `200 OK`

```json
[
  {
    "code": "INTERVIEW",
    "label": "면접형",
    "recommendedMinSec": 180,
    "recommendedMaxSec": 300
  },
  {
    "code": "PT",
    "label": "PT발표형",
    "recommendedMinSec": 300,
    "recommendedMaxSec": 480
  },
  {
    "code": "SPEECH",
    "label": "스피치형",
    "recommendedMinSec": 180,
    "recommendedMaxSec": 300
  }
]
```

---

## Practice Session API

> 인증 필요 (`Authorization: Bearer {accessToken}`)

### 발표 연습 세션 생성

```
POST /api/practice-sessions
```

발표 제목과 유형을 입력해 새 발표 연습 세션을 생성합니다.

**Request Body**

| 필드 | 타입 | 제약 |
|---|---|---|
| title | string | 필수, 최대 100자 |
| practiceTypeCode | string | 필수, `INTERVIEW` / `PT` / `SPEECH` 중 하나 (대소문자 무관) |
| targetDurationSeconds | short | 선택, 목표 발표 시간(초), 1 이상 |

```json
{
  "title": "프론트엔드 개발자 모의면접",
  "practiceTypeCode": "INTERVIEW",
  "targetDurationSeconds": 240
}
```

**Response** `201 Created`, `Location: /api/practice-sessions/{id}`

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "프론트엔드 개발자 모의면접",
  "practiceTypeCode": "INTERVIEW",
  "targetDurationSeconds": 240,
  "status": "CREATED",
  "audioOriginalName": null,
  "audioContentType": null,
  "audioSizeBytes": null,
  "durationMs": null,
  "recordedAt": null,
  "latestAnalysisJobId": null,
  "failureReason": null,
  "analysisCompletedAt": null,
  "overallScore": null,
  "createdAt": "2026-07-30T12:00:00",
  "updatedAt": "2026-07-30T12:00:00"
}
```

**에러**
- `400` — 존재하지 않거나 비활성화된 `practiceTypeCode`, 또는 `targetDurationSeconds`가 0 이하
- `401` — 인증 실패
- `403` — 차단/탈퇴된 사용자

---

### 발표 연습 세션 단건 조회

```
GET /api/practice-sessions/{sessionId}
```

본인 소유의 발표 연습 세션을 조회합니다.

**Path Parameter**

| 이름 | 타입 | 설명 |
|---|---|---|
| sessionId | UUID | 발표 연습 세션 id |

**Response** `200 OK` — 생성 API와 동일한 `PracticeSessionResponse`

**에러**
- `404` — 세션이 존재하지 않거나 본인 소유가 아님
- `401` — 인증 실패

---

### 발표 연습 세션 제목 수정

```
PATCH /api/practice-sessions/{sessionId}
```

본인 소유의 발표 연습 세션 제목을 수정합니다.

**Path Parameter**

| 이름 | 타입 | 설명 |
|---|---|---|
| sessionId | UUID | 발표 연습 세션 id |

**Request Body**

| 필드 | 타입 | 제약 |
|---|---|---|
| title | string | 필수, 최대 100자 |

**Response** `200 OK` — 생성 API와 동일한 `PracticeSessionResponse`

**에러**
- `404` — 세션이 존재하지 않거나 본인 소유가 아님
- `401` — 인증 실패

---

### 발표 연습 세션 음성 파일 업로드

```
POST /api/practice-sessions/{sessionId}/audio
Content-Type: multipart/form-data
```

본인 소유의 발표 연습 세션에 녹음된 음성 파일을 업로드합니다. core-service가 파일을 받아 S3에 업로드합니다. 세션 상태가 `CREATED` 또는 `FAILED`일 때만 업로드할 수 있습니다. 업로드에 성공하면 상태가 `UPLOADED`로 바뀝니다.

**Path Parameter**

| 이름 | 타입 | 설명 |
|---|---|---|
| sessionId | UUID | 발표 연습 세션 id |

**Form Fields**

| 필드 | 타입 | 제약 |
|---|---|---|
| file | file | 필수, 최대 50MB, 지원 형식: `audio/mpeg`, `audio/mp4`, `audio/x-m4a`, `audio/aac`, `audio/wav`, `audio/x-wav`, `audio/wave` |
| durationMs | long | 필수, 녹음 길이(밀리초) — 클라이언트에서 측정한 값을 전달 |

**Response** `200 OK`

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "프론트엔드 개발자 모의면접",
  "practiceTypeCode": "INTERVIEW",
  "targetDurationSeconds": 240,
  "status": "UPLOADED",
  "audioOriginalName": "recording.m4a",
  "audioContentType": "audio/x-m4a",
  "audioSizeBytes": 2456321,
  "durationMs": 184000,
  "recordedAt": "2026-07-30T12:05:00",
  "latestAnalysisJobId": null,
  "failureReason": null,
  "analysisCompletedAt": null,
  "overallScore": null,
  "createdAt": "2026-07-30T12:00:00",
  "updatedAt": "2026-07-30T12:05:00"
}
```

**에러**
- `400` — 지원하지 않는 오디오 형식, 또는 `durationMs`가 0 이하
- `404` — 세션이 존재하지 않거나 본인 소유가 아님
- `409` — 현재 세션 상태에서는 업로드 불가 (`UPLOADED`/`ANALYSIS_REQUESTED`/`COMPLETED` 상태)
- `413` — 파일 크기 초과 (최대 50MB)
- `401` — 인증 실패
- `500` — S3 업로드 실패

---

### 발표 분석 요청

```
POST /api/practice-sessions/{sessionId}/analysis
```

본인 소유의 발표 연습 세션에 대해 analysis-service에 분석 작업을 요청합니다. core-service는 인증·소유권 검증 후 analysis-service의 내부 API로 요청을 위임합니다. 세션 상태가 `UPLOADED`일 때만 요청할 수 있습니다. 성공하면 상태가 `ANALYSIS_REQUESTED`로 바뀝니다.

**Path Parameter**

| 이름 | 타입 | 설명 |
|---|---|---|
| sessionId | UUID | 발표 연습 세션 id |

**Response** `200 OK`

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "프론트엔드 개발자 모의면접",
  "practiceTypeCode": "INTERVIEW",
  "targetDurationSeconds": 240,
  "status": "ANALYSIS_REQUESTED",
  "audioOriginalName": "recording.m4a",
  "audioContentType": "audio/x-m4a",
  "audioSizeBytes": 2456321,
  "durationMs": 184000,
  "recordedAt": "2026-07-30T12:05:00",
  "latestAnalysisJobId": "9c6b6e2a-1f3a-4b0a-9d3a-2f7e6a1c5b90",
  "failureReason": null,
  "analysisCompletedAt": null,
  "overallScore": null,
  "createdAt": "2026-07-30T12:00:00",
  "updatedAt": "2026-07-30T12:06:00"
}
```

**에러**
- `404` — 세션이 존재하지 않거나 본인 소유가 아님
- `409` — 세션 상태가 `UPLOADED`가 아님
- `401` — 인증 실패
- `502` — analysis-service 호출 실패

---

## Analysis API

> 인증 필요 (`Authorization: Bearer {accessToken}`)

### 최근 분석 결과 조회

```
GET /api/analyses/recent
```

본인 소유 세션 중 분석이 완료된(`status: COMPLETED`) 것만 `analysisCompletedAt` 최신순으로 조회합니다.

**Query Parameter**

| 이름 | 타입 | 설명 |
|---|---|---|
| limit | int | 선택, 기본값 4, 1 이상 |

**Response** `200 OK`

```json
[
  {
    "analysisId": "9c6b6e2a-1f3a-4b0a-9d3a-2f7e6a1c5b90",
    "title": "취업 면접 연습",
    "createdAt": "2026-08-01T10:00:00",
    "durationSeconds": 125,
    "totalScore": 82
  }
]
```

`analysisId`는 `latestAnalysisJobId` 값으로, 분석 상태/결과 조회 API의 `{analysisJobId}` 경로 값과 동일합니다.

**에러**
- `400` — `limit`이 1 미만
- `401` — 인증 실패

---

### 분석 진행 상태 조회

```
GET /api/analyses/{analysisJobId}/status
```

분석 작업의 진행 상태를 조회합니다. `analysisJobId`는 분석 요청 API 응답의 `latestAnalysisJobId` 값입니다. 본인이 요청한 분석 작업만 조회할 수 있습니다. 조회 시점에 analysis-service의 상태가 `completed`/`failed`/`cancelled`로 확인되면, 해당 세션의 `status`/`failureReason`/`analysisCompletedAt`이 함께 동기화됩니다.

**Path Parameter**

| 이름 | 타입 | 설명 |
|---|---|---|
| analysisJobId | UUID | 분석 작업 id |

**Response** `200 OK`

```json
{
  "practiceSessionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "analysisJobId": "9c6b6e2a-1f3a-4b0a-9d3a-2f7e6a1c5b90",
  "status": "processing",
  "currentStep": "stt",
  "progress": 40,
  "errorMessage": null
}
```

`status`는 analysis-service의 원본 상태값입니다: `queued` / `processing` / `completed` / `failed` / `cancelled`

**에러**
- `404` — 분석 작업이 존재하지 않거나 본인 소유가 아님
- `401` — 인증 실패
- `502` — analysis-service 호출 실패

---

### 분석 결과 조회

```
GET /api/analyses/{analysisJobId}/result
```

분석 결과(종합 점수, 코치 코멘트, 지표별 점수, 피드백)를 조회합니다. 조회 시 `practice_sessions.overall_score`/`status`가 함께 갱신됩니다.

내부적으로는 analysis-service의 `GET /internal/v1/analysis-jobs/{id}` 응답에 담긴 `result` 필드(완료 전엔 `null`)를 그대로 사용합니다 — 별도의 결과 전용 API가 있는 게 아니라, 분석 요청 상태 조회 API 하나에 결과가 함께 내려옵니다. 판단 기준은 로컬에 캐시된 세션 상태가 아니라 **매 요청마다 analysis-service에 직접 물어보는 실시간 상태**라서, `/status`를 먼저 폴링하지 않고 바로 `/result`를 호출해도 정상 동작합니다.

**Path Parameter**

| 이름 | 타입 | 설명 |
|---|---|---|
| analysisJobId | UUID | 분석 작업 id |

**Response** `200 OK`

```json
{
  "practiceSessionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "analysisJobId": "9c6b6e2a-1f3a-4b0a-9d3a-2f7e6a1c5b90",
  "overallScore": 82,
  "coachComment": "전반적으로 안정적인 발표였습니다...",
  "speechRateScore": 80,
  "fillerWordScore": 79,
  "structureScore": 88,
  "deliveryScore": 78,
  "feedback": [
    { "metricCode": null, "itemType": "summary", "title": "전체 요약", "description": "..." },
    { "metricCode": "SPEED", "itemType": "improvement", "title": "말하기 속도 개선", "description": "..." }
  ]
}
```

`speechRateScore`/`fillerWordScore`/`structureScore`/`deliveryScore`는 analysis-service의 metricScores 중 각각 `SPEED`/`FILLER`/`STRUCTURE`/`DELIVERY` 지표 점수입니다. analysis-service가 해당 지표를 내려주지 않으면 `null`입니다. analysis-service는 이 외에도 `PRONUNCIATION`/`FLUENCY` 지표를 함께 내려줄 수 있지만, 현재 응답에는 포함하지 않습니다.

**에러**
- `404` — 분석 작업이 존재하지 않거나 본인 소유가 아님
- `409` — 아직 분석이 진행 중이거나(`queued`/`processing`), 분석이 실패함(`failed`/`cancelled`) — 메시지로 구분됨
- `401` — 인증 실패
- `502` — analysis-service 호출 실패

---

## 상태 값 참고

`practiceSessions.status`

| 값 | 의미 |
|---|---|
| `CREATED` | 세션 생성됨, 음성 미업로드 |
| `UPLOADED` | 음성 업로드 완료 |
| `ANALYSIS_REQUESTED` | 분석 요청됨, 진행 중 |
| `COMPLETED` | 분석 완료. `GET /api/analyses/{id}/result`로 점수·피드백 조회 가능 |
| `FAILED` | 분석 실패 (`failureReason` 참고) |

`practiceTypeCode`

| 값 | 라벨 |
|---|---|
| `INTERVIEW` | 면접형 |
| `PT` | PT발표형 |
| `SPEECH` | 스피치형 |
