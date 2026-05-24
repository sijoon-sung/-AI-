import os
import sys
import tkinter as tk
from tkinter import scrolledtext, messagebox
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

# 인코딩 설정 ------> 한글이 깨지는 문제
sys.stdout.reconfigure(encoding="utf-8")

# 환경 변수
load_dotenv("auth/.env", override=True)

# 타임라인 데이터 수집 (연동이 안되면 데이터 반환)
def get_timeline():
    try:
        from apis.activitywatch import getrecentapphistory
        apps = getrecentapphistory(30)
        
        result_list = []
        for item in apps[:10]:
            tempdict = {
                "time": f"{item['minutes']}분 사용",
                "app": item["app"],
                "title": item["title"]
            }
            result_list.append(tempdict)
        return result_list
    except:
        return [
            {"time": "10분 전", "app": "VS Code", "title": "daily_report.py - 코딩 작업 중"},
            {"time": "5분 전", "app": "Chrome", "title": "구글 검색 - python 인코딩 font 한글 깨짐 해결"},
            {"time": "4분 전", "app": "Chrome", "title": "블로그 - pycharm에서 인코딩 문제 해결 방법"},
            {"time": "2분 전", "app": "Chrome", "title": "블로그 - AI 컨퍼런스 관련 뉴스(구글 AI 컴퍼런스)"},
            {"time": "1분 전", "app": "Chrome", "title": "유튜브 - 구글 I/O 연설 검색 및 영상 시청"},
            {"time": "방금 전", "app": "Chrome", "title": "유튜브 - 'IT 테크 유튜버의 리뷰 영상 시청'"}
        ]

# gemini에게 이탈 로그를 보고 역추척을 시킴
def analyze_mind(goal, timeline):
    timelinetext = "\n".join([f"- {item['time']} | {item['app']} | {item['title']}" for item in timeline])
    
    prompt = f"""너는 인지심리학 전문 선생님이야. 타임라인을 참고해서 학생이 어떤 '트리거'와 '경로'로 집중을 잃었는지 객관적/과학적인 어조로 분석해줘. 4~6줄 내외로 간결하게 작성해줘. md말고 그냥 텍스트로 출력해줘

[원래 목표]: {goal}
[타임라인]:\n{timelinetext}"""

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.5)
    return llm.invoke([HumanMessage(content=prompt)]).content

# 결과창 UI 띄우기
def show_ui_window(goal, analysisresult):
    root = tk.Tk()
    root.title("메타인지 역분석")
    root.geometry("500x400")
    root.wm_attributes("-topmost", 1)

    tk.Label(root, text="나의 집중력 이탈 역분석 보고서", font=("맑은 고딕", 12, "bold")).pack(pady=10)
    
    txtarea = scrolledtext.ScrolledText(root, width=55, height=12, font=("맑은 고딕", 10), wrap=tk.WORD)
    txtarea.pack(pady=10)
    txtarea.insert(tk.END, f"원래 목표: {goal}\n\n{analysisresult}")
    txtarea.configure(state='disabled')

    btnframe = tk.Frame(root)
    btnframe.pack(pady=10)
    
    def on_rest():
        messagebox.showinfo("휴식", "컴퓨터에서 떨어져 눈을 붙이세요!")
        root.destroy()

    tk.Button(btnframe, text="다시 집중하기", command=root.destroy, width=12).pack(side=tk.LEFT, padx=5)
    tk.Button(btnframe, text="5분 휴식하기", command=on_rest, width=12).pack(side=tk.LEFT, padx=5)

    root.mainloop()

if __name__ == "__main__":
    goal = "파이썬으로 Matplotlib 집중도 차트 그리기 및 이메일 연동 완료하기"
    print("타임라인 분석 중...")
    show_ui_window(goal, analyze_mind(goal, get_timeline()))