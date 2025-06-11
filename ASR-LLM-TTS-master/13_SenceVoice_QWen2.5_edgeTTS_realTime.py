import cv2
import sounddevice as sd
import wave
import threading
import numpy as np
import time
from queue import Queue
import webrtcvad
import os
import threading
import requests
import speech_recognition as sr
import edge_tts
import asyncio
from time import sleep
import langid
from langdetect import detect
import soundfile as sf
import json
import datetime

# --- 配置huggingFace国内镜像 ---
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

# 大模型 API 的配置
API_URL = "https://api.siliconflow.cn/v1/chat/completions"
API_KEY = "sk-szjxvsopbfddnsxpiumkgkmcusqhpflilhbszpwwozlwzxzb"
MODEL_NAME = "Qwen/Qwen2-7B-Instruct"  # 模型名称配置

# 参数设置
AUDIO_RATE = 16000        # 音频采样率
AUDIO_CHANNELS = 1        # 单声道
CHUNK = 1024              # 音频块大小
VAD_MODE = 3              # VAD 模式 (0-3, 数字越大越敏感)
OUTPUT_DIR = os.path.abspath("./output")   # 输出目录的绝对路径
NO_SPEECH_THRESHOLD = 1   # 无效语音阈值，单位：秒
folder_path = os.path.abspath("./Test_QWen2_VL/")  # 音频输出目录的绝对路径
# video_output_path = os.path.abspath("./video_output/")  # 视频输出目录的绝对路径
audio_file_count = 0
# video_file_count = 0

# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(folder_path, exist_ok=True)
# os.makedirs(video_output_path, exist_ok=True)

# 队列用于音频和视频同步缓存
audio_queue = Queue()
# video_queue = Queue()

# 全局变量
last_active_time = time.time()
recording_active = True
segments_to_save = []
saved_intervals = []
last_vad_end_time = 0  # 上次保存的 VAD 有效段结束时间
is_processing = False  # 添加标志来跟踪模型是否正在处理

# 对话历史列表 (本次运行的)
conversation_history = []

# 本次对话的文件名
current_conversation_filename = f"conversation_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

# 初始化 WebRTC VAD
vad = webrtcvad.Vad()
vad.set_mode(VAD_MODE)

# 初始化语音识别器
recognizer = sr.Recognizer()

def audio_callback(indata, frames, time, status):
    """音频回调函数"""
    if status:
        print(f"音频状态: {status}")
    if not is_processing:
        audio_queue.put(indata.copy())

# 音频录制线程
def audio_recorder():
    global audio_queue, recording_active, last_active_time, segments_to_save, last_vad_end_time, is_processing
    
    print("音频录制已开始")
    
    with sd.InputStream(samplerate=AUDIO_RATE,
                       channels=AUDIO_CHANNELS,
                       callback=audio_callback,
                       blocksize=CHUNK):
        while recording_active:
            if is_processing:
                time.sleep(0.1)
                continue
                
            if not audio_queue.empty():
                data = audio_queue.get()
                # 将 float32 转换为 int16
                audio_data = (data * 32767).astype(np.int16).tobytes()
                
                # 检测 VAD
                if check_vad_activity(audio_data):
                    print("检测到语音活动")
                    last_active_time = time.time()
                    segments_to_save.append((audio_data, time.time()))
                else:
                    print("静音中...")
                
                # 检查无效语音时间
                if time.time() - last_active_time > NO_SPEECH_THRESHOLD:
                    if segments_to_save and segments_to_save[-1][1] > last_vad_end_time:
                        save_audio_video()
                        last_active_time = time.time()

# 视频录制线程
# def video_recorder():
#     global video_queue, recording_active
#     
#     cap = cv2.VideoCapture(0)  # 使用默认摄像头
#     print("视频录制已开始")
#     
#     while recording_active:
#         ret, frame = cap.read()
#         if ret:
#             video_queue.put((frame, time.time()))
#             
#             # 实时显示摄像头画面
#             cv2.imshow("Real Camera", frame)
#             if cv2.waitKey(1) & 0xFF == ord('q'):  # 按 Q 键退出
#                 break
#         else:
#             print("无法获取摄像头画面")
#     
#     cap.release()
#     cv2.destroyAllWindows()

# 检测 VAD 活动
def check_vad_activity(audio_data):
    # 将音频数据分块检测
    num, rate = 0, 0.4
    step = int(AUDIO_RATE * 0.02)  # 20ms 块大小
    flag_rate = round(rate * len(audio_data) // step)

    for i in range(0, len(audio_data), step):
        chunk = audio_data[i:i + step]
        if len(chunk) == step:
            if vad.is_speech(chunk, sample_rate=AUDIO_RATE):
                num += 1

    if num > flag_rate:
        return True
    return False

# 保存音频和视频
def save_audio_video():
    global segments_to_save, last_vad_end_time, saved_intervals
    # global video_file_count

    # 全局变量，用于保存音频文件名计数
    global audio_file_count
    audio_file_count += 1
    # video_file_count += 1
    audio_output_path = os.path.join(OUTPUT_DIR, f"audio_{audio_file_count}.wav")
    # video_output_file = os.path.join(video_output_path, f"video_{video_file_count}.mp4")
    print(f"准备保存音频到: {audio_output_path}")
    # print(f"准备保存视频到: {video_output_file}")

    if not segments_to_save:
        print("没有音频段需要保存")
        return
    
    # 获取有效段的时间范围
    start_time = segments_to_save[0][1]
    end_time = segments_to_save[-1][1]
    
    # 检查是否与之前的片段重叠
    if saved_intervals and saved_intervals[-1][1] >= start_time:
        print("当前片段与之前片段重叠，跳过保存")
        segments_to_save.clear()
        return
    
    try:
        # 保存音频
        audio_frames = [seg[0] for seg in segments_to_save]
        
        wf = wave.open(audio_output_path, 'wb')
        wf.setnchannels(AUDIO_CHANNELS)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(AUDIO_RATE)
        wf.writeframes(b''.join(audio_frames))
        wf.close()
        print(f"音频已保存至 {audio_output_path}")
        
        # # 保存视频
        # video_frames = []
        # while not video_queue.empty():
        #     frame, timestamp = video_queue.get()
        #     if start_time <= timestamp <= end_time:
        #         video_frames.append(frame)
        
        # if video_frames:
        #     # 获取视频参数
        #     height, width = video_frames[0].shape[:2]
        #     fps = 30  # 设置帧率
            
        #     # 创建视频写入器
        #     fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        #     out = cv2.VideoWriter(video_output_file, fourcc, fps, (width, height))
            
        #     # 写入视频帧
        #     for frame in video_frames:
        #         out.write(frame)
            
        #     out.release()
        #     print(f"视频已保存至 {video_output_file}")
        
        # 检查文件是否成功保存
        if os.path.exists(audio_output_path):
            print(f"确认音频文件已创建: {audio_output_path}")
            # 使用线程执行推理
            inference_thread = threading.Thread(target=Inference, args=(audio_output_path,))
            inference_thread.start()
        else:
            print(f"错误：音频文件未能成功创建: {audio_output_path}")
            
    except Exception as e:
        print(f"保存音频时出错: {e}")
        return
        
    # 记录保存的区间
    saved_intervals.append((start_time, end_time))
    
    # 清空缓冲区
    segments_to_save.clear()

# --- 播放音频 -
def play_audio(file_path):
    try:
        # 使用 sounddevice 播放音频
        data, samplerate = sf.read(file_path)
        sd.play(data, samplerate)
        sd.wait()  # 等待音频播放完成
        print("播放完成！")
    except Exception as e:
        print(f"播放失败: {e}")

async def amain(TEXT, VOICE, OUTPUT_FILE) -> None:
    """Main function"""
    communicate = edge_tts.Communicate(TEXT, VOICE)
    await communicate.save(OUTPUT_FILE)

def call_qwen_api(prompt):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": MODEL_NAME,  # 使用配置的模型名称
        "messages": [
            {"role": "system", "content": "你叫千问，是一个18岁的女大学生，性格活泼开朗，说话俏皮"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 512,
        "top_p": 0.8,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        print(f"API 调用出错: {e}")
        return None

# 保存对话历史到文件并更新历史列表
def save_conversation_history():
    global conversation_history, current_conversation_filename
    
    # 保存当前对话历史
    output_file_path = os.path.join(OUTPUT_DIR, current_conversation_filename)
    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(conversation_history, f, ensure_ascii=False, indent=4)
        print(f"当前对话历史已写入 {output_file_path}")
    except Exception as file_write_e:
        print(f"写入当前对话历史文件时出错: {file_write_e}")
    
    # 更新历史文件列表
    update_history_list()

# 更新历史文件列表文件
def update_history_list():
    history_files = []
    for filename in os.listdir(OUTPUT_DIR):
        if filename.startswith('conversation_') and filename.endswith('.json'):
            history_files.append(filename)
    
    history_list_path = os.path.join(OUTPUT_DIR, 'history_list.json')
    try:
        with open(history_list_path, 'w', encoding='utf-8') as f:
            json.dump(history_files, f, ensure_ascii=False, indent=4)
        print(f"历史文件列表已更新到 {history_list_path}")
    except Exception as list_write_e:
        print(f"写入历史文件列表时出错: {list_write_e}")

def Inference(TEMP_AUDIO_FILE):
    global is_processing, conversation_history, current_conversation_filename
    try:
        is_processing = True  # 设置处理标志
        # 检查音频文件是否存在
        if not os.path.exists(TEMP_AUDIO_FILE):
            print(f"错误：找不到音频文件: {TEMP_AUDIO_FILE}")
            is_processing = False  # 重置处理标志
            return
            
        print(f"正在处理音频文件: {TEMP_AUDIO_FILE}")
        print(f"文件大小: {os.path.getsize(TEMP_AUDIO_FILE)} 字节")
        
        try:
            # 使用 speech_recognition 进行语音识别
            with sr.AudioFile(TEMP_AUDIO_FILE) as source:
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data, language='zh-CN')
                print("ASR OUT:", text)
                
                prompt = text + "，回答可以详细，50字以内！"
                
                # -------- 调用大模型 API ------
                output_text = call_qwen_api(prompt)
                if output_text:
                    print("answer:", output_text)
                    
                    # 创建当前对话条目
                    current_dialogue = {
                        "asr_out": text,
                        "answer": output_text
                    }
                    
                    # 将当前对话添加到历史记录
                    conversation_history.append(current_dialogue)
                    
                    # 保存对话历史到文件并更新历史列表
                    save_conversation_history()
                    
                    # 输入文本
                    text = output_text
                    # 语种识别 -- langid
                    language, confidence = langid.classify(text)
                    
                    language_speaker = {
                        "ja" : "ja-JP-NanamiNeural",            # ok
                        "fr" : "fr-FR-DeniseNeural",            # ok
                        "es" : "ca-ES-JoanaNeural",             # ok
                        "de" : "de-DE-KatjaNeural",             # ok
                        "zh" : "zh-CN-XiaoyiNeural",            # ok
                        "en" : "en-US-AnaNeural",               # ok
                    }

                    if language not in language_speaker.keys():
                        used_speaker = "zh-CN-XiaoyiNeural"
                    else:
                        used_speaker = language_speaker[language]
                        print("检测到语种：", language, "使用音色：", language_speaker[language])

                    global audio_file_count
                    output_audio_path = os.path.join(folder_path, f"sft_{audio_file_count}.mp3")
                    print(f"准备生成语音文件: {output_audio_path}")
                    asyncio.run(amain(text, used_speaker, output_audio_path))
                    print(f"语音文件生成完成，准备播放")
                    play_audio(output_audio_path)
                else:
                    print("大模型 API 调用失败")
                    
        except sr.UnknownValueError:
            print("无法识别音频内容")
        except sr.RequestError as e:
            print(f"无法从Google Speech Recognition服务获取结果; {e}")
        except Exception as e:
            print(f"音频处理失败: {e}")
            import traceback
            print("错误堆栈:", traceback.format_exc())
            
    except Exception as e:
        print(f"处理过程出错: {e}")
        print("详细错误信息:", str(e))
        import traceback
        print("错误堆栈:", traceback.format_exc())
    finally:
        is_processing = False  # 确保在任何情况下都重置处理标志

# 主函数
if __name__ == "__main__":
    try:
        # 启动时先更新一次历史文件列表，确保前端能拿到最新数据
        update_history_list()

        # 启动音视频录制线程
        audio_thread = threading.Thread(target=audio_recorder)
        # video_thread = threading.Thread(target=video_recorder)
        audio_thread.start()
        # video_thread.start()
        
        print("按 Ctrl+C 停止录制")
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("录制停止中...")
        recording_active = False
        audio_thread.join()
        # video_thread.join()
        print("录制已停止")
