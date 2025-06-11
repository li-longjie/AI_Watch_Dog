from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import speech_recognition as sr
import edge_tts
import asyncio
import os
import tempfile
import requests
import json
from datetime import datetime
from fastapi.responses import FileResponse

app = FastAPI()

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置
API_URL = "https://api.siliconflow.cn/v1/chat/completions"
API_KEY = "sk-szjxvsopbfddnsxpiumkgkmcusqhpflilhbszpwwozlwzxzb"
MODEL_NAME = "Qwen/Qwen2-7B-Instruct"

# 创建临时目录
TEMP_DIR = os.path.join(tempfile.gettempdir(), "voice_chat")
os.makedirs(TEMP_DIR, exist_ok=True)

@app.post("/api/voice/process")
async def process_voice(audio: UploadFile = File(...)):
    try:
        # 保存上传的音频文件
        temp_audio_path = os.path.join(TEMP_DIR, f"input_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")
        with open(temp_audio_path, "wb") as f:
            content = await audio.read()
            f.write(content)

        # 语音识别
        recognizer = sr.Recognizer()
        with sr.AudioFile(temp_audio_path) as source:
            audio_data = recognizer.record(source)
            user_text = recognizer.recognize_google(audio_data, language='zh-CN')

        # 调用大模型 API
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": "你叫千问，是一个18岁的女大学生，性格活泼开朗，说话俏皮"},
                {"role": "user", "content": user_text + "，回答可以详细，50字以内！"}
            ],
            "temperature": 0.7,
            "max_tokens": 512,
            "top_p": 0.8,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0
        }

        response = requests.post(API_URL, headers=headers, json=data)
        response.raise_for_status()
        ai_response = response.json()['choices'][0]['message']['content']

        # 生成语音回复
        output_audio_path = os.path.join(TEMP_DIR, f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3")
        communicate = edge_tts.Communicate(ai_response, "zh-CN-XiaoyiNeural")
        await communicate.save(output_audio_path)

        # 清理临时文件
        os.remove(temp_audio_path)

        return {
            "userText": user_text,
            "aiResponse": ai_response,
            "audioUrl": f"/api/voice/audio/{os.path.basename(output_audio_path)}"
        }

    except Exception as e:
        print(f"处理语音时出错: {str(e)}")
        return {"error": str(e)}

@app.get("/api/voice/audio/{filename}")
async def get_audio(filename: str):
    audio_path = os.path.join(TEMP_DIR, filename)
    if os.path.exists(audio_path):
        return FileResponse(audio_path)
    return {"error": "音频文件不存在"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=16532) 