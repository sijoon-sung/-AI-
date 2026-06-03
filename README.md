# AI 집중력 & 자세 코치 에이전트

AI를 활용해 모니터 화면 캡처, 앱 사용 기록, 실시간 자세를 분석하고 피드백을 주는 프로그램입니다.

## 사전 요구 사항

1. [ActivityWatch](https://activitywatch.net/): 백그라운드에 실행 중이어야 합니다. (http://localhost:5600)
2. **구글 API 키**: `auth/.env` 파일을 만들고 아래 내용을 입력합니다.
   ```env
   GOOGLE_API_KEY="본인의_API_키"
   ```
3. **Google Tasks API 자격증명**: Google Cloud Console에서 **Google Tasks API**를 활성화하고, 발급받은 `client_secret.json` 파일을 `auth/` 폴더에 넣어야 합니다.

## 설치 방법

```bash
# 가상환경 설정 및 활성화
python -m venv .venv
.venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

## 실행 방법

메인 프로그램을 실행합니다. (자세 감시 모듈도 함께 작동합니다.)

```bash
python main.py
```

## 주요 단축키 (`main.py` 콘솔)

- `Enter`: 즉시 상태 측정 및 피드백 받기
- `g`: 목표 작업 및 과목 변경
- `t`: 측정 주기 시간 변경 (기본 10분)
- `q`: 프로그램 종료
