# ActivityWatch 로컬 서버(http://localhost:5600)에서 앱 사용 정보를 가져옴

import urllib.request
import json
from datetime import datetime, timedelta

AW_URL = "http://localhost:5600/api/0"

# windows에서 현재 앱 가져오기
def getactiveapp():

    try:
        with urllib.request.urlopen(AW_URL + "/buckets/", timeout=3) as r:
            buckets = json.loads(r.read())  # buckets에 읽어오기
    # 반드시 예외 상황을 만들어야 함 -----> 없으면 문제
    except:
        return {"app": "알 수 없음", "title": "알 수 없음", "source": "unknown"}

    # window 버킷 ID 찾기
    windowid = None
    for b in buckets: ## 전체 버킷 키들을 돌며 검사합니다.
        if b.startswith("aw-watcher-window_"):  # 윈도우 탐지 버킷 이름
            windowid = b # 발견한 키 이름

    # app / title/url/source 초기화
    app = "알 수 없음"
    title = "알 수 없음"
    url = ""
    source = "unknown"

    # 찾은 버킷이 존재할 때
    if windowid != None:
        try: #세부 속성 알아내기
            with urllib.request.urlopen(AW_URL + f"/buckets/{windowid}/events?limit=1", timeout=3) as r:
                events = json.loads(r.read())
                # 이벤트 JSON을 배열로 받음
            # 이벤트가 안비어 있으면
            if events:
                app = events[0]["data"]["app"]
                title = events[0]["data"]["title"]
                source = "window"
                # 세부 정보 뽑기
        except:
            pass

    return {"app": app, "title": title, "source": source}
# 확정된 3개의 결과 키를 딕셔너리를 반환함

def getrecentapphistory(minutes=10):
    # 기본 minutes분 동안의 앱 및 창 사용 내역을 반환
    # 반환값 = [{"app": 앱이름, "title": 창제목, "minutes": 분}, ...]

    # 버킷 목록 가져오기 -------> dict로 로드
    with urllib.request.urlopen(AW_URL + "/buckets/", timeout=3) as r:
        buckets = json.loads(r.read())
    # 버킷 이름
    windowid = None
    for b in buckets:
        if b.startswith("aw-watcher-window_"):
            windowid = b # 버킷이름을 찾음
            break
    if not windowid: #없는 경우
        return []

    # 현재 시각에서 minutes만큼 뺀 시각 -> ISO 포맷 (버킷의 포맷과 같이)
    now = datetime.now()
    start = now - timedelta(minutes=minutes)
    start_iso = start.strftime("%Y-%m-%dT%H:%M:%SZ")

    results = {}  # (app, title) key로 -> secs 합산용 딕셔너리

    url = f"{AW_URL}/buckets/{windowid}/events?start={start_iso}"
    # 기준 시각 이후의 데이터만 수집
    with urllib.request.urlopen(url, timeout=3) as r:
        events = json.loads(r.read())

    # 이벤트 별로 제목/사용시간 집계
    for event in events:

        app = event["data"]["app"] #app
        title = event["data"]["title"] #창이름
        secs = float(event["duration"]) # 쓴 시간
        key = (app, title)  # app / title을 키로해서 합산
        
        # 합계로직 - 빈도수 검사랑 똑같이
        results[key] = results.get(key, 0.0) + secs

    # 결과 정리 -> 10초 미만은 자체적으로 정리
    output = []
    for (app, title), secs in results.items(): # 튜플 언패킹을 사용해서
        if secs < 10:
            continue
            # 반올림 해서 append
        output.append({
            "app": app,
            "title": title,
            "minutes": round(secs / 60, 1)
        })

    # 내림차순으로 만들기 - minutes 가 기준
    output.sort(key=lambda x: x["minutes"], reverse=True)
    return output
 # 가장 오래 사용한 앱 앞에