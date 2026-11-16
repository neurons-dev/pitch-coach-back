## 🚀 프로젝트 소개

발표 연습 음성을 업로드하면 AI가 분석해 피드백을 주는 발표 코칭 서비스 "Pitch Coach"의 백엔드 리포지토리입니다.

> "발표 연습, 혼자서도 제대로 피드백 받을 수 없을까?"

발표를 준비할 때 가장 어려운 점은 내 발표를 객관적으로 평가받기 어렵다는 것입니다.
Pitch Coach는 연습한 발표 음성을 올리면 말하기 속도, 발음, 습관어(“음…”, “어…”), 내용 구성을 AI가 분석해 지표별 점수와 개선 피드백을 제공합니다.
연습 기록이 쌓이면 최근 분석 결과를 비교하며 스스로의 성장을 확인할 수 있습니다.

### 📅 개발 기간

2026.07 ~ 2026.08

### ✨ 주요 기능

- **회원**: 이메일 회원가입 · 로그인, Kakao · Google 소셜 로그인, 프로필 이미지, 비밀번호 변경, 탈퇴
- **발표 연습 세션**: 연습 유형과 목표 시간을 정해 세션 생성, 발표 음성 업로드
- **AI 분석**: 분석 요청 → 진행 상태 조회 → 결과 조회의 비동기 분석 흐름
- **분석 결과**: 지표별 점수와 항목별 피드백, 최근 분석 결과 목록

### 🏗️ 아키텍처

무거운 음성 분석을 FastAPI 서버로, 요청 처리 및 응답은 Spring 서버로 분리한 폴리글랏 아키텍처입니다.

```
Client ─▶ Nginx ─┬─▶ core-service (Spring Boot) ─▶ PostgreSQL / S3
                 │          │ 분석 작업 요청 · 상태 조회
                 │          ▼
                 └─▶ analysis-service (FastAPI) ─▶ 음성 인식 · AI 분석
```

- `core-service` : 사용자 · 인증 · 발표 연습 세션 · 분석 결과를 담당하는 Spring Boot 서버
- `analysis-service` : 음성 인식과 발표 분석을 담당하는 FastAPI 서버
- 두 서비스는 공유 Docker 네트워크로 통신하며, GitHub Actions(OIDC)로 서비스별 ECR · EC2 자동 배포됩니다.

## 🛠️ 기술 스택

![Java](https://img.shields.io/badge/Java-ED8B00?style=for-the-badge&logo=openjdk&logoColor=white)
![Spring Boot](https://img.shields.io/badge/Spring%20Boot-6DB33F?style=for-the-badge&logo=springboot&logoColor=white)
![Spring Security](https://img.shields.io/badge/Spring%20Security-6DB33F?style=for-the-badge&logo=springsecurity&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-232F3E?style=for-the-badge&logo=amazonwebservices&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Nginx](https://img.shields.io/badge/Nginx-009639?style=for-the-badge&logo=nginx&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)

## 🫱🏻‍🫲🏻 멤버

<table>
  <tr>
    <td align="center" width="200px">
      <img src="https://github.com/imdongyoung.png" />
      임동영<br/>
      <b>imdongyoung</b><br/>
      <a href="https://github.com/imdongyoung">@imdongyoung</a>
    </td>
    <td align="center" width="200px">
      <img src="https://github.com/yxxjxxeee.png" />
      윤지은<br/>
      <b>yxxjxxeee</b><br/>
      <a href="https://github.com/yxxjxxeee">@yxxjxxeee</a>
    </td>
  </tr>
</table>
