import cv2

def test_camera(camera_index):
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"无法打开摄像头 {camera_index}")
        return
        
    print(f"摄像头 {camera_index} 打开成功")
    print(f"分辨率: {cap.get(cv2.CAP_PROP_FRAME_WIDTH)}x{cap.get(cv2.CAP_PROP_FRAME_HEIGHT)}")
    print(f"帧率: {cap.get(cv2.CAP_PROP_FPS)}")
    
    ret, frame = cap.read()
    if ret:
        print("成功读取一帧")
    else:
        print("读取帧失败")
    
    cap.release()

# 测试所有可能的摄像头
for i in range(10):
    print(f"\n测试摄像头 {i}")
    test_camera(i) 