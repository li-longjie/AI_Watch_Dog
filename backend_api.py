import os
import requests
import speech_recognition as sr
import edge_tts
import asyncio
import pygame
import time
import uuid # 用于生成唯一文件名

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS # 导入 CORS 扩展
from pydub import AudioSegment
import langid

# --- 配置huggingFace国内镜像 (如果需要) ---
# os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

# 大模型 API 的配置
API_URL = "https://api.siliconflow.cn/v1/chat/completions"
API_KEY = "sk-YOUR-API-KEY"  # <-- 请替换为您的实际 API 密钥
MODEL_NAME = "Qwen/Qwen2-7B-Instruct"  # 模型名称配置

# 配置音频输出目录
# 请确保这个目录是可写的，并且可以通过HTTP访问（如果返回文件路径）
# 或者您也可以选择直接返回音频数据
OUTPUT_AUDIO_DIR = os.path.abspath("./output_audio")
os.makedirs(OUTPUT_AUDIO_DIR, exist_ok=True)

app = Flask(__name__)
CORS(app) # 在 Flask 应用上应用 CORS

# 初始化语音识别器
recognizer = sr.Recognizer()

# 初始化 pygame mixer (用于播放后端生成的音频，可选，主要用于测试)
try:
    pygame.mixer.init()
except pygame.error as e:
    print(f"Pygame mixer initialization failed: {e}. Audio playback in backend might not work.")

# --- LLM API 调用函数 ---
def call_llm_api(prompt):
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
        response.raise_for_status() # 检查HTTP错误
        result = response.json()
        return result['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        print(f"API 调用出错: {e}")
        return None

# --- Edge TTS 调用函数 ---
async def generate_tts_audio(text, output_file):
    try:
        # 语种识别
        language, confidence = langid.classify(text)
        
        language_speaker = {
            "ja" : "ja-JP-NanamiNeural",
            "fr" : "fr-FR-DeniseNeural",
            "es" : "ca-ES-JoanaNeural",
            "de" : "de-DE-KatjaNeural",
            "zh" : "zh-CN-XiaoyiNeural",
            "en" : "en-US-AnaNeural",
        }

        used_speaker = language_speaker.get(language, "zh-CN-XiaoyiNeural")
        print(f"检测到语种：{language} 使用音色：{used_speaker}")
        
        communicate = edge_tts.Communicate(text, used_speaker)
        await communicate.save(output_file)
        return True
    except Exception as e:
        print(f"TTS 生成失败: {e}")
        return False

# --- 音频处理、ASR、LLM、TTS 整合函数 ---
def process_voice_command(audio_file_path):
    user_text = None
    ai_response_text = None
    ai_audio_url = None # 或者文件路径
    
    try:
        # 1. ASR 语音识别
        print(f"正在进行 ASR 处理: {audio_file_path}")
        with sr.AudioFile(audio_file_path) as source:
            audio_data = recognizer.record(source)
            try:
                user_text = recognizer.recognize_google(audio_data, language='zh-CN')
                print("ASR OUT:", user_text)
            except sr.UnknownValueError:
                print("ASR 无法识别音频内容")
                user_text = "[未能识别语音]"
            except sr.RequestError as e:
                print(f"ASR 请求失败; {e}")
                user_text = f"[ASR 错误: {e}]"
        
        # 如果成功识别到用户语音，则调用 LLM
        if user_text and not user_text.startswith("["):
            # 2. 调用 LLM 获取回复
            print("正在调用 LLM...")
            prompt = user_text + "，回答可以详细，50字以内！" # 可以在此处调整prompt
            ai_response_text = call_llm_api(prompt)
            if ai_response_text:
                print("LLM Answer:", ai_response_text)
                
                # 3. TTS 生成语音回复
                print("正在进行 TTS...")
                unique_filename = f"reply_{uuid.uuid4()}.mp3"
                output_audio_path = os.path.join(OUTPUT_AUDIO_DIR, unique_filename)
                
                # Edge TTS 是异步的，需要在同步函数中运行
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(generate_tts_audio(ai_response_text, output_audio_path))
                loop.close()
                
                if success:
                    # 返回可访问的音频文件路径或 URL
                    # 假设 OUTPUT_AUDIO_DIR 可以通过 /audio 路由访问
                    ai_audio_url = f"/audio/{unique_filename}"
                    print(f"TTS Audio saved to: {output_audio_path}")
                    # 可选：在后端播放生成的音频进行测试
                    # if os.path.exists(output_audio_path) and pygame.mixer.get_init():
                    #     try:
                    #         pygame.mixer.music.load(output_audio_path)
                    #         pygame.mixer.music.play()
                    #         # 注意：在请求处理中阻塞播放不好，这里仅为演示播放，实际API不应等待播放结束
                    #         # while pygame.mixer.music.get_busy():
                    #         #     time.sleep(0.1)
                    #     except Exception as e:
                    #         print(f"后端播放音频失败: {e}")
                else:
                    ai_response_text += " [语音生成失败]"
                    
        elif not user_text.startswith("["):
             ai_response_text = "未能获取有效的LLM回复。"
        
    except Exception as e:
        print(f"后端处理语音时出错: {e}")
        import traceback
        print("错误堆栈:", traceback.format_exc())
        user_text = user_text if user_text else "[处理错误]"
        ai_response_text = ai_response_text if ai_response_text else f"[后端错误: {e}]"

    # 返回结果给前端
    return {
        "userText": user_text,
        "aiResponse": ai_response_text,
        "audioUrl": ai_audio_url
    }

# --- Flask 路由 ---
@app.route('/api/voice/process', methods=['POST'])
def process_voice():
    print("收到 /api/voice/process 请求")
    # 检查是否有文件在请求中
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file part in the request"}), 400
    
    audio_file = request.files['audio']
    
    # 如果用户没有选择文件，浏览器也会提交一个空文件部分
    if audio_file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if audio_file:
        # 创建一个临时文件来保存上传的音频
        temp_audio_path = f"./temp_audio_{uuid.uuid4()}.wav"
        
        try:
            # 原始音频可能是 webm 或其他格式，需要转换为 WAV 格式供 speech_recognition 使用
            # 使用 pydub 进行转换
            audio = AudioSegment.from_file(audio_file)
            audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
            audio.export(temp_audio_path, format="wav")
            print(f"音频已保存并转换为 WAV 格式: {temp_audio_path}")
            
            # 调用处理函数
            results = process_voice_command(temp_audio_path)
            
            # 返回 JSON 结果
            return jsonify(results)
            
        except Exception as e:
            print(f"处理上传文件时出错: {e}")
            return jsonify({"error": f"Error processing audio file: {e}"}), 500
        finally:
            # 清理临时文件
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
                print(f"临时文件已清理: {temp_audio_path}")

# --- 静态文件路由，用于访问生成的音频文件 ---
@app.route('/audio/<filename>')
def serve_audio(filename):
    try:
        return send_file(os.path.join(OUTPUT_AUDIO_DIR, filename))
    except FileNotFoundError:
        return "File not found", 404

# --- 运行 Flask 应用 ---
if __name__ == '__main__':
    # 在开发模式下运行，host='0.0.0.0' 允许外部访问
    # debug=True 会提供更详细的错误信息
    print(f"后端服务正在运行，监听端口 5000. 音频输出目录: {OUTPUT_AUDIO_DIR}")
    print(f"请确保您的 API 密钥已替换: {API_KEY}")
    app.run(host='0.0.0.0', port=5000, debug=True) 