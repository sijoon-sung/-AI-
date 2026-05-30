import os
import json
from datetime import datetime

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# 루트 / 하위 디렉토리 어디서든지 읽을 수 있게 수정
if os.path.exists("auth/.env"):
    load_dotenv("auth/.env", override=True)

else:
    load_dotenv("../auth/.env", override=True)

SCOPES = ["https://www.googleapis.com/auth/tasks"]


def google_login():
    creds = None # # 최종 반환 자격 증명을 담아둘 변수


    if os.path.exists("auth/client_secret.json"):
        tokenpath = "auth/token.json"
        secretpath = "auth/client_secret.json"
    else:
        tokenpath = "../auth/token.json"
        secretpath = "../auth/client_secret.json"
    # 기존에 로그인 -> 토큰이 있다면
    if os.path.exists(tokenpath):
        creds = Credentials.from_authorized_user_file(tokenpath, SCOPES)

    # 토큰이 없는 경우
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        if not creds:
            # client_secret.json 파일이 지정한 위치에 있는지 확인
            if not os.path.exists(secretpath):
                raise FileNotFoundError(
                    f"인증 파일이 없습니다. 지정된 위치를 확인하세요:\n{secretpath}"
                )
            
            print("구글 로그인 창")
            flow = InstalledAppFlow.from_client_secrets_file(secretpath, SCOPES)
            creds = flow.run_local_server(port=0)

        # 새로 발급받은 토큰 저장
        with open(tokenpath, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return creds



def getsubjectlist():
    # 과목(리스트) 목록 반환 - goal(할일) 반환
    service = build("tasks", "v1", credentials=google_login())
    result = service.tasklists().list().execute()

    #  결과에서 id와 title만 추출하여 반환
    items = result.get("items", [])
    resultlist = []

    for item in items:
        resultlist.append({
            "id": item["id"],
            "title": item["title"]
        })
    return resultlist


def getalltodotitles():
    # 모든 할일을 csv 형태(,)로 구분해서 반환
    service = build("tasks", "v1", credentials=google_login())
    # 최대 20개의 할일 조회
    lists = service.tasklists().list(maxResults=20).execute()
    titles = []

    for lst in lists.get("items", []):
        try:
            # 각 list_id에 포함된 실제 할 일(tasks)을 가져옴
            tasks_result = service.tasks().list(tasklist=lst["id"], showCompleted=False).execute()
            tasks = tasks_result.get("items", [])
            for task in tasks:
                # title 만 가져옴
                titles.append(task["title"])
        except Exception as e:
            # 없거나 못 찾는 경우의 예외 처리------> 필요
            print(f"목록 {lst['title']} | 에러: {e}")
            continue
    #
    return ",".join(titles) if titles else "할일 없음"



# 세부 할일도 list로 반환하는 함수
def gettodolist(list_id):
    # list_id의 할일 찾기
    service = build("tasks", "v1", credentials=google_login())
    tasks_result = service.tasks().list(tasklist=list_id, showCompleted=False).execute()

    # id / title만 추출해서 반환
    items = tasks_result.get("items", [])
    resultlist = []
    # {"id": "abc123", "title": "운영체제 과제"} 형태로 dict로 만들어서 반환
    for item in items:
        resultlist.append({
            "id": item["id"],
            "title": item["title"]
        })
    return resultlist


def savetojson(task_name, focus_score, is_distracted):
    # 집중도 측정 결과 => data.json 에 저장
    today = datetime.now().strftime("%Y-%m-%d")
    logpath = f"data/log_{today}.json"  # 날마다 다른 파일
    logs = []

    # 기존에 파일이 있으면 불러오기
    if os.path.exists(logpath):
        with open(logpath, "r", encoding="utf-8") as f:
            logs = json.load(f)
    # 새로운 기록 추가
    logs.append({
        #기록시간 / 작업명 / 집중도 점수 / 딴짓 여부
        "check_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "task_name": task_name,
        "score": focus_score,
        "distracted": is_distracted,
    })
    # JSON으로 저장 + indent 띄어 쓰기 적용
    with open(logpath, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
