# 智能RAG系统 - MCP工具集成架构

## 概述

这是一个全新的架构设计，将原有RAG系统中的MCP（Model Context Protocol）工具调用功能完全模块化，并引入了LLM驱动的智能意图识别机制。

## 架构特点

### 🎯 核心改进
- **完全移除关键词匹配**：不再使用硬编码的关键词来判断用户意图
- **LLM智能路由**：让大模型自主判断是否需要使用工具，以及使用哪个工具
- **模块化设计**：每个MCP工具独立为单独的类，易于扩展和维护
- **标准化接口**：统一的工具接口设计，支持动态工具发现

### 🏗️ 架构组件

```
智能RAG系统 v2.0
├── intelligent_agent.py          # 智能代理核心
├── mcp_tools/                     # MCP工具包
│   ├── __init__.py
│   ├── base_tool.py              # 工具基类
│   ├── tool_registry.py          # 工具注册表
│   ├── fetch_tool.py             # 网页抓取工具
│   ├── time_tool.py              # 时间工具
│   ├── filesystem_tool.py        # 文件系统工具
│   └── browser_tool.py           # 浏览器工具
├── rag_server_v2.py              # 新版RAG服务器
└── test_intelligent_agent.py     # 测试脚本
```

## 工作原理

### 1. 智能意图识别

用户发送自然语言请求 → LLM分析意图 → 智能选择工具或直接回答

```python
# 示例：LLM自动识别意图
用户: "现在几点了？"
LLM分析: 需要获取时间信息 → 选择时间工具
结果: 调用get_current_time函数

用户: "你好，今天天气怎么样？"  
LLM分析: 普通聊天，无需工具 → 直接回答
结果: 生成友好的回复
```

### 2. 工具自动发现

系统启动时自动注册所有MCP工具，并生成详细的工具描述传递给LLM：

```python
class ToolRegistry:
    def format_tools_for_llm(self) -> str:
        """格式化所有工具信息供LLM理解"""
        # 自动生成包含所有工具、函数、参数的完整描述
```

### 3. 统一工具接口

所有工具都继承自基类，确保接口一致性：

```python
class BaseMCPTool(ABC):
    @abstractmethod
    async def execute_function(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行指定函数"""
        pass
    
    @abstractmethod
    def get_available_functions(self) -> Dict[str, Dict[str, Any]]:
        """获取可用函数列表及其描述"""
        pass
```

## 可用工具

### 🌐 网页抓取工具 (FetchTool)
- **功能**: 获取任意URL的网页内容
- **函数**: `fetch_webpage(url, max_length)`
- **示例**: "帮我抓取https://www.baidu.com的内容"

### ⏰ 时间工具 (TimeTool)
- **功能**: 获取当前时间和日期信息
- **函数**: `get_current_time(timezone)`
- **示例**: "现在几点了？", "今天是几号？"

### 📁 文件系统工具 (FilesystemTool)
- **功能**: 列出目录内容，查看文件信息
- **函数**: `list_directory(path)`
- **示例**: "查看桌面上有什么文件"

### 🌍 浏览器工具 (BrowserTool)
- **功能**: 浏览器自动化和深度搜索
- **函数**: 
  - `run_browser_agent(task, add_infos)` - 浏览器自动化
  - `run_deep_search(research_task)` - 深度网络搜索
- **示例**: "打开百度搜索Python教程", "研究AI最新发展趋势"

## 使用方法

### 启动新版服务器

```bash
python rag_server_v2.py
```

新服务器运行在端口8086，提供以下接口：

- `POST /chat/` - 智能聊天接口（集成所有功能）
- `GET /capabilities/` - 获取系统能力信息
- `GET /health/` - 健康检查
- 其他原有接口保持兼容

### API调用示例

```python
import requests

# 智能聊天 - 自动工具选择
response = requests.post("http://localhost:8086/chat/", 
    json={"query": "现在几点了？"})

# 系统会自动：
# 1. LLM分析用户意图
# 2. 选择时间工具
# 3. 调用get_current_time函数
# 4. 返回自然语言回答
```

### 测试系统

```bash
python test_intelligent_agent.py
```

测试脚本包含：
- 基本能力测试
- 不同工具类型测试
- 交互式测试模式

## 系统提示词机制

智能代理会自动生成包含所有工具信息的系统提示词：

```
# 可用的MCP工具 (4个)

以下是所有可用的MCP工具及其功能...

## 时间工具
**描述**: 用于获取当前时间、日期等时间相关信息

**可用函数**:
### get_current_time
- **描述**: 获取当前的日期和时间信息
- **参数**:
  - `timezone` (string) (可选): 时区设置，默认为Asia/Shanghai
- **使用示例**:
  - 现在几点了？
  - 今天是几号？
...
```

## LLM响应格式

LLM必须按照标准JSON格式响应：

```json
// 使用工具时
{
    "action": "use_tool",
    "tool_name": "时间工具",
    "function_name": "get_current_time", 
    "parameters": {
        "timezone": "Asia/Shanghai"
    },
    "reasoning": "用户询问时间，需要调用时间工具获取当前时间"
}

// 直接回答时
{
    "action": "direct_answer",
    "answer": "你好！我是智能助手，很高兴为你服务。",
    "reasoning": "这是普通的问候，不需要使用任何工具"
}
```

## 扩展新工具

添加新的MCP工具非常简单：

### 1. 创建工具类

```python
# mcp_tools/new_tool.py
from .base_tool import BaseMCPTool

class NewTool(BaseMCPTool):
    @property
    def tool_name(self) -> str:
        return "新工具"
    
    @property 
    def description(self) -> str:
        return "新工具的描述"
    
    def get_available_functions(self):
        return {
            "new_function": {
                "description": "新函数的描述",
                "parameters": {...},
                "examples": [...]
            }
        }
    
    async def execute_function(self, function_name, parameters):
        # 实现具体功能
        pass
```

### 2. 注册到系统

```python
# mcp_tools/tool_registry.py
from .new_tool import NewTool

def _initialize_tools(self):
    # 添加新工具
    self.register_tool(NewTool(self.base_url))
```

### 3. 更新导入

```python
# mcp_tools/__init__.py
from .new_tool import NewTool
```

## 优势对比

### 🔄 旧架构 vs 新架构

| 方面 | 旧架构 | 新架构 |
|------|--------|--------|
| 意图识别 | 关键词匹配 | LLM智能分析 |
| 工具集成 | 硬编码在主文件 | 模块化独立 |
| 扩展性 | 需要修改核心代码 | 添加新工具类即可 |
| 维护性 | 工具耦合严重 | 工具完全解耦 |
| 准确性 | 依赖关键词覆盖 | LLM理解自然语言 |
| 灵活性 | 固定匹配规则 | 动态意图理解 |

### 📈 性能优化

- **并行处理**: 工具调用异步执行
- **智能缓存**: 工具结果可缓存复用
- **错误恢复**: 工具失败时自动降级
- **超时处理**: 避免长时间等待

## 配置说明

### MCP服务配置

确保`mcp.json`配置正确：

```json
{
  "mcpServers": {
    "fetch": {"command": "uvx", "args": ["mcp-server-fetch"]},
    "time": {"command": "uvx", "args": ["mcp-server-time"]},
    "filesystem": {"command": "npx", "args": [...]},
    "browser-use": {"command": "uv", "args": [...]}
  }
}
```

### 环境变量

```bash
export MCP_API_KEY="your-api-key"
export MCP_MODEL_PROVIDER="deepseek"
export MCP_BASE_URL="http://127.0.0.1:8000"
```

## 故障排除

### 常见问题

1. **工具未注册**: 检查`tool_registry.py`中的工具初始化
2. **LLM格式错误**: 查看`intelligent_agent.py`中的解析逻辑
3. **MCP服务不可用**: 验证MCP服务器状态
4. **权限问题**: 确保文件系统工具有足够权限

### 调试技巧

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 测试单个工具
from mcp_tools import TimeTool
tool = TimeTool()
result = await tool.execute_function("get_current_time", {})
```

## 未来规划

- [ ] 支持工具链调用（多个工具协作）
- [ ] 添加工具使用统计和分析
- [ ] 实现工具权限管理
- [ ] 支持用户自定义工具
- [ ] 添加工具性能监控

## 贡献指南

欢迎贡献新的MCP工具！请遵循以下步骤：

1. 继承`BaseMCPTool`类
2. 实现必需的抽象方法
3. 添加完整的函数文档和示例
4. 编写测试用例
5. 更新注册表

---

**总结**: 这个新架构实现了真正的智能工具选择，移除了关键词匹配的限制，让LLM根据自然语言理解来决定工具使用，大大提升了系统的灵活性和准确性。 