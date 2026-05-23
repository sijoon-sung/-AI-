import os
import sys
import json
import time
import threading


# 스레드를 사용해서 타이머를 연산하는 스크립트를 계속 돌림


# 계속 해서 한글이 깨지는 문제 발생 -> 인코딩에 문제가 되는 듯

# Windows cp949 인코딩 에러 방지용 -------UTF-8 설정
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


# error: get_tasks_in_list import 누락 해결
from apis.google_tasks import get_task_lists, get_all_task_titles, get_tasks_in_list

from checker import check_now

# 기본적인 설정 값
GOAL_FILE = "data/goal.json"
interval = 10 * 60 # 10분 간격
running = True
goal = ""
task_titles =""


# 현재 시간을 기록
last_check_time = time.time()


# 목표 저장 하고 불러오기
def save_goal(g, t):
    with open(GOAL_FILE, "w", encoding="utf-8") as f:
        json.dump({"subject": g, "todo": t}, f, ensure_ascii=False, indent=2)
        # 저장하기 - "goal", "task" 가 키임


def load_goal():
    if not os.path.exists(GOAL_FILE):
        return "", "" # 없으면 빈칸 리턴하기
    with open(GOAL_FILE, encoding="utf-8") as f:
        d = json.load(f) # 로드해서 반환하기 goal/task를
    return d["subject"], d["todo"]

# Google tasks에 목표 메뉴를 고름
def pick_goal():
    # 터미널에서 과목 -> 할일 선택 해서 반환
    print("\n Google task 목표 입력\n")
    lists = get_task_lists()
    if not lists:
        print("구글 Task에 goal을 넣으세요")
        return "", ""

    for i, lst in enumerate(lists):
        print(f"{i+1},{lst['title']}")
    choice = input("번호 입력 / enter = 건너뀌기")
    # 리스트 안에 드는 지도 확인해야 함


#===============
# error: 입력 유효성 검증 오류 해결 (유효하지 않을 때 return 하도록 수정)
    if not choice.isdigit() or not (1 <= int(choice) <= len(lists)):
        return "", ""

    picked_list = lists[int(choice)-1] #index -1
    """
    picked_list는 이런 형태
    {
    "id": "리스트ID",
    "title": "리스트 이름"
    }
    """

    picked_goal = picked_list["title"]
    print(f"과목: {picked_goal}")

    # 과목 안에 세부적인 task 뽑기
    tasks = get_tasks_in_list(picked_list["id"])
    if not tasks:
        return picked_goal ,""
    for i, t in enumerate(tasks):
        print(f"{i+1},{t['title']}")
    choice = input("세부task: 번호 입력 / enter = 건너뜀")

#===============
# error: 입력 유효성 오류 ---------> 둘 다 필요함
    if not choice.isdigit() or not (1 <= int(choice) <= len(tasks)):
        return picked_goal, "" # 이거 picked goal은 반환을 해줘야 함 - 주의

    picked_task = tasks[int(choice) - 1]["title"]
    # 세부 테스크를 고름
    print(f"할 일: {picked_task}")
    return picked_goal, picked_task

def print_status():
    goal_str = f"{goal} {task_titles}" if goal else "미지정"

    elapsed = time.time() - last_check_time
    percent = min(elapsed / interval, 1.0) * 100
    rem_seconds = max(0, interval - elapsed)
    rem_min = int(rem_seconds // 60)
    rem_sec = int(rem_seconds % 60)

    print()
    print(" 에이전트 상태")
    print(f"목표: {goal_str}")
    print(f"주기: {interval // 60}분")
    print(f"진행: {percent:.1f}% (남은 시간: {rem_min}분 {rem_sec}초)")
    print()

    print("Enter: 측정 | g: 목표 | t: 주기 | q: 종료")

def timer_thread():
    # 언제 마지막으로 체크 했는지
    global last_check_time
    last_printed_minute = 0
    while running:
        time.sleep(1)
        elapsed = time.time() - last_check_time
        current_minute = int(elapsed // 60)

        # 매 분마다 진행률 출력
        if current_minute > last_printed_minute and elapsed < interval:
            last_printed_minute = current_minute
            percent = min(elapsed / interval, 1.0) * 100
            rem = max(0, interval - elapsed)
            print(f" 진행도: {percent}% 완료, 남은 시간 {int(rem//60)}분 {int(rem%60)}초")

        # 주기에 도달하면 자동으로 측정 실행
        if elapsed >= interval:
            last_check_time = time.time()
            last_printed_minute = 0
            print(" ======== 자동 측정 시작 ========")
            res = check_now(goal, task_titles)
            if res and "messages" in res:
                print(f" AI 피드백: {res['messages'][-1].content}")
            print_status()



# main
def main():
    global running, goal, task_titles, interval

    print("="*50)
    print("AI 집중력 관리 에이전트 (성시준)")
    print("="*50)


# error: 프로그램 진입점 추가
    # 이전 목표 불러오기
    saved_goal, saved_task = load_goal()
    if saved_goal:
        print(f"saved goal: [{saved_goal}] {saved_task or '(없음)'}")
        change = input("목표를 바꿀까요? |y=예 / 엔터=유지|: ")
        if change == "y":
            goal, task_titles = pick_goal()
        else:
            goal, task_titles = saved_goal, saved_task
    else:
        goal, task_titles = pick_goal()

    save_goal(goal, task_titles)

# error: 타이머 시작 시간 리셋 및 타이머 구동
    global last_check_time
    last_check_time = time.time()
    # 백그라운드 타이머 스레드 시작
    threading.Thread(target=timer_thread, daemon=True).start()


    print_status()

    # 입력 처리 루프
    while running:
        cmd = input()
        if cmd == "q":
            print("exit")
            running = False
            break

        elif cmd == "g":
            new_goal, new_task = pick_goal()
            if new_goal:
                goal, task_titles = new_goal, new_task
                save_goal(goal, task_titles)

            print_status()
        elif cmd == "t":
            new_interval = input(f"새 주기 입력(현재 {interval//60}분): ")
            if new_interval.isdigit() and int(new_interval) > 0:
                interval = int(new_interval) * 60
                print(f"측정 주기 = {new_interval}분으로 변경")

            else:
                print("올바른 숫자가 아닙니다")
            print_status()
        elif cmd == "":
            print("측정을 시작합니다...")

            res = check_now(goal, task_titles)


            if res and "messages" in res:
                last_msg = res["messages"][-1]
                print("=" * 60)
                print(" AI의 피드백")
                print("-" * 60)
                print(last_msg.content)
                print("=" * 60)


            last_check_time = time.time() # last_check time 업데이트
            print_status()
        else:
            print("알 수 없는 명령입니다.")
            print_status()


if __name__ == "__main__":
    main()
# ==============


