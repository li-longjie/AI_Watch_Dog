# 智能在线聊天系统 - MCPO测试项目

这是一个基于Flask的在线聊天系统，专门设计用于测试和展示MCPO（MCP-to-OpenAPI代理服务器）的功能。本项目集成了AI大模型对话、网页内容分析和时间查询功能，通过MCPO实现对MCP服务的标准化访问。
<img width="959" alt="5e43cedcb1b2e730f6f3ecc40f78529" src="https://github.com/user-attachments/assets/f6b7ec99-d2ab-455f-8945-1bfff702cddd" />

## 关于MCPO

MCPO（MCP-to-OpenAPI）是一个简单高效的代理服务器，可以将任何基于MCP（Model Context Protocol）的工具即时转换为符合OpenAPI标准的HTTP服务器，实现：

- ✅ 通过标准RESTful API访问MCP服务
- 🛡 增强安全性、稳定性和可扩展性
- 🧠 自动生成每个工具的交互式文档
- 🔌 使用纯HTTP协议，无需套接字、无需胶水代码

本项目正是MCPO的一个实际应用案例，展示了如何将MCP服务（时间查询和网页内容获取）集成到Web应用中。

## 功能特点

- **AI对话**：接入OpenRouter API，提供DeepSeek等大模型对话服务
- **网页内容分析**：自动识别用户消息中的URL，获取网页内容并进行分析
- **时间信息查询**：支持用户查询当前时间，获取精确的时区和时间信息
- **文件系统访问**：可直接查询桌面文件，自动列出文件和文件夹
- **聊天历史记录**：保存会话历史，支持清空历史记录

## 系统架构

系统由以下几个主要部分组成：

1. **Flask前端应用**：提供Web界面和API接口
2. **MCPO服务**：将MCP工具转换为标准OpenAPI服务
   - Fetch服务：负责获取网页内容
   - Time服务：提供精确的时间信息
   - Filesystem服务：访问桌面文件系统
3. **AI大模型**：通过OpenRouter API接入DeepSeek等大模型

## MCPO的优势

在本项目中，MCPO提供了以下关键优势：

- **用户友好且熟悉的接口**：无需自定义客户端，只使用HTTP REST端点
- **即时集成**：立即兼容数千种现有的REST/OpenAPI工具、SDK和服务
- **强大的自动文档**：内置Swagger UI文档自动生成，始终准确并维护
- **无新协议开销**：消除了直接处理MCP特定协议复杂性和套接字通信问题的必要性
- **经过验证的安全性和稳定性**：继承了成熟的HTTPS传输、标准认证方法（JWT、API密钥）

## 安装与运行

### 必备条件

- Python 3.11+
- Flask
- MCPO服务

### 安装步骤

1. 安装Python依赖：
```bash
pip install flask requests
```

2. 安装MCPO服务：
```bash
pip install mcpo
```

3. 安装文件系统MCP服务：
```bash
npm install -g @modelcontextprotocol/server-filesystem
```

4. 运行MCPO服务：
```bash
mcpo --config mcp.json --port 8000
```

5. 运行Flask应用：
```bash
python app.py
```

6. 访问应用：
在浏览器中打开 http://127.0.0.1:5000

## 配置说明

### mcp.json配置

```json
{
  "mcpServers": {
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"]
    },
    "time": {
      "command": "uvx",
      "args": ["mcp-server-time", "--local-timezone=America/New_York"]
    },
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "C:\\Users\\Jason\\Desktop"
      ]
    }
  }
}
```

通过这个配置文件，MCPO会自动创建三个服务端点：
- http://localhost:8000/fetch - 用于获取网页内容
- http://localhost:8000/time - 用于获取时间信息
- http://localhost:8000/filesystem - 用于访问桌面文件系统

每个服务都有自己专用的OpenAPI文档（可通过/fetch/docs、/time/docs和/filesystem/docs访问）。

### API配置

在`app.py`中配置以下参数：

- `OPENROUTER_API_KEY`：OpenRouter API密钥
- `OPENROUTER_API_URL`：OpenRouter API URL
- `OPENROUTER_MODEL`：使用的模型，如"deepseek/deepseek-chat-v3-0324:free"
- `MCP_FETCH_URL`：MCPO Fetch服务地址
- `MCP_TIME_URL`：MCPO Time服务地址
- `MCP_FILESYSTEM_URL`：MCPO Filesystem服务地址

## 使用说明

1. 启动MCPO服务
2. 启动Flask应用
3. 在浏览器中访问应用
4. 在聊天框中输入消息：
   - 询问时间信息，如"现在几点了？"
   - 输入URL进行网页内容分析
   - 任何其他问题进行普通对话

## 文件结构

```
├── app.py                # Flask应用主文件
├── fetch_webpage.py      # 网页内容获取功能实现
├── filesystem_operations.py # 文件系统操作功能实现
├── mcp.json              # MCPO服务配置文件
├── templates/            # HTML模板目录
│   ├── chat.html         # 聊天页面模板
│   ├── filesystem.html   # 文件系统管理页面
│   └── index.html        # 首页模板
└── static/               # 静态资源目录
    ├── css/              # CSS样式文件
    │   ├── chat.css      # 聊天页面样式
    │   └── style.css     # 通用样式
    └── js/               # JavaScript文件
        ├── chat.js       # 聊天功能脚本
        └── script.js     # 通用脚本
```

## 测试MCPO的目标

本项目作为MCPO的测试应用，旨在验证：

1. MCPO服务的稳定性和可靠性
2. MCP工具转换为OpenAPI的效果
3. 在实际Web应用中集成MCPO的便捷性
4. 多种MCP服务（时间、网页内容获取）的并行运行能力
5. 通过标准RESTful API访问MCP服务的用户体验

## 故障排除

如果遇到问题，请检查：

1. MCPO服务是否正常运行（通过访问http://localhost:8000/docs验证）
2. API端点配置是否正确（注意路径格式，应为/服务名称/服务名称）
3. 网络连接是否正常
4. API密钥是否有效

## 开发和扩展

可以通过以下方式扩展系统功能：

1. 添加新的MCP服务到test.json
2. 增强AI提示词工程
3. 添加更多专业领域的分析能力
4. 改进用户界面和体验

## 了解更多关于MCPO

如需了解更多关于MCPO的信息，请访问：
- GitHub仓库：https://github.com/open-webui/mcpo
- 官方文档：https://docs.openwebui.com/openapi-servers/mcp/
