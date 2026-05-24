"""
1._login(): google tasks / Gmail API를 위한 인증 Outh를 진행
특징:
    - 프로젝트 루트 기준으로:Auth 폴더를 자동으로 생성 그 안에 인증 파일을 보관하자: .env/ client.json/ token.json등
    - token.json: 기존에 로그인 새션이 있으면 재사용, 만료되면 갱신함
    - 처음 로그인 하거나 토큰이 깨진 경우에만 cilent_secret.json을 읽음

2. get_task_lists(): 사용자의 구글 task에 생성되어 있는 할일 목록의 이름과 고유한 ID를 반환
형태:
[
    {"id": "ABCDEFGHI...", "title": "운영체제"},
    {"id": "...", "title": "클라우드 AI 프로그래밍"},
    {"id": "...", "title": "기본 목록"}
]

3. get_task_in_list(list_id): 특정한 할일을 지정하면 그 목록안에 포함 안되는 일은 제외하고 보여줌
[
    {"id": ... , "title": "CHP 7 memory management"},
    {"id": , "title": "클라우드 AI 프로그래밍 기말과제 초안"}
]

4. get_all_task_titles(): 최대 20개의 할일을 전부 돌아서 제목만 뽑아서 전달 (프롬프트용 전달)
형태:
CHP 7 memory management 복습,
클라우드 활용 수업듣기,
클라우드 활용 블로그 과제 초안,
클라우드 AI 프로그래밍 기말과제 초안 # 콤마로 구분할 수 있게 join

5. save_log(task_name, focus_score, is_distracted)
역할: 현재 수행 중인 작업명과 집중도 측정 결과를 로컬 JSON 파일에 저장
"""

import os
import json
from datetime import datetime

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv("../auth/.env", override=True)

SCOPES = ["https://www.googleapis.com/auth/tasks", "https://www.googleapis.com/auth/gmail.send"]


def google_login():
    creds = None

    # auth 폴더 경로 지정 (단독 실행 등 경로가 안 맞을 경우 대비)
    tokenpath = "auth/token.json"
    secretpath = "auth/client_secret.json"
    if not os.path.exists(tokenpath):
        tokenpath = "../auth/token.json"
        secretpath = "../auth/client_secret.json"


    if os.path.exists(tokenpath):
        creds = Credentials.from_authorized_user_file(tokenpath, SCOPES)

    # 토큰이 없거 경우
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        if not creds:
            # client_secret.json 파일이 지정한 위치에 있는지 확인
            if not os.path.exists(secretpath):
                raise FileNotFoundError(
                    f"인증 파일이 없습니다. 지정된 위치를 확인하세요:\n{secretpath}"
                )

            print("구글 로그인 창이 열립니다...")
            flow = InstalledAppFlow.from_client_secrets_file(secretpath, SCOPES)
            creds = flow.run_local_server(port=0)

        # 로그인 후 새로 발급받은 토큰 저장
        with open(tokenpath, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return creds



def getsubjectlist():
    # 과목(리스트) 목록 반환
    # [{"id": ..., "title": ...}, ...]
    service = build("tasks", "v1", credentials=google_login())
    result = service.tasklists().list().execute()
    
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
            print(f"목록 {lst['title']} 로딩 중 에러: {e}")
            continue

    return ",".join(titles) if titles else "할일 없음"


#===============
# error: get_tasks_in_list 함수를 따로 만듬 -> list로 쓸 떄
def gettodolist(list_id):
    service = build("tasks", "v1", credentials=google_login())
    tasks_result = service.tasks().list(tasklist=list_id, showCompleted=False).execute()
    
    items = tasks_result.get("items", [])
    resultlist = []
    for item in items:
        resultlist.append({
            "id": item["id"],
            "title": item["title"]
        })
    return resultlist
# ==============

def savetojson(task_name, focus_score, is_distracted):
    # 집중도 측정 결과 => data/log_YYYY-MM-DD.json 에 저장
    today = datetime.now().strftime("%Y-%m-%d")
    logpath = f"data/log_{today}.json"  # 날마다 다른 파일
    logs = []

    if os.path.exists(logpath):
        with open(logpath, "r", encoding="utf-8") as f:
            logs = json.load(f)

    logs.append({
        "check_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "task_name": task_name,
        "score": focus_score,
        "distracted": is_distracted,
    })

    with open(logpath, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print("===과목 목록===")
    try:
        for lst in getsubjectlist():
            print(f"{lst['title']}")
    except Exception as e:
        print(f"과목 목록 가져오기 실패: {e}")

    print("\n==== 전체 할 일 =========")
    try:
        print(getalltodotitles())
    except Exception as e:
        print(f"할 일 목록 가져오기 실패: {e}")