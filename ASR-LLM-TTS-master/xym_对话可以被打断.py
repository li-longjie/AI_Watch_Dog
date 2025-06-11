import cv2
import pyaudio
import wave
import threading
import numpy as np
import time
from queue import Queue
import webrtcvad
import os
import threading
import requests
import whisper
import pygame
import edge_tts
import asyncio
from time import sleep
import langid
from langdetect import detect
import soundfile as sf

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
audio_file_count = 0

# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(folder_path, exist_ok=True)

# 队列用于音频和视频同步缓存
audio_queue = Queue()
video_queue = Queue()

# 全局变量
last_active_time = time.time()
recording_active = True
segments_to_save = []
saved_intervals = []
last_vad_end_time = 0  # 上次保存的 VAD 有效段结束时间

# 初始化 WebRTC VAD
vad = webrtcvad.Vad()
vad.set_mode(VAD_MODE)

# 音频录制线程
def audio_recorder():
    global audio_queue, recording_active, last_active_time, segments_to_save, last_vad_end_time
    
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=AUDIO_CHANNELS,
                    rate=AUDIO_RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
    
    audio_buffer = []
    print("音频录制已开始")
    
    while recording_active:
        data = stream.read(CHUNK)
        audio_buffer.append(data)
        
        # 每 0.5 秒检测一次 VAD
        if len(audio_buffer) * CHUNK / AUDIO_RATE >= 0.5:
            # 拼接音频数据并检测 VAD
            raw_audio = b''.join(audio_buffer)
            vad_result = check_vad_activity(raw_audio)
            
            if vad_result:
                print("检测到语音活动")
                last_active_time = time.time()
                segments_to_save.append((raw_audio, time.time()))
            else:
                print("静音中...")
            
            audio_buffer = []  # 清空缓冲区
        
        # 检查无效语音时间
        if time.time() - last_active_time > NO_SPEECH_THRESHOLD:
            # 检查是否需要保存
            if segments_to_save and segments_to_save[-1][1] > last_vad_end_time:
                save_audio_video()
                last_active_time = time.time()
            else:
                pass
                # print("无新增语音段，跳过保存")
    
    stream.stop_stream()
    stream.close()
    p.terminate()

# 视频录制线程
def video_recorder():
    global video_queue, recording_active
    
    cap = cv2.VideoCapture(0)  # 使用默认摄像头
    print("视频录制已开始")
    
    while recording_active:
        ret, frame = cap.read()
        if ret:
            video_queue.put((frame, time.time()))
            
            # 实时显示摄像头画面
            cv2.imshow("Real Camera", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):  # 按 Q 键退出
                break
        else:
            print("无法获取摄像头画面")
    
    cap.release()
    cv2.destroyAllWindows()

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
    pygame.mixer.init()

    global segments_to_save, video_queue, last_vad_end_time, saved_intervals

    # 全局变量，用于保存音频文件名计数
    global audio_file_count
    audio_file_count += 1
    audio_output_path = os.path.join(OUTPUT_DIR, f"audio_{audio_file_count}.wav")
    print(f"准备保存音频到: {audio_output_path}")

    if not segments_to_save:
        print("没有音频段需要保存")
        return
    
    # 停止当前播放的音频
    if pygame.mixer.music.get_busy():
        pygame.mixer.music.stop()
        print("检测到新的有效音，已停止当前音频播放")
        
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
        pygame.mixer.init()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(1)  # 等待音频播放结束
        print("播放完成！")
    except Exception as e:
        print(f"播放失败: {e}")
    finally:
        pygame.mixer.quit()

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

def Inference(TEMP_AUDIO_FILE):
    try:
        # 检查音频文件是否存在
        if not os.path.exists(TEMP_AUDIO_FILE):
            print(f"错误：找不到音频文件: {TEMP_AUDIO_FILE}")
            return
            
        print(f"正在处理音频文件: {TEMP_AUDIO_FILE}")
        print(f"文件大小: {os.path.getsize(TEMP_AUDIO_FILE)} 字节")
        
        # 尝试打开文件检查是否可读
        try:
            with open(TEMP_AUDIO_FILE, 'rb') as f:
                print("文件可以正常打开和读取")
        except Exception as e:
            print(f"文件打开失败: {e}")
            return
            
        print("正在加载 Whisper 模型...")
        # 使用 Whisper 的 tiny 模型，体积更小，下载更快
        model = whisper.load_model("tiny", download_root=os.path.join(os.path.expanduser("~"), ".cache", "whisper"))
        print("模型加载完成，开始语音识别...")
        
        try:
            # 使用 soundfile 读取音频
            print("正在读取音频文件...")
            audio_data, sample_rate = sf.read(TEMP_AUDIO_FILE)
            print(f"音频文件信息：")
            print(f"- 采样率: {sample_rate}")
            print(f"- 音频数据形状: {audio_data.shape}")
            
            # 确保音频是单声道
            if len(audio_data.shape) > 1:
                print("转换为单声道...")
                audio_data = audio_data.mean(axis=1)
            
            # 转换为 float32 类型
            print("转换为float32格式...")
            audio_data = audio_data.astype(np.float32)
            
            # 确保采样率是16kHz
            if sample_rate != 16000:
                print(f"调整采样率从 {sample_rate}Hz 到 16000Hz...")
                from scipy import signal
                audio_data = signal.resample(audio_data, int(len(audio_data) * 16000 / sample_rate))
                sample_rate = 16000
            
            print("开始转录音频...")
            result = model.transcribe(audio_data)
            prompt = result["text"] + "，回答简短一些，保持50字以内！"
            print("ASR OUT:", prompt)
            
            # -------- 调用大模型 API ------
            output_text = call_qwen_api(prompt)
            if output_text:
                print("answer:", output_text)
                
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
        except Exception as e:
            print(f"音频处理失败: {e}")
            import traceback
            print("错误堆栈:", traceback.format_exc())
            return
            
    except Exception as e:
        print(f"处理过程出错: {e}")
        print("详细错误信息:", str(e))
        import traceback
        print("错误堆栈:", traceback.format_exc())
        if "checksum" in str(e).lower():
            print("模型下载可能不完整，请检查网络连接后重试")

# 主函数
if __name__ == "__main__":
    try:
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
