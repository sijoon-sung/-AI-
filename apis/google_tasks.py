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
특징: data/log_YYYY-MM-DD.json 형태로 날짜별로 분리해서 저장, 기존에 있으면 append


"""

import os
import json
import logging
from datetime import datetime

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv("../auth/.env", override=True)

logger = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/tasks", "https://www.googleapis.com/auth/gmail.send"]


def _login():
    creds = None

    # 폴더 경로에 대한 오류를 AI의 도움으로 해결함 -----------------------------------
    # 1. 현재 파일(apis/google_tasks.py) 기준 최상위 프로젝트 루트 경로 계산
    current_dir = os.path.dirname(os.path.abspath(__file__))  # apis 폴더
    project_root = os.path.dirname(current_dir)  # PythonProject 루트 폴더

    # 2. 루트 폴더 아래의 auth 폴더 및 파일 경로 설정
    auth_dir = os.path.join(project_root, "auth")
    os.makedirs(auth_dir, exist_ok=True)  # 폴더가 없으면 자동 생성

    token_path = os.path.join(auth_dir, "token.json")
    secret_path = os.path.join(auth_dir, "client_secret.json")


    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except:
            pass

    # 4. 토큰이 없거나 만료된 경우 처리
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except:
                creds = None

        if not creds:
            # client_secret.json 파일이 지정한 위치에 있는지 확인
            if not os.path.exists(secret_path):
                raise FileNotFoundError(
                    f"인증 파일이 없습니다. 지정된 위치를 확인하세요:\n{secret_path}"
                )

            print("구글 로그인 창이 열립니다...")
            flow = InstalledAppFlow.from_client_secrets_file(secret_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # 로그인 후 새로 발급받은 토큰 저장
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return creds



def get_task_lists():
    # 과목(리스트) 목록 반환
    # [{"id": ..., "title": ...}, ...]
    service = build("tasks", "v1", credentials=_login())
    result = service.tasklists().list().execute()
    
    items = result.get("items", [])
    result_list = []
    for item in items:
        result_list.append({
            "id": item["id"],
            "title": item["title"]
        })
    return result_list


def get_all_task_titles():
    # 모든 할일을 csv 형태(,)로 구분해서 반환
    service = build("tasks", "v1", credentials=_login())
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
            logger.error(f"목록 {lst['title']} 로딩 중 에러: {e}")
            continue

    return ",".join(titles) if titles else "할일 없음"


#===============
# error: get_tasks_in_list 함수 누락 오류 해결
def get_tasks_in_list(list_id):
    service = build("tasks", "v1", credentials=_login())
    tasks_result = service.tasks().list(tasklist=list_id, showCompleted=False).execute()
    
    items = tasks_result.get("items", [])
    result_list = []
    for item in items:
        result_list.append({
            "id": item["id"],
            "title": item["title"]
        })
    return result_list
# ==============


def save_log(task_name, focus_score, is_distracted):
    # 집중도 측정 결과 => data/log_YYYY-MM-DD.json 에 저장
    os.makedirs("data", exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = f"data/log_{today}.json"  # 날마다 다른 파일
    logs = []

    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except:
            logs = []

    logs.append({
        "check_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "task_name": task_name,
        "score": focus_score,
        "distracted": is_distracted,
    })

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print("===과목 목록===")
    try:
        for lst in get_task_lists():
            print(f"{lst['title']}")
    except Exception as e:
        print(f"과목 목록 가져오기 실패: {e}")

    print("\n==== 전체 할 일 =========")
    try:
        print(get_all_task_titles())
    except Exception as e:
        print(f"할 일 목록 가져오기 실패: {e}")