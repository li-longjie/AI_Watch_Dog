from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import io
import wave
import numpy as np
import speech_recognition as sr
import edge_tts
import asyncio
import requests
import datetime
import soundfile as sf # 确保安装了 soundfile
# from pydub import AudioSegment # 引入 pydub (不再使用 pydub)
import subprocess # 引入 subprocess 模块

# --- 设置 FFmpeg 和 FFprobe 的路径 (解决 pydub 找不到 ffmpeg 的问题) ---
# !!! IMPORTANT: 请将以下路径替换为您的 ffmpeg 安装目录中 'bin' 文件夹的实际路径 !!!
# 例如： "C:/ffmpeg/ffmpeg-7.0.2-full_build-www.gyan.dev/bin"
FFMPEG_BIN_DIR = "D:/software/ffmpeg/ffmpeg-7.0.2-full_build/bin" # <<<<<<< 在这里替换为您的实际路径

FFMPEG_EXE_PATH = os.path.join(FFMPEG_BIN_DIR, "ffmpeg.exe")
FFPROBE_EXE_PATH = os.path.join(FFMPEG_BIN_DIR, "ffprobe.exe")

# 可以选择不再设置环境变量，因为我们将直接指定路径给 subprocess
# os.environ["FFMPEG_PATH"] = FFMPEG_EXE_PATH
# os.environ["FFPROBE_PATH"] = FFPROBE_EXE_PATH

# --- Flask 应用配置 ---
app = Flask(__name__)
CORS(app) # 允许所有来源的跨域请求，在生产环境中应限制

# --- 配置huggingFace国内镜像 ---
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

# 大模型 API 的配置
API_URL = "https://api.siliconflow.cn/v1/chat/completions"
API_KEY = "sk-szjxvsopbfddnsxpiumkgkmcusqhpflilhbszpwwozlwzxzb" # 请替换为您的实际API密钥
MODEL_NAME = "Qwen/Qwen2-7B-Instruct"  # 模型名称配置

# 输出目录配置
OUTPUT_DIR = os.path.abspath("./ASR-LLM-TTS-master/output")
TTS_OUTPUT_DIR = os.path.abspath("./ASR-LLM-TTS-master/Test_QWen2_VL")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)

# 初始化语音识别器
recognizer = sr.Recognizer()

# --- 辅助函数：调用大模型 API ---
def call_qwen_api(prompt):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": MODEL_NAME,
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

# --- 辅助函数：文本转语音 (TTS) ---
async def tts_generate_audio(text, output_file):
    # 这里我们只支持中文音色，如果需要多语言，需要更复杂的逻辑
    # 参考之前 13_SenceVoice_QWen2.5_edgeTTS_realTime.py 中的 langid 和 language_speaker 逻辑
    used_speaker = "zh-CN-XiaoyiNeural" 
    communicate = edge_tts.Communicate(text, used_speaker)
    await communicate.save(output_file)

# --- API 路由：处理语音输入 ---
@app.route('/api/voice/process', methods=['POST'])
def process_voice():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files['audio']
    audio_data = audio_file.read() # 读取二进制音频数据

    # --- 保存接收到的音频（可选，用于调试）---
    temp_audio_path = os.path.join(OUTPUT_DIR, f"received_audio_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.webm")
    with open(temp_audio_path, 'wb') as f:
        f.write(audio_data)
    print(f"接收到音频并保存至: {temp_audio_path}")

    try:
        temp_wav_path = os.path.join(OUTPUT_DIR, f"converted_audio_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")

        # 使用 subprocess 直接调用 ffmpeg 进行转换
        command = [
            FFMPEG_EXE_PATH,
            '-i', temp_audio_path,  # 输入文件
            '-acodec', 'pcm_s16le', # 音频编码为 16-bit signed little-endian PCM
            '-ar', '16000',         # 采样率 16000 Hz
            '-ac', '1',             # 单声道
            temp_wav_path           # 输出文件
        ]
        
        print(f"执行 ffmpeg 命令: {' '.join(command)}")
        
        # 执行 ffmpeg 命令，并设置工作目录
        result = subprocess.run(command, capture_output=True, text=True, check=False, cwd=FFMPEG_BIN_DIR)
        
        if result.returncode != 0:
            print(f"FFmpeg 转换失败！错误输出: {result.stderr}")
            raise Exception(f"FFmpeg 转换失败: {result.stderr}")
            
        print(f"音频已从 webm 转换为 wav 并保存至: {temp_wav_path}")

        # 使用 speech_recognition 从转换后的 wav 文件中读取音频
        with sr.AudioFile(temp_wav_path) as source:
            audio_source = recognizer.record(source)
        
        user_text = recognizer.recognize_google(audio_source, language='zh-CN')
        print("ASR OUT:", user_text)

        # 调用大模型
        prompt = user_text + "，汉语要返回简体文字，回答可以详细，50字以内！"
        ai_response = call_qwen_api(prompt)
        print("Answer:", ai_response)

        if not ai_response:
            return jsonify({"userText": user_text, "aiResponse": "大模型未能提供有效回答。"}), 200
        
        # 生成 AI 语音响应
        tts_filename = f"ai_response_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        tts_output_path = os.path.join(TTS_OUTPUT_DIR, tts_filename)
        
        asyncio.run(tts_generate_audio(ai_response, tts_output_path))
        print(f"AI 语音已生成至: {tts_output_path}")

        # 返回响应数据
        audio_url = f"/audio/{tts_filename}"

        return jsonify({
            "userText": user_text,
            "aiResponse": ai_response,
            "audioUrl": audio_url
        })

    except sr.UnknownValueError:
        print("未能识别语音内容")
        return jsonify({"userText": None, "aiResponse": "未能识别语音内容。"}), 200
    except sr.RequestError as e:
        print(f"无法从Google Speech Recognition服务获取结果; {e}")
        return jsonify({"userText": None, "aiResponse": f"语音识别服务出错: {e}"}), 500
    except Exception as e:
        print(f"处理语音时出错: {e}")
        return jsonify({"error": f"服务器内部错误: {e}"}), 500
    finally:
        # 清理临时文件
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
        if 'temp_wav_path' in locals() and os.path.exists(temp_wav_path):
            os.remove(temp_wav_path)

# --- API 路由：提供生成的语音文件 ---
@app.route('/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(TTS_OUTPUT_DIR, filename)

# --- API 路由：处理文本输入 ---
@app.route('/api/chat/text', methods=['POST'])
def process_text():
    data = request.get_json()
    query = data.get('query')

    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        ai_response = call_qwen_api(query)
        if ai_response:
            return jsonify({"status": "success", "answer": ai_response})
        else:
            return jsonify({"status": "error", "message": "大模型未能提供有效回答。"}), 500
    except Exception as e:
        print(f"处理文本消息时出错: {e}")
        return jsonify({"status": "error", "message": f"服务器内部错误: {e}"}), 500

# --- 运行 Flask 应用 ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 