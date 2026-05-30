import cv2
import json
import time
from ultralytics import YOLO


def start_camera():
    model = YOLO("yolo11n-pose.pt") #pretrained yolo 모델 로드
    cam = cv2.VideoCapture(0) # 웹캠사용 입력 받음

    print("자세 감시 시작")

    while True:
        time.sleep(5.0)  # 5초 주기 ----------> CPU 과부화 때문에 간격을 늘림

        ret, frame = cam.read() # frame 데이터 캡처

        # 모델 실행 - 로그 출력 X
        results = model(frame, verbose=False)

        msg = "자리 비움"
        slouched = False # 나쁜 자세 flag

        # 사람 들어왔는지 체크
        if len(results[0].boxes) > 0 and results[0].keypoints is not None:

            # 화면에 잡힌 포인트들 을 파이썬 리스트로 가져옴
            points = results[0].keypoints.xy[0].tolist()

            # 최소 포인트 갯수가 있어야 함--------> index에서 오류 방지
            if len(points) >= 7:
                nose = points[0] #코
                left_shoulder = points[5] # 어깨 왼쪽
                right_shoulder = points[6] # 어깨 오른쪽

                # 왼쪽 어깨와 오른쪽의 차이를 구하기
                width = abs(left_shoulder[0] - right_shoulder[0])
                # y 좌표의 평균 구하기
                shoulder_y_avg = (left_shoulder[1] + right_shoulder[1]) / 2
                # 코와 어깨의 y 차이 구하기
                height = shoulder_y_avg - nose[1]

                # 비율 계산
                ratio = height / width

                # 비율로 좋은 자세인지 아닌지 판정
                if ratio < 0.28:
                    slouched = True #나쁜 자세 flag = True
                    msg = f"비율:{ratio:.2f} (나쁜 자세)"
                else:
                    slouched = False # 좋은 자세 flag = False
                    msg = f"비율: {ratio:.2f} (좋은 자세)"
            else:
                msg = "신체 포인트 부족"
        else:
            msg = "사람 미감지"

        # 프린트
        print(f"[Pose] {msg}")

        #  JSON 저장
        status_data = {
            "slouched": slouched, # 나쁜 자세 flag
            "msg": msg # 판독 설명
        }
        # JSON으로 파일을 사용해서 AI 에이전트가 지금의 자세를 계산할 수 있도록 함
        with open("data/posture_status.json", "w", encoding="utf-8") as f:
            # JSON 포맷으로 dump
            json.dump(status_data, f, ensure_ascii=False, indent=2)

    cam.release() # 카메라 release

if __name__ == "__main__":
    start_camera()