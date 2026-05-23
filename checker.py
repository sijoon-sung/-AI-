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
agent-> conditional_edges: Gemini가 판단하여 capture_and_analyz 등의 도구가 필요하다고 판단하면 tools 노드로 진입
tools -> agent: 도구 수행 결과( 화면 내용, 사용 시간 등)


Node의 함수
agent_node: 4가지 tool을 바인딩해서 실행
1.화면 캡처 분석  2. 활동 로그 확인 3. 종합 판단 후 필요시 윈도우 알림 4. 결과 저장

should_continue(state): 그래프의 흐름을 제어하는 분기점
tool_calls이 있으면 tools 노드 반환 없으면 END

run_check(goal, task_titles): 10분마다 주기적으로 호출 할 수 있게 에이전트 실행하는 진입 node

"""

"""
capture_and_analyze: 모니터 화면을 스크린 샷을 한 뒤에 GEMINI에게 전송해서 시각적으로 분석
-------------------> pyautogui, Base64 

get_activity: 최근 10분간 활성화된 창과 웹 주소를 가져와서 텍스트로 요약
-------------> apis.activitywatch

send_alert: 땃짓으로 감지되었을 경우에는 하단에 알림을 띄움( 알림을 9분 가격으로 띄울 수 있게 해줌)
---------------> plyer.notification

save_result: 분석 점수와 땃짓 여부를 로컬 파일에 기록
is_distracted = True일 경우 백그라운드 세레드를 생성해서 Tkinter 창을 비동기로 실행함
-------------> apis.google_tasks, apis.pacemaker
"""
import os
import sys
import base64
import time
from datetime import datetime
from typing import Annotated, TypedDict   # LangGraph 필수

# Windows cp949 인코딩 에러 방지용 UTF-8 설정 -------> 한글 깨짐 방지용
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
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

# 알림이 계속 오지 않도록 하기 위한 클록 - 전역으로 사용
_last_alert_time = 0

#===============
# error: LangGraph ToolNode State 키 복수형 변경 (message -> messages)
class State(TypedDict):
    messages: Annotated[list, add_messages]
# ==============

# 도구 1번
@tool
def capture_and_analyze():
    """화면을 캡쳐 후에 Gemini vision으로 뭘하고 있는지 평가하게 함"""
    os.makedirs("data", exist_ok=True) # 있으면 넘어가게 코드 수정
    pyautogui.screenshot().save("data/temp.png")
    # 스크린 샷을 만들고 -> PIL 객체로 변환
    # .save로 .png 포맷으로 저장

    # temp.json이 아니라 temp.png를 읽어야 에러가 안 남
    with open("data/temp.png", "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    os.remove("data/temp.png") # 분석을 하고 지우기

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

    # type: text
    # type: image_url을 base 64 인코딩된 데이터 URI 형태로 전달
    response = llm.invoke([HumanMessage(content=[
        {"type": "text", "text": "이 화면을 분석해줘:\n1. 뭘 하고 있는지 요약\n2. 딴짓 여부 (예/아니오)\n3. 이유\n."},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
    ])])

    return response.content

# 도구2ㅣ activity watch 앱 내역
@tool
def get_activity():
    """AW에서 지금 쓰는 앱 / 10분 의 내역을 가져옴"""
    current = get_current_app()
    recent = get_recent_apps(10)

    # 파이썬 비트연산자 | 에러를 올바른 문자열 포맷 형식으로 수정
    lines = [f"현재: {current['app']} | {current['title']}"]

    for item in recent[:10]:
        src = "[웹]" if item["source"] == "web" else "[앱]"
        lines.append(f" {src} {item['app']} | {item['title']} | {item['minutes']}분")

    return "\n".join(lines)

# 도구3: window 알림: plyer 모듈 사용
@tool
def send_alert(message: str):
    """사용자에게 집중하라는 윈도우 알림을 전송"""
    global _last_alert_time
    if time.time() - _last_alert_time < 540: #최소한 9분 간격
        return "최근에 이미 알림 전송함"
    notification.notify(title="===집중도 코치===", message=message, timeout=6)
    _last_alert_time = time.time() # 업데이트
    return "알람 전송"

# 도구 4번 로그 저장
@tool
def save_result(is_distracted: bool, focus_score: int, reason: str, task_name: str):
    """분석이 끝나면 마지막에 save_result로 결과를 저장"""

    # 출력 형식
    """
    - is_distracted : True / False
    - focus_score   : 0~100
    - reason        : 판단 이유 한 줄
    - task_name     : 현재 작업명
    """
    if save_log:
        save_log(task_name, focus_score, is_distracted)

    # 딴짓이 감지되었다면 -> 사용자를 잡아 줄 수 있도록 함
    # -> pace maker의 GUI 호출 -> threading 으로 처리 (비동기로 별도로 처리할 수 있는 로직 개발)
    import threading
    if is_distracted:
        threading.Thread(
            target=trigger_intervention,
            args=(task_name, reason),
            daemon=True
        ).start()

    return f"저장 완료 || {task_name} : {focus_score}점"

# 사용할 도구 리스트 구성
TOOLS = [capture_and_analyze, get_activity, send_alert, save_result]

# 에이전트 노드
def agent_node(state):
    """GEMINI 가 메시지를 보고 도구를 호출하거나 피드백을 작성할 수 있게함"""
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash").bind_tools(TOOLS)
    system = SystemMessage(content="""너는 집중도 분석 AI야
순서:
1. capture_and_analyze() 호출 -> 화면 분석
2. get_activity() 호출 -> 앱 사용 내역 확인
3. 종합 판단:
   - 딴짓이면 -> send_alert() 호출
   - 집중 중이면 -> 그냥 넘어가기
4. save_result() 반드시 마지막에 호출
5. 도구 호출 다 끝나면 -> 다음 턴에 학생에게 짧은 피드백 1~2문장만 작성
   (피드백 쓰는 턴에 도구 호출 하지 마)""")


# error: State 키 복수형 변경 (message -> messages)
    messages = [system] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}

# 도구 호출이 있으면 tools로, 없으면 END로
# 도구 호출 메커니즘 -> agent가 필요한 도구를 요청
def should_continue(state):

# error: State 키 복수형 ( messages)
    last = state["messages"][-1] #마지막 메세지 확인

    # getattr -> 반드시 사용해서 오류 없애기 아무것도 반환하지 않는 것 방지
    if getattr(last, "tool_calls", None):
        return "tools"
    return END

# main -> LangGraph를 사용한 agent를 node로 연결
def run_check(goal, task_titles):
    """집중도 측정 실행 => main에서 10분마다 호출"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ----> 집중도 측정 시작")

    # 그래프 연결 (중복 제거 및 구조 연결 수정)
    graph = StateGraph(State) # 에이전트의 실행 단계를 연결하는 경로를 제공
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    app = graph.compile()

    first_message = HumanMessage(content=f"분석 시작해줘.\n목표: {goal or '미지정'}\n할 일: {task_titles or '없음'}")

    result = app.invoke({"messages": [first_message]})
    return result

if __name__ == "__main__":
    from apis.google_tasks import get_all_task_titles
    run_check("클라우드 AI 프로그래밍", get_all_task_titles())