# 분석 정확도 baseline

발음, 필러, 발표 구조 분석 방식의 변경 전후를 동일한 입력으로 비교하기 위한 오프라인 평가 도구다. 운영 요청이나 일반 단위 테스트에서는 실행하지 않는다.

## 구성

- `samples/validation_samples.json`: 한국어 발표문, 필러 위치, 정상 표현, 구조 요소와 사람 기준 점수
- `generate_tts.ps1`: Windows SAPI의 한국어 음성으로 로컬 TTS WAV 생성
- `capture_audio_baseline.py`: TTS를 현재 Faster Whisper와 로컬 발음 평가기에 통과시켜 관측값 저장
- `runner.py`: 필러 Precision/Recall/F1, 구조 점수 일치도, 발음 비교 지표 생성
- `compare.py`: 동일한 샘플로 생성한 기존 baseline과 개선 후보 결과 비교
- `baselines/coach-ko-v1.json`: 고정 단어 기반 기존 결과
- `PUBLIC_AUDIO_SOURCES.md`: 공개 한국어 음성 후보의 출처, 라이선스, 채택 여부

## 실행

Analysis Service 디렉터리에서 실행한다.

```powershell
powershell -ExecutionPolicy Bypass -File evaluation/generate_tts.ps1
python -m evaluation.capture_audio_baseline --model-size tiny
python -m evaluation.runner
```

텍스트 기반 baseline만 갱신하려면 마지막 명령만 실행하면 된다. 생성된 WAV는 음성 사용 조건이 명확하지 않은 상태에서 재배포되지 않도록 Git에서 제외한다. `audio_observations.json`에는 WAV 해시와 현재 STT·발음 점수만 기록한다.

개선한 점수 규칙의 결과를 별도 파일로 생성한 뒤 기존 baseline과 비교한다.
비교 도구는 샘플셋 해시를 확인해 발표문이나 정답 라벨이 달라진 결과끼리 비교되는 것을 막는다.

```powershell
python -m evaluation.runner
python -m evaluation.compare evaluation/baselines/coach-ko-v1.json evaluation/baselines/coach-ko-v2.local.json --output evaluation/baselines/coach-ko-v1-v2-comparison.json
```

`runner.py`는 현재 `FILLER_DETECTOR` 설정을 사용한다. 기본값은 `openai`이며 API 키가 필요하다. 필러 탐지 모델은 `FILLER_DETECTOR_MODEL`(기본값 `gpt-4o`)로 피드백 생성용 `OPENAI_MODEL`과 분리되어 있다 — 문맥 판단 정확도가 중요해 `gpt-4o-mini`보다 정밀도가 높은 모델을 기본으로 쓴다. 결과에는 탐지기, 모델, 프롬프트 버전과 폴백 사유가 포함된다. LLM 결과는 모델 업데이트에 따라 달라질 수 있으므로 생성된 v2 결과와 비교 파일은 Git에 커밋하지 않고 PR 검증 결과에 Precision, Recall, F1과 주요 오탐만 기록한다.

## 평가 기준

- 필러: 정답 문자 위치와 탐지 문자 위치를 비교해 Precision, Recall, F1 계산
- 구조: 사람이 부여한 점수와 현재 STRUCTURE 점수의 MAE, 완전 일치율, 10점 이내 일치율 계산
- 발음: `useForAccuracy=true`이며 사람 점수가 있는 실제 사람 음성만 MAE와 Pearson 상관계수에 포함

TTS는 STT부터 발음 평가기까지 파이프라인이 동작하는지 확인하는 용도다. 합성 음성의 발음 점수는 저장하지만 정확도의 정답에는 포함하지 않는다.

## 한국어 NLP 도구 검토

- Kiwi는 형태소와 품사 정보를 제공하지만 `그`, `이제`, `약간`이 문맥상 불필요한 말버릇인지 직접 판정하지 않는다.
- KoNLPy 계열은 JVM 등 운영 의존성이 추가되지만 필러 판정 기능을 제공하지 않는다.
- 따라서 별도 형태소 분석기는 추가하지 않고, 로컬에서는 후보 위치·반복·말 더듬음·문장 중단과 timestamp를 추출하며 LLM이 문맥상 필러 여부를 판정한다.
- LLM 장애 시에는 `어`, `음`, `뭐랄까`만 세는 보수적 폴백을 사용한다.

## 공개·사람 음성 추가 기준

- 공개 음성은 원본 URL, 라이선스, 이용 조건을 `audio.source`와 `audio.usage`에 기록한다.
- 사람 음성은 녹음, 분석, 저장에 동의한 경우만 추가하고 동의 증빙 위치를 메타데이터에 기록한다.
- 실제 사람 음성에는 최소 2명의 평가 점수를 `pronunciation.humanScores`에 기록한다.
- 개인 음성 원본은 공개 저장소에 커밋하지 않는다.
