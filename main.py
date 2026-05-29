import os
import sys
import json
import time
import threading

# 한글 오류용
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# # 구글 태스크 / startcheck: 에이전트 처음 실행 시
from apis.google_tasks import getsubjectlist, gettodolist
from checker import startcheck

# 전역 변수 설정
GOAL_FILE = "data/goal.json"
interval = 10 * 60  # 기본 주기 10분
running = True # 돌고 있는지
goal = "" # 목표
task_titles = "" #task의 title

# 마지막 시간 체크  ----- 알람이 계속 오는 것을 방지
last_check_time = time.time()


# 목표 파일 저장
def save_goal(g, t):
    with open(GOAL_FILE, "w", encoding="utf-8") as f:
        # JSON 저장
        json.dump({"subject": g, "todo": t}, f, ensure_ascii=False, indent=2)

# 목표 파일 load
def load_goal():
    if not os.path.exists(GOAL_FILE):
        return "", ""  # 파일 없으면 빈칸 리턴
    with open(GOAL_FILE, encoding="utf-8") as f:
        d = json.load(f)
    return d["subject"], d["todo"]


# 구글 task에서 목표를 선택
def pick_goal():
    print("\n Google task 목표 입력\n")
    lists = getsubjectlist() #apis - google task에서 가져옴

    # 과목 목록 출력 ---> 번호랑 함께 출력
    for i, lst in enumerate(lists):
        print(f"{i + 1}. {lst['title']}")
    choice = input("번호 입력 (엔터치면 건너뜀) ")

    # 잘못 입력 --> 빈 문자열 리턴
    if not choice.isdigit() or not (1 <= int(choice) <= len(lists)):
        return "", ""
    # 선택된 task
    pickedlist = lists[int(choice) - 1]
    pickedgoal = pickedlist["title"]
    print(f"과목 선택됨: {pickedgoal}")

    # 과목 안의 세부 할 일 목록 출력
    tasks = gettodolist(pickedlist["id"])
    if not tasks:
        return pickedgoal, ""
    for i, t in enumerate(tasks):
        print(f"{i + 1}. {t['title']}")
    choice = input("세부할일 번호 입력 (엔터 건너뜀) ")

    pickedtask = tasks[int(choice) - 1]["title"]
    print(f"할 일 선택됨: {pickedtask}")
    return pickedgoal, pickedtask


# 현재 에이전트 상태 화면 출력
def print_status():
    goal_str = f"{goal} {task_titles}" if goal else "미지정"

    elapsed = time.time() - last_check_time
    rem_seconds = max(0, interval - elapsed)
    rem_min = int(rem_seconds // 60)
    rem_sec = int(rem_seconds % 60)

    print()
    print(" [에이전트 상태]")
    print(f"다음 측정까지 남은 시간: {rem_min}분 {rem_sec}초")
    print()
    print("엔터: 지금 측정 | g: 목표 변경 | t: 주기 변경 | q: 프로그램 종료")


# 백그라운드에서 돌아가는 타이머 스레드
def timer_thread():
    global last_check_time
    while running:
        time.sleep(2)  # 2초마다 검사

        # 설정한 주기가 지났는지 체크
        if time.time() - last_check_time >= interval:
            last_check_time = time.time()
            res = startcheck(goal, task_titles)
            if res and "messages" in res:
                print(res["messages"][-1].content)
            print_status()

# 메인 실행부
def main():
    global running, goal, task_titles, interval, last_check_time

    print("=" * 50)
    print("AI 집중력 관리 에이전트 (성시준)")
    print("=" * 50)

    # 기존 저장된 목표 불러오기
    savedgoal, savedtask = load_goal()
    if savedgoal:
        print(f"최근 저장된 목표: [{savedgoal}] {savedtask or '(없음)'}")
        change = input("목표를 바꾸시겠습니까? (y 입력시 변경 / 엔터 치면 유지) ")
        if change == "y":
            goal, task_titles = pick_goal()
        else:
            goal, task_titles = savedgoal, savedtask
    else:
        goal, task_titles = pick_goal()

    # 불러온거 다시 저장해서 동기화
    save_goal(goal, task_titles)

    # 타이머 시작
    last_check_time = time.time()
    # 스레드 구동 ----->  타이머가 계속 돌아가게 해서 주기마다 agent를 작동시킴
    threading.Thread(target=timer_thread, daemon=True).start()

    print_status()

    # 입력값 처리 루프
    while running:
        cmd = input()
        if cmd == "q":
            print("프로그램을 종료합니다.")
            running = False
            break

        elif cmd == "g":
            newgoal, newtask = pick_goal()
            if newgoal:
                goal, task_titles = newgoal, newtask
                save_goal(goal, task_titles)
            print_status()

        elif cmd == "t":
            new_interval = int(input(f"새 주기 입력: "))
            interval = new_interval * 60
            print(f"측정 주기 {new_interval}분으로 변경")
            print_status()

        elif cmd == "":
            res = startcheck(goal, task_titles)
            if res and "messages" in res:
                print(res["messages"][-1].content)
            last_check_time = time.time()  # 타이머 리셋
            print_status()
        else:
            print("잘못된 명령")
            print_status()

if __name__ == "__main__":
    main()