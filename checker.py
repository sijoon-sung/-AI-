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


import os
import sys
import base64
import time
import cv2
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

from apis.activitywatch import getactiveapp, getrecentapphistory # 앱활동 로드
from apis.google_tasks   import savetojson # 측정 결과 JSON 저장
from apis.pacemaker import restpopup # UI 팝업

# # LangGraph 에이전트 상태
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    # 노드를 거치면서 모든 대화 기록을 누적 기록 dict

# 도구 1: 화면 캡처 분석
@tool
def screencheck():
    """현재 모니터 화면을 캡처하고 분석합니다.""" # llm이 이해할 수 있는 docstring으로

    # 현재 모니터 캡쳐
    pyautogui.screenshot().save("data/temp.png")

    # 데이터만 base64로 읽어오고 이미지는 버림
    with open("data/temp.png", "rb") as f:
        imgdata = base64.b64encode(f.read()).decode("utf-8")
    os.remove("data/temp.png")

    chat = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    res = chat.invoke([HumanMessage(content=[
        {"type": "text", "text": "이 화면을 분석해줘:1. 뭘 하고 있는지 요약  2. 딴짓 여부 (예/아니오)3. 사유."},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{imgdata}"}}
    ])])
    # gemini한테 분석을 맡김 = text, image

    return res.content

# 도구 2: ActivityWatch 활동 조회
@tool
def applogread():
    """최근 10분 동안의 사용자 앱 사용 로그를 조회합니다."""
    # 최근 10분동안의 활동 로그
    now_app = getactiveapp() #지금 사용하고 있는 앱
    apphistory = getrecentapphistory(10)#최근 10분간의 내역

    lines = [f"지금: {now_app['app']} | {now_app['title']}"]
    # 최근 10분간의 내역도 list에 넣기
    for item in apphistory[:10]:
        lines.append(f" [앱] {item['app']} | {item['title']} | {item['minutes']}분")
    # 문자열로 합쳐서 반환
    return "\n".join(lines)

# 도구 3: 알림창 띄우기
@tool
def showwarning(msg: str):
    """집중력 저하 경고 또는 자세 불량 알림을 사용자에게 보냅니다."""
    # 딴짓을 한다고 생각하면 경고
    notification.notify(title="===집중도 코치===", message=msg, timeout=6)
    return "경고 전송"

# 도구 4: 결과 저장 / 트리거 분석
@tool
def saveresultdata(is_distracted: bool, score: int, reason: str, task: str):
    """사용자의 집중도 분석 결과를 저장하고 관련 팝업을 실행합니다."""
    # 분석결과를 저장
    if savetojson:
        savetojson(task, score, is_distracted)
    # UI 띄우기 - restpopup / 메인 로직에 영향을 주지 않기 위해서 thread로 실행
    import threading
    if is_distracted: # 딴짓이 맞는 경우에
        threading.Thread(
            target=restpopup,
            args=(task, reason), # task / 이탈 이유를 인자로
            daemon=True # 메인 프로그램이 종료되면 팝업창 스레드도 같이 종료
        ).start()

    return f"저장 완료: {task} | {score}점" # 결과를 에이전트에 반환

@tool
def get_pose():
    """사용자의 실시간 신체 자세 상태 정보를 가져옵니다."""
    # 파일에 저장된 사용자 자세 정보를 읽음
    import json
    try:
        with open("data/posture_status.json", "r", encoding="utf-8") as f:
            d = json.load(f) #저장된 파일을 dict로 읽음
        return d.get("msg", "상태 조회 실패") #자세관련 메세지 반환
    except:
        return "데이터 없음" # 데이터 없음 LLM에 반환

tools = [screencheck, applogread, get_pose, showwarning, saveresultdata]

# 에이전트 실행 노드
def runagent(state):
    #  적절한 도구 실행 / 피드백을 주도록
    chat = ChatGoogleGenerativeAI(model="gemini-2.5-flash").bind_tools(tools)
    # 반드시 가이드를 주기 ------>
    sysmsg = SystemMessage(content="""너는 집중 코치야. 순서대로 도구를 실행해줘:
1. screencheck, applogread, get_pose 순으로 사용자 상태를 확인한다.
2. 결과 분석:
   - 자리 비움: 경고 없이 집중도 데이터 저장(saveresultdata) 후 종료
   - 딴짓 중 + 나쁜 자세: 경고(showwarning), 자세경고 후 저장
   - 공부 중 + 나쁜 자세: 자세 경고(showwarning) 후 저장 
   - 공부 중 + 바른 자세: 경고 없이 저장 
3. 분석 완료 후 반드시 saveresultdata를 호출, 짧은 피드백 1줄을 남긴다.""")

    messages = [sysmsg] + state["messages"] # system message + 이전의 대화 내용
    res = chat.invoke(messages) # 실행
    return {"messages": [res]} # 메세지 결과를 graph 상태 리스트에 추가

# 조건부 분기
def loopcheck(state):
    last = state["messages"][-1]
    if last.tool_calls: # 실행을 요구하는 tool 목록이 있으면
        return "tools" # tool 노드로 이동
    return END #더는 호출할 도구가 없으면 그래프 끝냄

# 실행 함수
def startcheck(goal, task_titles):
    #집중도 측정을 한 번 실행하는 메인 에이전트 함수

    graph = StateGraph(AgentState)
    graph.add_node("agent", runagent) # agent 노드
    graph.add_node("tools", ToolNode(tools)) # tool노드

    graph.add_edge(START, "agent") # start
    # 조건부 분기 > agent의 결과에 따라서 tool로 갈지 END할지
    graph.add_conditional_edges("agent", loopcheck, {"tools": "tools", END: END})
    # tool -> agent 노드로 돌아가서 다음 판단
    graph.add_edge("tools", "agent")
    app = graph.compile()

    startmsg = HumanMessage(content=f"분석 시작해줘 | 목표: {goal}  | 할 일: {task_titles}")

    #입력 메세지 넣고 결과를 반환
    result = app.invoke({"messages": [startmsg]})
    return result

if __name__ == "__main__":
    from apis.google_tasks import getalltodotitles
    startcheck("클라우드 AI 프로그래밍", getalltodotitles())