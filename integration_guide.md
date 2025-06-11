# 前端集成指南：将 app.py 功能整合到 http://localhost:5173

## 🎯 目标
将 `app.py` 的所有功能（文件操作、旅游规划、搜索、时间查询等）整合到现有的 `http://localhost:5173` 前端界面中。

## 🔧 已完成的后端修改

### 1. 端口配置
- `rag_server.py`: 端口 **8085** (监控、RAG搜索)
- `app.py`: 端口 **8086** (文件操作、旅游规划、搜索等)

### 2. 新增API端点
在 `app.py` 中新增了统一的聊天API：
```
POST http://localhost:8086/api/unified-chat
```

请求格式：
```json
{
  "message": "用户输入的消息"
}
```

响应格式：
```json
{
  "status": "success",
  "answer": "AI回答内容",
  "is_markdown": true,
  "messages": [...],
  "intent": {...}
}
```

## 🚀 前端集成方案

### 方案一：智能路由（推荐）
在前端的消息发送函数中添加智能路由逻辑：

```javascript
async function sendMessage(userMessage) {
    try {
        // 1. 先判断是否为监控相关查询
        const monitoringKeywords = ['监控', '摄像头', '发现', '检测到', '看到', '观察到', '显示', '记录', '什么时候'];
        const isMonitoring = monitoringKeywords.some(keyword => userMessage.includes(keyword));
        
        let response;
        
        if (isMonitoring) {
            // 调用 RAG 服务 (rag_server.py)
            response = await fetch('http://localhost:8085/detect_intent/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: userMessage })
            });
        } else {
            // 调用综合服务 (app.py)
            response = await fetch('http://localhost:8086/api/unified-chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: userMessage })
            });
        }
        
        const result = await response.json();
        
        // 统一处理响应
        if (result.status === 'success' || result.answer) {
            const answer = result.answer || result.response;
            displayMessage(answer, 'assistant');
        } else {
            displayMessage('抱歉，处理您的请求时出现了问题。', 'assistant');
        }
        
    } catch (error) {
        console.error('发送消息失败:', error);
        displayMessage('网络连接错误，请稍后重试。', 'assistant');
    }
}
```

### 方案二：并行尝试
同时向两个服务发送请求，使用响应更快或更相关的结果：

```javascript
async function sendMessage(userMessage) {
    try {
        // 并行发送到两个服务
        const [ragPromise, appPromise] = await Promise.allSettled([
            fetch('http://localhost:8085/detect_intent/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: userMessage })
            }),
            fetch('http://localhost:8086/api/unified-chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: userMessage })
            })
        ]);
        
        // 优先使用成功的响应
        let bestResponse = null;
        
        if (ragPromise.status === 'fulfilled' && ragPromise.value.ok) {
            const ragResult = await ragPromise.value.json();
            if (ragResult.status === 'success' && ragResult.answer) {
                bestResponse = ragResult.answer;
            }
        }
        
        if (!bestResponse && appPromise.status === 'fulfilled' && appPromise.value.ok) {
            const appResult = await appPromise.value.json();
            if (appResult.status === 'success' && appResult.answer) {
                bestResponse = appResult.answer;
            }
        }
        
        if (bestResponse) {
            displayMessage(bestResponse, 'assistant');
        } else {
            displayMessage('抱歉，暂时无法处理您的请求。', 'assistant');
        }
        
    } catch (error) {
        console.error('发送消息失败:', error);
        displayMessage('网络连接错误，请稍后重试。', 'assistant');
    }
}
```

## 📋 功能分类

### RAG服务 (8085端口)
- ✅ 监控视频分析
- ✅ 历史记录查询
- ✅ 时间相关查询
- ✅ 网页内容提取
- ✅ 浏览器自动化任务
- ✅ 深度搜索研究

### 综合服务 (8086端口) 
- ✅ **文件操作**（读取、写入、创建、重命名、移动）
- ✅ **旅游规划**（景点推荐、路线规划、交通方式）
- ✅ **地图服务**（路线规划、地点搜索、天气查询）
- ✅ **网络搜索**（DuckDuckGo搜索）
- ✅ **语音合成**（TTS功能）
- ✅ **逐步推理**（Sequential Thinking）
- ✅ **时间查询**
- ✅ **日常对话**

## 🏃‍♂️ 启动步骤

1. **启动RAG服务**：
   ```bash
   cd d:\PyCharm\workplace\AI_Watch_Dog
   python rag_server.py
   ```
   
2. **启动综合服务**：
   ```bash
   cd d:\PyCharm\workplace\AI_Watch_Dog\mcpo2
   python app.py
   ```
   
3. **启动前端**：
   ```bash
   # 在前端项目目录
   npm run dev
   # 访问 http://localhost:5173
   ```

## 🎨 用户体验

集成后，用户在 `http://localhost:5173` 的对话框中可以：

- 🔍 **询问监控**: "今天有什么监控记录？"
- 📁 **文件操作**: "桌面上有什么文件？"
- 🗺️ **旅游规划**: "制定兴城一日游计划"
- 🚌 **路线查询**: "从沈阳站到沈阳北站怎么走？"
- 🔎 **网络搜索**: "搜索最新的AI技术发展"
- 🎵 **语音合成**: "帮我生成语音：你好世界"
- 🕒 **时间查询**: "现在几点了？"
- 💭 **复杂推理**: "帮我分析这个问题的解决方案"

## 🔧 测试命令

测试两个服务是否正常工作：

```bash
# 测试RAG服务
curl -X POST http://localhost:8085/detect_intent/ \
  -H "Content-Type: application/json" \
  -d '{"query": "今天的监控记录"}'

# 测试综合服务  
curl -X POST http://localhost:8086/api/unified-chat \
  -H "Content-Type: application/json" \
  -d '{"message": "桌面上有什么文件？"}'
```

这样就可以在一个统一的前端界面中使用所有功能了！ 