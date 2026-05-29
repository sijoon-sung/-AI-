import os
import sys
import json
import base64
from datetime import datetime
from email.message import EmailMessage
from dotenv import load_dotenv

# 한글 깨짐 방지 설정
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# 환경 변수 로드 (.env 설정)
load_dotenv("auth/.env")
load_dotenv(".env")

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from apis.activitywatch import gettodayapphistory

if __name__ == "__main__":
    print("오늘의 집중도 리포트 생성중....")
    print("=" * 50)

    # 오늘의 JSON 파일 읽기
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = f"data/log_{today}.json"

    logs = []
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            logs = json.load(f)

    print(f"오늘의 측정 기록: {len(logs)}건 측정 완료")

    if logs:
        total = len(logs)
        # 땃짓 횟수
        distracted = sum(1 for l in logs if l.get("distracted"))
        # 평균 점수
        score_sum = sum(l.get("score", 0) for l in logs)
        avg_score = score_sum // total

        log_text = f" {total}회 | 딴짓 {distracted} | 평균 집중점수 {avg_score}점\n\n"

        # 상세 내역 텍스트
        for l in logs:
            flag = " 딴짓" if l.get("distracted") else "집중"
            score = l.get("score", "?")
            time_str = l.get("check_time", "")[-8:-3]  # hh:mm 형식
            task = l.get("task_name", "미지정")
            log_text += f"  [{time_str}] {flag} {score}점 | {task}\n"
    else:
        log_text = "측정 기록 없음"

    # Activity Watch 기록 가져옴
    apps = gettodayapphistory()

    # 1분 미만 ---> 필터링
    apps = [a for a in apps if a["minutes"] >= 1.0]

    if apps:
        aw_text = ""

        # 로컬 앱 / web 분리
        app_items = [a for a in apps if a["source"] != "web"]
        web_items = [a for a in apps if a["source"] == "web"]

        if app_items:
            aw_text += "로컬 앱:"
            for item in app_items[:20]:  # 상위 20개만 출력
                aw_text += f"  {item['app']} | {int(item['minutes'])}분 | {item['title'][:50]}\n"

        if web_items:
            aw_text += "브라우저 탭: "
            for item in web_items[:35]:  # 상위 20개만 출력
                aw_text += f"  {int(item['minutes'])}분 | {item['title'][:50]}\n"
                if item.get("url"):
                    aw_text += f" : {item['url']}\n"

        # 오늘 총 사용 시간 계산 (sum 사용)
        total_mins = sum(a["minutes"] for a in apps)
        aw_text += f"\n total 컴퓨터 사용: {int(total_mins)}분 ({int(total_mins / 60)}시간)"
    else:
        aw_text = "ActivityWatch의 데이터 없음"

    print("Activity Watch 데이터 로드 완료")

    #  리포트 생성
    print("Gemini로 리포트 작성 중.")
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)

    system_message = SystemMessage(content="""
        너는 학생의 하루 공부를 분석해주는 AI야. 준 데이터를 보고 리포트를 작성해줘

        출력 형식:
        ------------------------
        1. 오늘의 집중도 요약: 통계요약
        2. 잘한 점: 구체적으로 집중한 시간이나 구체적인 task 명시
        3. 반성할 점: 데이터를 근거로 아쉬운점 하나
        4. 내일의 조언 하나
        5. 생산성 점수: XX 점 / 100 점
    """)

    user_message = HumanMessage(content=f"""
[집중도 측정 기록]
{log_text}

[Activitywatch 내역]
{aw_text}""")

    # AI 호출 + 결과
    response = llm.invoke([system_message, user_message])
    report = response.content
    print(report)

    # Gmail API -----> 나에게 메일 전송
    print("이메일 발송 중...")
    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
    creds = None
    service = None

    # 기존 토큰 불러오기
    if os.path.exists("auth/token.json"):
        creds = Credentials.from_authorized_user_file("auth/token.json", SCOPES)

    # 토큰이 없으면 새로 로그인
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file("auth/client_secret.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("auth/token.json", "w") as f:
            f.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds)

    my_email = os.getenv("MY_EMAIL", "sijoon0404@gmail.com")

    msg = EmailMessage()
    msg["Subject"] = f"집중도 리포트 :({datetime.now().strftime('%m월 %d일')})"
    msg["From"] = my_email
    msg["To"] = my_email
    msg.set_content(report)

    # 이메일 변환 후 발송
    encoded_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": encoded_message}).execute()

    print("이메일이 정상적으로 전송")