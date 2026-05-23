import os
from datetime import datetime
import json
import base64
from email.message import EmailMessage

from dotenv import load_dotenv
from pyexpat import model

# load_dotenv 함수를 사용해서 각각 다른 경로를 부르는 걸로 해결...
load_dotenv("auth/.env")
load_dotenv(".env")

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build  # Gmail API 서비스 빌드를 위해 추가

from apis.activitywatch import get_today_apps

if __name__ == "__main__":
    print("오늘의 집중도 리포트 생성중....")
    print("=" * 50)

    # 2가지의 로그를 읽은 거 => 내부 JSON 집중도 측정 로그 / activity_watch의 localDB
    # 집중도 측정 로그 읽기

    # 오늘의 today log를 찾기 위함
    today = datetime.now().strftime("%Y-%m-%d")

#===============
# error: 로그 저장/조회 파일 경로 불일치 해결
    log_path = f"data/log_{today}.json"



    logs = []
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            logs = json.load(f)

    print(f"오늘의 측정 기록: {len(logs)}건 측정 완료")

    # 로그 텍스트 파싱
    if logs:
        total = len(logs)
        distracted = 0
        for l in logs:
            if l.get("distracted"):  # key = distracted에서 방해를 받았지는 안 받았는지 True/False로 넣음
                distracted += 1
        
        score_sum = 0
        for l in logs:
            score_sum += l.get("score", 0)
        avg_score = score_sum // total  # 평균적인 점수를 냄 -> 다 합해서 평균
        
        log_text = f"총 {total}회 측정됨 | 딴짓 {distracted}회 | 평균 집중점수 {avg_score}점\n\n"
        for l in logs:
            flag = " 딴짓" if l.get("distracted") else "집중"
            score = l.get("score", "?")  # 없으면 ? get으로 수정
            t = l.get("check_time", "")[-8:-3]
            task = l.get("task_name", "미지정")  # task도 get으로 수정
            log_text += f"  [{t}] {flag} {score}점 | {task}\n"
    else:
        log_text = "측정 기록 없음"

    # Activity Watch 앱 내역을 가져오기

    """
    aw-watcher-window (로컬 앱 버킷):
    aw-watcher-web (웹 브라우저 버킷):
    """
    print("ActivityWatch 데이터 수집 중...")
    apps = get_today_apps()  # 함수 불러오기
    
    # 1분 미만은 제거
    # 계속해서 앱이 바뀌는 순간까지 포착을 하기 때문에 많은 로그들이 나옴 -> 1분 미만은 제거함
    filtered_apps = []
    for a in apps:
        if a["minutes"] >= 1.0:
            filtered_apps.append(a)
    apps = filtered_apps

    if apps:
        aw_text = ""
        web_items = []
        app_items = []
        # 둘의 데이터가 겹치지 않는 부분이 있어서 나눔
        for a in apps:
            if a["source"] == "web":
                web_items.append(a)
            else:
                app_items.append(a)

        if app_items:
            aw_text += "====== 로컬 앱 =========="
            for item in app_items[:20]:  # 일단은 다 보여주는 게 아니라 상위(정렬이 되어서 받아옴) 20개만
                # 형식을 맞추기
                aw_text += f"  {item['app']} | {int(item['minutes'])}분 | {item['title'][:50]}\n"

        if web_items:
            aw_text += "\n=== 브라우저 탭 ===\n"
            for item in web_items[:35]:
                # 웹은 chrome / edge의 이름만이 나오ㅓ기 때문에 ['app']은 빼고 적음
                aw_text += f"  {int(item['minutes'])}분 | {item['title'][:50]}\n"

                if item.get("url"):  # url 주소가 있으면
                    aw_text += f"    ㄴ-----{item['url']}"

        total_mins = 0
        for a in apps:
            total_mins += a["minutes"]
        aw_text += f"\n total 컴퓨터 사용: {int(total_mins)}분 ({int(total_mins / 60)}시간)"  # 시간/분으로 바꾸기 --- 보기 안좋음
    else:
        aw_text = "ActivityWatch의 데이터 없음"

    print("======Activity Watch 데이터 로드 완료======")

    # Gemini로 리포트 생성
    print("Gemini로 리포트 작성 중")
    print("===============")
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)

    # LangChain의 SystemMessage는 context가 아니라 content 매개변수를 받습니다.
    system = SystemMessage(content="""
        너는 학생의 하루 공부를 분석해주는 AI 코치야. 주어진 데이터를 보고 한국어로 리포트를 작성해줘

        출력 형식:
        ------------------------
        1. 오늘의 집중도 요약: 측정 통계 요약
        2. 잘한 점: 구체적으로 집중한 시간이나 구체적인 task 명시
        3. 반성할 점: 데이터를 근거로 아쉬운점 하나
        4. 내일을 위한 조언 하나
        5. 오늘의 생산성 점수: XX 점 / 100 점
    """)

    # 전역 레벨이 아닌 if __name__ 내부로 들여쓰기하여 NameError 방지
    user = HumanMessage(content=f"""
[집중도 측정 기록]
{log_text}

[ActivityWatch 앱/웹 사용 내역]
{aw_text}""")

    # 아까 만들었던 log_text => 내부 JSON으로 스크린샷으로 캡처를 한 것
    # aw_text => 외부 API 로 부터 받은 상위 30개의 목록

    response = llm.invoke([system, user])
    report = response.content

    print(report)

    # 4. 이메일 발송
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
    msg["Subject"] = f"오늘의 집중도 리포트 ({datetime.now().strftime('%m월 %d일')})"
    msg["From"] = my_email
    msg["To"] = my_email
    msg.set_content(report)  # 속성 대입(=)이 아닌 메서드 함수 호출로 수정

    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": encoded}).execute()
    print("이메일로 보냈습니다!")

