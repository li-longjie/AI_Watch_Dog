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
import re # 添加正则表达式模块
import json # 添加json模块

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

# 监控系统配置
MONITORING_DATA_FILE = os.path.abspath("./monitoring_data.json")

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

# 提取时间范围信息
def extract_time_ranges(text):
    """
    从文本中提取时间范围信息，格式如"13:03:02-13:04:33"
    """
    # 匹配时间范围格式，如"13:03:02-13:04:33"或"13:03-13:04"
    range_matches = re.findall(r'(\d{1,2}:\d{1,2}(?::\d{1,2})?)\s*[-—–]\s*(\d{1,2}:\d{1,2}(?::\d{1,2})?)', text)
    
    time_ranges = []
    for start_time, end_time in range_matches:
        time_ranges.append((start_time, end_time))
    
    return time_ranges

# --- 新增：直接从监控系统获取数据 ---
def get_monitoring_data(activity_type=None, today_only=True):
    """
    直接从监控系统获取数据，而不是从RAG数据库
    
    参数:
    activity_type (str): 活动类型，如"玩手机"、"专注工作学习"等
    today_only (bool): 是否只返回今天的记录
    
    返回:
    list: 符合条件的监控记录列表
    """
    try:
        # 如果监控数据文件不存在，创建一个示例数据文件
        if not os.path.exists(MONITORING_DATA_FILE):
            # 创建示例数据
            today_str = datetime.datetime.now().strftime('%Y-%m-%d')
            example_data = {
                "records": [
                    {
                        "activity": "玩手机",
                        "start_time": "13:03:02",
                        "end_time": "13:04:33",
                        "duration": "1.5分钟",
                        "date": today_str
                    },
                    {
                        "activity": "玩手机",
                        "start_time": "12:58:07",
                        "end_time": None,
                        "duration": None,
                        "date": today_str
                    },
                    {
                        "activity": "专注工作学习",
                        "start_time": "11:14:26",
                        "end_time": "11:20:46",
                        "duration": "6.3分钟",
                        "date": today_str
                    },
                    {
                        "activity": "专注工作学习",
                        "start_time": "11:11:17",
                        "end_time": None,
                        "duration": None,
                        "date": today_str
                    }
                ]
            }
            
            # 保存示例数据到文件
            with open(MONITORING_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(example_data, f, ensure_ascii=False, indent=2)
            
            print(f"创建了示例监控数据文件: {MONITORING_DATA_FILE}")
        
        # 读取监控数据
        with open(MONITORING_DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 过滤数据
        filtered_records = []
        today_str = datetime.datetime.now().strftime('%Y-%m-%d')
        
        for record in data.get("records", []):
            # 过滤活动类型
            if activity_type and record.get("activity") != activity_type:
                continue
            
            # 过滤日期
            if today_only and record.get("date") != today_str:
                continue
            
            filtered_records.append(record)
        
        return filtered_records
        
    except Exception as e:
        print(f"获取监控数据时出错: {e}")
        import traceback
        traceback.print_exc()
        return []

# --- 新增：从RAG服务器查询监控记录 ---
def query_monitoring_records(query_text):
    """
    从RAG服务器查询监控记录，用于处理特定的查询模式
    """
    try:
        print(f"尝试识别监控记录查询: {query_text}")
        
        # 从查询中提取关键信息
        # 匹配模式："你好请告诉我..." 以及可能的误识别变体
        possible_prefixes = [
            "你好", "您好", "喂", "嗨"
        ]
        
        # 检查是否以任何可能的前缀开头
        matched_prefix = None
        for prefix in possible_prefixes:
            if query_text.startswith(prefix):
                matched_prefix = prefix
                print(f"匹配到前缀: {matched_prefix}")
                break
                
        if not matched_prefix:
            print("未匹配到有效前缀")
            return None
            
        # 检查是否包含"请告诉我"或其变体
        tell_phrases = ["请告诉我", "请告诉", "告诉我", "告诉"]
        matched_tell_phrase = None
        for phrase in tell_phrases:
            if phrase in query_text:
                matched_tell_phrase = phrase
                print(f"匹配到请求短语: {matched_tell_phrase}")
                break
                
        if not matched_tell_phrase:
            print("未匹配到有效请求短语")
            return None
            
        # 提取查询的实际内容
        prefix_end = query_text.find(matched_tell_phrase) + len(matched_tell_phrase)
        actual_query = query_text[prefix_end:].strip()
        print(f"提取的实际查询内容: {actual_query}")
        
        # 定义关键情况列表
        key_situations = {
            "睡觉": ["睡觉", "睡眠", "躺下", "休息"],
            "玩手机": ["玩手机", "使用手机", "看手机", "几点玩手机", "什么时候玩手机", "玩手机了"],
            "喝饮料": ["喝饮料", "喝", "饮料"],
            "喝水": ["喝水", "饮水"],
            "吃东西": ["吃", "进食", "零食"],
            "专注工作学习": ["专注", "工作", "学习", "看书"],
            "发现明火": ["明火", "火", "火灾"],
            "人员聚集": ["聚集", "聚会", "人群"],
            "打架斗殴": ["打架", "斗殴", "冲突"]
        }
        
        # 检查查询是否与关键情况相关
        situation_type = None
        for situation, keywords in key_situations.items():
            if any(keyword in actual_query for keyword in keywords):
                situation_type = situation
                print(f"匹配到情境类型: {situation_type}")
                break
                
        if not situation_type:
            print("未匹配到有效情境类型")
            return None
            
        # 直接从监控系统获取数据，而不是从RAG数据库
        records = get_monitoring_data(activity_type=situation_type, today_only=True)
        print(f"从监控系统获取到 {len(records)} 条记录")
        
        if not records:
            return f"根据今天的监控记录，我没有发现你{situation_type}的情况。"
        
        # 构建回复
        time_info = []
        
        for record in records:
            start_time = record.get("start_time")
            end_time = record.get("end_time")
            duration = record.get("duration")
            
            if start_time and end_time and duration:
                time_info.append(f"{start_time}-{end_time} ({duration})")
            elif start_time and end_time:
                time_info.append(f"{start_time}-{end_time}")
            elif start_time:
                time_info.append(f"{start_time}")
        
        if time_info:
            if situation_type == "玩手机":
                if len(time_info) == 1:
                    return f"根据今天的监控记录，你在 {time_info[0]} 玩手机了。"
                else:
                    return f"根据今天的监控记录，你在以下时间段玩手机了：{'; '.join(time_info)}。"
            else:
                if len(time_info) == 1:
                    return f"根据今天的监控记录，你在 {time_info[0]} {situation_type}了。"
                else:
                    return f"根据今天的监控记录，你在以下时间段{situation_type}了：{'; '.join(time_info)}。"
        else:
            return f"找到了关于今天{situation_type}的记录，但无法确定具体时间。"
            
    except Exception as e:
        print(f"查询监控记录时出错: {e}")
        import traceback
        traceback.print_exc()
        return None

# --- API 路由：处理语音输入 ---
@app.route('/api/voice/process', methods=['POST'])
def process_voice():
    print("=== Voice processing endpoint called ===")
    if 'audio' not in request.files:
        print("Error: No audio file provided in request")
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files['audio']
    audio_data = audio_file.read() # 读取二进制音频数据
    print(f"Received audio data of size: {len(audio_data)} bytes")

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
            print("开始从音频文件读取数据...")
            audio_source = recognizer.record(source)
        
        print("开始进行语音识别...")
        user_text = recognizer.recognize_google(audio_source, language='zh-CN')
        print("ASR OUT:", user_text)

        # 检查是否是特定的查询模式
        monitoring_response = query_monitoring_records(user_text)
        if monitoring_response:
            print(f"从监控记录中获取到回答: {monitoring_response}")
            
            # 生成 AI 语音响应
            tts_filename = f"ai_response_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            tts_output_path = os.path.join(TTS_OUTPUT_DIR, tts_filename)
            
            print(f"开始生成 TTS 语音，输出路径: {tts_output_path}")
            asyncio.run(tts_generate_audio(monitoring_response, tts_output_path))
            print(f"AI 语音已生成至: {tts_output_path}")

            # 返回响应数据
            audio_url = f"/audio/{tts_filename}"
            print(f"返回响应，音频URL: {audio_url}")

            return jsonify({
                "userText": user_text,
                "aiResponse": monitoring_response,
                "audioUrl": audio_url
            })
        
        # 如果不是特定查询模式或没有找到监控记录，则使用大模型回答
        prompt = user_text + "，回答可以详细，50字以内！"
        print(f"调用大模型，提示词: {prompt}")
        ai_response = call_qwen_api(prompt)
        print("Answer:", ai_response)

        if not ai_response:
            print("大模型未能提供有效回答")
            return jsonify({"userText": user_text, "aiResponse": "大模型未能提供有效回答。"}), 200
        
        # 生成 AI 语音响应
        tts_filename = f"ai_response_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        tts_output_path = os.path.join(TTS_OUTPUT_DIR, tts_filename)
        
        print(f"开始生成 TTS 语音，输出路径: {tts_output_path}")
        asyncio.run(tts_generate_audio(ai_response, tts_output_path))
        print(f"AI 语音已生成至: {tts_output_path}")

        # 返回响应数据
        audio_url = f"/audio/{tts_filename}"
        print(f"返回响应，音频URL: {audio_url}")

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
        import traceback
        traceback.print_exc()
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
        # 检查是否是特定的查询模式
        monitoring_response = query_monitoring_records(query)
        if monitoring_response:
            print(f"从监控记录中获取到回答: {monitoring_response}")
            return jsonify({"status": "success", "answer": monitoring_response})
        
        # 如果不是特定查询模式或没有找到监控记录，则使用大模型回答
        ai_response = call_qwen_api(query)
        if ai_response:
            return jsonify({"status": "success", "answer": ai_response})
        else:
            return jsonify({"status": "error", "message": "大模型未能提供有效回答。"}), 500
    except Exception as e:
        print(f"处理文本消息时出错: {e}")
        return jsonify({"status": "error", "message": f"服务器内部错误: {e}"}), 500

# --- API 路由：获取监控数据 ---
@app.route('/api/monitoring/data', methods=['GET'])
def get_monitoring_data_api():
    try:
        # 获取查询参数
        activity_type = request.args.get('activity_type')
        today_only_str = request.args.get('today_only', 'true')
        today_only = today_only_str.lower() == 'true'
        
        # 获取监控数据
        records = get_monitoring_data(activity_type=activity_type, today_only=today_only)
        
        return jsonify({
            "status": "success",
            "records": records
        })
    except Exception as e:
        print(f"获取监控数据时出错: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"服务器内部错误: {e}"}), 500

# --- API 路由：更新监控数据 ---
@app.route('/api/monitoring/update', methods=['POST'])
def update_monitoring_data():
    try:
        # 获取请求数据
        data = request.get_json()
        records = data.get('records', [])
        
        if not records:
            return jsonify({"status": "error", "message": "没有提供记录数据"}), 400
        
        # 确保每条记录都有日期字段，使用当前日期
        today_str = datetime.datetime.now().strftime('%Y-%m-%d')
        for record in records:
            if 'date' not in record or not record['date']:
                record['date'] = today_str
        
        # 保存到监控数据文件
        with open(MONITORING_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({"records": records}, f, ensure_ascii=False, indent=2)
        
        print(f"已更新监控数据文件: {MONITORING_DATA_FILE}")
        print(f"更新的记录数: {len(records)}")
        
        return jsonify({
            "status": "success",
            "message": "监控数据已更新",
            "count": len(records)
        })
    except Exception as e:
        print(f"更新监控数据时出错: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"服务器内部错误: {e}"}), 500

# --- 运行 Flask 应用 ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 