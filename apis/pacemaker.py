import sys
import time
import tkinter as tk
from tkinter import messagebox
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

load_dotenv("auth/.env", override=True)

# 딴짓이 캡처되었을 때 원인을 진단 및 복귀 유도하는 팝업 함수
def restpopup(goal, reason):
    # 타임라인 데이터 가져오기 - 20분
    from apis.activitywatch import getrecentapphistory
    apps = getrecentapphistory(20)
    timelinelines = []
    # 상위 10개의 list를 통해서 타임라인 분석
    for i in apps[:10]:
        timelinelines.append(f" {i['minutes']}분 사용 | {i['app']} | {i['title']}")
    timelinetext = "\n".join(timelinelines)
# 하나의 긴 타임라인 문자열로 파싱

    #  Gemini에 이탈 심리 분석 요청
    prompt = f"""너는 인지심리학 전문 AI야. 주어진 정보를 바탕으로 학생이 집중을 잃은 트리거 / 경로를 분석해줘. 4줄 내외로 간결하게 작성해줘.
[원래 목표]: {goal}
[이탈 원인]: {reason}
[타임라인]:  {timelinetext}"""

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.5)
    analysis_result = llm.invoke([HumanMessage(content=prompt)]).content

    # Tkinter 윈도우 숨기기 -> 다른 앱들 위에 최상위에 경고창을 올림 / 최상위로 올라가게
    root = tk.Tk()
    root.withdraw()  # 메인 윈도우 창을 띄우지 않음
    root.attributes("-topmost", True)

    # 분석 결과
    messagebox.showwarning("역분석 보고서", f"원래 목표: {goal}\n{analysis_result}")

    # 예/아니오 복귀  알림창 전송
    isfocus = messagebox.askyesno("집중 복귀", "원래 목표로 복귀하시겠습니까?\n(아니오이면 5분간 휴식 모드로 진입)")
    # 아니요를 누른 경우
    if not isfocus:
        messagebox.showinfo("5분 휴식", "5분 동안 쉬고 오세요")
        time.sleep(300)  # 5분 동안 실행 차단

    root.destroy()