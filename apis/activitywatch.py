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
        return {"app": "알 수 없음", "title": "알 수 없음", "url": "", "source": "unknown"}

    # window 버킷 ID 찾기
    windowid = None
    for b in buckets:
        if b.startswith("aw-watcher-window_"):  # 윈도우 탐지 버킷 이름
            windowid = b

    # app / title/url/source
    app = "알 수 없음"
    title = "알 수 없음"
    url = ""
    source = "unknown"

    # windows에서 현재 앱 가져오기
    if windowid != None:
        try:
            with urllib.request.urlopen(AW_URL + f"/buckets/{windowid}/events?limit=1", timeout=3) as r:
                events = json.loads(r.read())
            if events:
                app = events[0]["data"]["app"]
                title = events[0]["data"]["title"]
                source = "window"
        except:
            pass

    return {"app": app, "title": title, "url": url, "source": source}


def get_events(bucket_id, start_iso):
    url = f"{AW_URL}/buckets/{bucket_id}/events?start={start_iso}"
    with urllib.request.urlopen(url, timeout=3) as r:
        return json.loads(r.read())


def getrecentapphistory(minutes=10):
    # 기본 minutes분 동안의 앱 및 창 사용 내역을 반환
    # 반환값 = [{"app": 앱이름, "title": 창제목, "minutes": 분}, ...]

    # 버킷 목록 가져오기
    with urllib.request.urlopen(AW_URL + "/buckets/", timeout=3) as r:
        buckets = json.loads(r.read())

    windowid = None
    for b in buckets:
        if b.startswith("aw-watcher-window_"):
            windowid = b

    # 최근 minutes분 동안의 활동 기록 수집 -> results 정리
    now = datetime.utcnow()
    start = now - timedelta(minutes=minutes)
    start_iso = start.strftime("%Y-%m-%dT%H:%M:%SZ")

    results = {}  # (app, title) -> secs 합산용 딕셔너리

    if windowid != None:
        # window의 값이 있을 때만
        for event in get_events(windowid, start_iso):
            app = event["data"]["app"]
            title = event["data"]["title"]
            secs = float(event["duration"])
            
            key = (app, title)
            
            # 집계로직
            results[key] = results.get(key, 0.0) + secs

    # 결과 정리 -> 10초 미만은 자체적으로 정리
    output = []
    for (app, title), secs in results.items():
        if secs < 10:
            continue
        output.append({
            "app": app,
            "title": title,
            "minutes": round(secs / 60, 1)
        })

    # 내림차순으로 만들어서 노이즈 제거
    output.sort(key=lambda x: x["minutes"], reverse=True)
    return output


def gettodayapphistory():
    # daily_report용 호출함수
    return getrecentapphistory(minutes=60 * 24)
