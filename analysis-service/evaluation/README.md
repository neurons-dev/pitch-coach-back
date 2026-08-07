# 분석 정확도 baseline

발음, 필러, 발표 구조 분석 방식의 변경 전후를 동일한 입력으로 비교하기 위한 오프라인 평가 도구다. 운영 요청이나 일반 단위 테스트에서는 실행하지 않는다.

## 구성

- `samples/validation_samples.json`: 한국어 발표문, 필러 위치, 정상 표현, 구조 요소와 사람 기준 점수
- `generate_tts.ps1`: Windows SAPI의 한국어 음성으로 로컬 TTS WAV 생성
- `capture_audio_baseline.py`: TTS를 현재 Faster Whisper와 로컬 발음 평가기에 통과시켜 관측값 저장
- `runner.py`: 필러 Precision/Recall/F1, 구조 점수 일치도, 발음 비교 지표 생성
- `compare.py`: 동일한 샘플로 생성한 기존 baseline과 개선 후보 결과 비교
- `baselines/coach-ko-v1.json`: 현재 `SCORING_RULE_VERSION` 기준 결과
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
python -m evaluation.runner --output evaluation/baselines/coach-ko-v2.json
python -m evaluation.compare evaluation/baselines/coach-ko-v1.json evaluation/baselines/coach-ko-v2.json
```

## 평가 기준

- 필러: 정답 문자 위치와 탐지 문자 위치를 비교해 Precision, Recall, F1 계산
- 구조: 사람이 부여한 점수와 현재 STRUCTURE 점수의 MAE, 완전 일치율, 10점 이내 일치율 계산
- 발음: `useForAccuracy=true`이며 사람 점수가 있는 실제 사람 음성만 MAE와 Pearson 상관계수에 포함

TTS는 STT부터 발음 평가기까지 파이프라인이 동작하는지 확인하는 용도다. 합성 음성의 발음 점수는 저장하지만 정확도의 정답에는 포함하지 않는다.

## 공개·사람 음성 추가 기준

- 공개 음성은 원본 URL, 라이선스, 이용 조건을 `audio.source`와 `audio.usage`에 기록한다.
- 사람 음성은 녹음, 분석, 저장에 동의한 경우만 추가하고 동의 증빙 위치를 메타데이터에 기록한다.
- 실제 사람 음성에는 최소 2명의 평가 점수를 `pronunciation.humanScores`에 기록한다.
- 개인 음성 원본은 공개 저장소에 커밋하지 않는다.
