# ActivityWatch 로컬 서버(http://localhost:5600)에서 앱 사용 정보를 가져옴
"""
get_current_app(): 현재 띄우고 있는 앱 정보를 1개 가져옴
                 : 브라우저를 쓰고 있으면 윈도우 대신 web에서 정보를 받아올 수 있게 함

{
    app: "앱 이름",
    title: "창이름/웹페이지 제목"
    url: "웹사이트 주소(window= 빈문자)"
    source: "데이터 출처" (window / web / unknown)
}


get_recent_apps(minutes=10): 지정장 시간 (기본 10분 동안) 의 기록을 합산해서 보여줌
특징: 동일한 웹/앱 제목은 합산해서 반환해줌
총 사용량이 10초 미만은 노이즈로 간주해서 제거
사용량이 긴 순서대로 정렬 해서 반환해줌

[
    {
        "app": "앱 이름 (앱 =  실제 이름 web = '브라우저')"
        "title": "창 제목"
        "url": "웹사이트 주소 (일반 앱 = 빈 문자열 )"
        "minutes": 10,
        "source": "(window 또는 web)"
    },
    {
        "app": "obsidian",
        "title": "obsidian:운영체제",
        "url": "",
        "minutes": 9,
        "source": "window"
    }
    #  사용량이 많은 순서대로
]

get_
"""

import urllib.request
import json
from datetime import datetime, timedelta

AW_URL = "http://localhost:5600/api/0"

# lower로 바꾸기 -> 대소문자가 바뀌어서 감지가 안되는 경우가 있었음
BROWSERS = ["chrome", "google chrome", "msedge", "firefox", "whale", "opera", "brave"]


def get_current_app():
    """
    지금 사용중인 app의 정보를 반환
    브라우저는 web을 사용해서 좀 더 정확한 제목을 가져옴
    """

    try:
        with urllib.request.urlopen(AW_URL + "/buckets/", timeout=3) as r:
            buckets = json.loads(r.read())  # buckets에 읽어오기
    except:
        return {"app": "알 수 없음", "title": "알 수 없음", "url": "", "source": "unknown"}

    # window 버킷 ID, web 버킷 ID 구분해서 찾기
    window_id = None
    web_id = None
    for b in buckets:
        if b.startswith("aw-watcher-window_"):  # 윈도우 탐지 버킷 이름
            window_id = b
        if b.startswith("aw-watcher-web"):
            web_id = b

    # app / title/url/source
    app = "알 수 없음"
    title = "알 수 없음"
    url = ""
    source = "unknown"

    # windows에서 현재 앱 가져오기
    if window_id != None:
        try:
            with urllib.request.urlopen(AW_URL + f"/buckets/{window_id}/events?limit=1", timeout=3) as r:
                events = json.loads(r.read())
            if events:
                app = events[0]["data"].get("app", "알 수 없음")
                title = events[0]["data"].get("title", "알 수 없음")
                source = "window"
        except:
            pass

    # 브라우저라면 web 버킷에서 탭/제목/url 가져오기
    if app.lower() in BROWSERS and web_id:
        try:
            with urllib.request.urlopen(AW_URL + f"/buckets/{web_id}/events?limit=1", timeout=3) as r:
                events = json.loads(r.read())
            if events:
                title = events[0]["data"].get("title", title)
                url = events[0]["data"].get("url", "")
                source = "web"
        except:
            pass

    return {"app": app, "title": title, "url": url, "source": source}


def get_recent_apps(minutes=10):
    # 최근 N분 기본 10분간의 앱/웹 사용내역을 반환
    # 반환값 = [{ "app": ..., "title": ..., "url": ..., "minutes": ..., "source": ... }, ...]

    try:  # 버킷 목록 가져오기
        with urllib.request.urlopen(AW_URL + "/buckets/", timeout=3) as r:
            buckets = json.loads(r.read())
    except:
        return []

    window_id = None
    web_id = None

    for b in buckets:
        if b.startswith("aw-watcher-window_"):
            window_id = b
        if b.startswith("aw-watcher-web"):
            web_id = b

    # 최근 minutes분 동안의 활동 기록이나 로그 수집 -> results 정리
    now = datetime.now().astimezone()
    start = now - timedelta(minutes=minutes)
    # ISO format 사용
    timeperiod = f"{start.isoformat()}/{now.isoformat()}"

    results = {}  # (app, title)을 넣으면 -> {secs, source, url} 반환

    if window_id != None:
        # window의 값이 있을 때만
        body = json.dumps({
            "timeperiods": [timeperiod],  # 시작시간/현재시간 -> 배열 (데이터를 버킷에서 가져오기 위해서)
            "query": [
                f"events = query_bucket('{window_id}');",  # 해당 window id에 대한 이벤트 데이터를 가져옴
                "events = merge_events_by_keys(events, ['app', 'title']);",  # app, title 기준으로 이벤트를 결합해서 저장
                "RETURN = events;"  # 최종 결과를 반환
            ]
        }).encode()
        try:
            # HTTP POST 형태로 요청
            req = urllib.request.Request(
                AW_URL + "/query/",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
                events = data[0] if data else []

                for event in events:
                    app = event["data"].get("app", "알 수 없음")
                    title = event["data"].get("title", "알 수 없음")
                    secs = float(event.get("duration", event.get("data", {}).get("duration", 0)))
                    if app.lower() in BROWSERS and web_id:  # 브라우저는 좀 더 상세하게 정리 가능한 WEB 버킷 사용
                        continue
                    key = (app, title)

                    # 집계로직
                    if key not in results:
                        results[key] = {"secs": 0, "source": "window", "url": ""}
                    results[key]["secs"] += secs
        except:
            pass

    if web_id:
        body = json.dumps({
            "timeperiods": [timeperiod],
            "query": [
                f"events = query_bucket('{web_id}');",
                "events = merge_events_by_keys(events, ['title', 'url']);",
                "RETURN = events;"
            ]
        }).encode()
        # WEB은 APP 이름은 안중요함

        # 똑같이 HTTP로 요청 - body만 다르게 해서
        try:
            req = urllib.request.Request(
                AW_URL + "/query/",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
                events = data[0] if data else []
                for ev in events:
                    title = ev["data"].get("title", "알 수 없음")
                    url = ev["data"].get("url", "")
                    secs = float(ev.get("duration", ev.get("data", {}).get("duration", 0)))
                    if not url or len(url) < 8:
                        continue
                    key = ("브라우저", title)
                    if key not in results:
                        results[key] = {"secs": 0, "source": "web", "url": url}
                    results[key]["secs"] += secs
        except:
            pass

    # 결과 정리 -> 10초 미만은 자체적으로 정리
    output = []
    for (app, title), info in results.items():
        if info["secs"] < 10:
            continue
        output.append({
            "app": app,
            "title": title,
            "url": info["url"],
            "minutes": round(info["secs"] / 60, 1),
            "source": info["source"]
        })

    # 내림차순으로 만들어서 노이즈 제거
    output.sort(key=lambda x: x["minutes"], reverse=True)
    return output


def get_today_apps():
    # daily_report용 호출함수
    return get_recent_apps(minutes=60 * 24)


# 테스트
if __name__ == "__main__":
    print("=== 현재 앱 ===")
    c = get_current_app()
    print(f"앱: {c['app']} | 제목: {c['title']} | 출처: {c['source']}")

    print("\n=== 최근 10분 ===")
    for item in get_recent_apps(10):
        src = "[웹]" if item["source"] == "web" else "[앱]"
        print(f"{src} {item['app']} | {item['title']} | {item['minutes']}분")

    print("\n=== 오늘 하루 전체 사용 내역 (상위 20개) ===")
    today_apps = get_today_apps()

    # 데이터가 20개보다 적을 수 있으므로 안전하게 슬라이싱 처리
    top_20_apps = today_apps[:20]

    if not top_20_apps:
        print("오늘 기록된 앱 사용 내역 X")
    else:
        for idx, item in enumerate(top_20_apps, 1):
            src = "[웹]" if item["source"] == "web" else "[앱]"
            # (앱 이름 | title | minutes )정리
            print(f"{idx:02d}. {src} {item['app']} | {item['title']}... | {item['minutes']}분")