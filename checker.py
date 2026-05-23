"""
checker.py - LangGraph + Gemini 집중도 측정

그래프:
    START -> agent -> 도구호출이 있으면? -> tools -> agent -> ...
                                없으면 -> END
"""

"""
LangGraph 워크플로우
START ---> [agent] ------> 조건분 분기 ----> 도구 호출 있음 -----> [tools]
              |                                                   |
              도구 호출 X                                       다시[agent]
              |
              END
              
start -> agent: 사용자가 입력한 현재 목표와 할일 목록을 가지고 분석을 시작
agent-> conditional_edges: Gemini가 판단하여 check_screen 등의 도구가 필요하다고 판단하면 tools 노드로 진입
tools -> agent: 도구 수행 결과( 화면 내용, 사용 시간 등)


Node의 함수
agent_run: 4가지 tool을 바인딩해서 실행
1.화면 캡처 분석  2. 활동 로그 확인 3. 종합 판단 후 필요시 윈도우 알림 4. 결과 저장

check_loop(state): 그래프의 흐름을 제어하는 분기점
tool_calls이 있으면 tools 노드 반환 없으면 END

check_now(goal, task_titles): 10분마다 주기적으로 호출 할 수 있게 에이전트 실행하는 진입 node

"""

"""
check_screen: 모니터 화면을 스크린 샷을 한 뒤에 GEMINI에게 전송해서 시각적으로 분석
-------------------> pyautogui, Base64 

get_app_log: 최근 10분간 활성화된 창과 웹 주소를 가져와서 텍스트로 요약
-------------> apis.activitywatch

warn_user: 땃짓으로 감지되었을 경우에는 하단에 알림을 띄움( 알림을 9분 가격으로 띄울 수 있게 해줌)
---------------> plyer.notification

save_data: 분석 점수와 딴짓 여부를 로컬 파일에 기록
is_distracted = True일 경우 백그라운드 세레드를 생성해서 Tkinter 창을 비동기로 실행함
-------------> apis.google_tasks, apis.pacemaker
"""

import os
import sys
import base64
import time
from datetime import datetime
from typing import Annotated, TypedDict

#  UTF-8 설정
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import pyautogui
from plyer import notification
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

load_dotenv("auth/.env", override=True)

from apis.activitywatch import get_current_app, get_recent_apps
from apis.google_tasks   import save_log
from apis.pacemaker import trigger_intervention

# 알림 쿨타임용 변수
last_alert_time = 0

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# 도구 1: 화면 캡처 분석
@tool
def check_screen():
    """현재 모니터 화면을 캡처해서 공부중인지 딴짓하는지 분석함"""
    pyautogui.screenshot().save("data/temp.png")

    with open("data/temp.png", "rb") as f:
        img_data = base64.b64encode(f.read()).decode("utf-8")
    os.remove("data/temp.png")

    chat = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    res = chat.invoke([HumanMessage(content=[
        {"type": "text", "text": "이 화면을 분석해줘:\n1. 뭘 하고 있는지 요약\n2. 딴짓 여부 (예/아니오)\n3. 이유\n."},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_data}"}}
    ])])

    return res.content

# 도구 2: ActivityWatch 활동 조회
@tool
def get_app_log():
    """최근 10분 동안 사용한 프로그램과 웹페이지 목록을 가져옴"""
    now_app = get_current_app()
    app_history = get_recent_apps(10)

    lines = [f"현재: {now_app['app']} | {now_app['title']}"]
    for item in app_history[:10]:
        tag = "[웹]" if item["source"] == "web" else "[앱]"
        lines.append(f" {tag} {item['app']} | {item['title']} | {item['minutes']}분")

    return "\n".join(lines)

# 도구 3: 알림창 띄우기
@tool
def warn_user(msg: str):
    """사용자가 딴짓할 때 윈도우 알림으로 경고를 보냄"""
    global last_alert_time
    if time.time() - last_alert_time < 540: # 9분 쿨타임
        return "최근에 경고를 이미 보냈음"
    
    notification.notify(title="===집중도 코치===", message=msg, timeout=6)
    last_alert_time = time.time()
    return "경고 전송 완료"

# 도구 4: 결과 저장 및 개입 UI 트리거
@tool
def save_data(is_distracted: bool, score: int, reason: str, task: str):
    """분석 결과를 저장하고 딴짓인 경우 경고 UI를 띄움"""
    if save_log:
        save_log(task, score, is_distracted)

    import threading
    if is_distracted:
        threading.Thread(
            target=trigger_intervention,
            args=(task, reason),
            daemon=True
        ).start()

    return f"저장 완료: {task} - {score}점"

tools = [check_screen, get_app_log, warn_user, save_data]

# 에이전트 실행 노드
def agent_run(state):
    """Gemini가 상태를 보고 적절한 도구를 실행하거나 피드백을 주도록 함"""
    chat = ChatGoogleGenerativeAI(model="gemini-2.5-flash").bind_tools(tools)
    sys_msg = SystemMessage(content="""너는 집중도 분석 AI야
순서:
1. check_screen() 호출 -> 화면 분석
2. get_app_log() 호출 -> 앱 사용 내역 확인
3. 종합 판단:
   - 딴짓이면 -> warn_user() 호출
   - 집중 중이면 -> 그냥 넘어가기
4. save_data() 반드시 마지막에 호출
5. 도구 호출 다 끝나면 -> 다음 턴에 학생에게 짧은 피드백 1~2문장만 작성
   (피드백 쓰는 턴에 도구 호출 하지 마)""")

    messages = [sys_msg] + state["messages"]
    res = chat.invoke(messages)
    return {"messages": [res]}

# 조건부 분기 (도구 실행 여부 판단)
def check_loop(state):
    last = state["messages"][-1]
    if last.tool_calls:
        return "tools"
    return END

# 실행 함수
def check_now(goal, task_titles):
    """집중도 측정을 한 번 실행하는 메인 에이전트 함수"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ----> 집중도 측정 시작")

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_run)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", check_loop, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    app = graph.compile()

    start_msg = HumanMessage(content=f"분석 시작해줘.\n목표: {goal or '미지정'}\n할 일: {task_titles or '없음'}")

    result = app.invoke({"messages": [start_msg]})
    return result

if __name__ == "__main__":
    from apis.google_tasks import get_all_task_titles
    check_now("클라우드 AI 프로그래밍", get_all_task_titles())