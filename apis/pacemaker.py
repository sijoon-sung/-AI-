import time
import tkinter as tk
from tkinter import messagebox
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

load_dotenv("auth/.env", override=True)

def trigger_intervention(goal, reason):
    # 1. 타임라인 데이터 가져오기
    from apis.activitywatch import get_recent_apps
    timeline = [{"time": f"{i['minutes']}분 사용", "app": i["app"], "title": i["title"]} for i in get_recent_apps(20)[:10]]
    timeline_text = "\n".join([f"- {item['time']} | {item['app']} | {item['title'][:50]}" for item in timeline])

    # 2. Gemini에 이탈 심리 분석 요청
    prompt = f"""너는 인지심리학 전문 코치야. 정보를 바탕으로 학생이 집중을 잃은 '트리거' / '경로'를 객관적인 어조로 분석해줘. 4줄 내외로 간결하게 작성해줘. md가 아닌 일반텍스트 형식으로 작성해줘.
[원래 목표]: {goal}
[이탈 원인]: {reason}
[타임라인]:\n{timeline_text}"""

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.5)
    analysis_result = llm.invoke([HumanMessage(content=prompt)]).content

    # 3. Tkinter 윈도우 숨기기 -> 최상위로 올라가게
    root = tk.Tk()
    root.withdraw()  # 메인 윈도우 창을 띄우지 않음
    root.attributes("-topmost", True)

    # 안내 및 분석 결과 노출 (확인용)
    messagebox.showwarning("역분석 보고서", f"[원래 목표]: {goal}\n\n{analysis_result}")

    # 다시 집중할지 말지 대화상자 (다시 집중 = Yes / 5분 휴식 = No)
    is_focus = messagebox.askyesno("집중 복귀", "지금 바로 원래 목표로 복귀하시겠습니까?\n\n('아니오'를 누르시면 5분간 휴식 모드로 진입.)")

    if not is_focus:
        messagebox.showinfo("5분 휴식", "5분 동안 떨어져서 쉬고 오세요")
        time.sleep(300)  # 5분 동안 스크립트 실행 차단

    root.destroy()

if __name__ == "__main__":
    trigger_intervention("파이썬 프로그래밍 및 데모 완성", "유튜브 접속 감지됨")