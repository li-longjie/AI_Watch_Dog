document.addEventListener('DOMContentLoaded', function() {
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const chatMessages = document.getElementById('chatMessages');
    const newChatBtn = document.getElementById('newChatBtn');
    
    let isProcessing = false;
    
    // 自动调整输入框高度
    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        
        // 启用/禁用发送按钮
        sendBtn.disabled = this.value.trim() === '';
    });
    
    // 处理发送按钮点击
    sendBtn.addEventListener('click', sendMessage);
    
    // 处理Enter键发送(Shift+Enter换行)
    messageInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendBtn.disabled && !isProcessing) {
                sendMessage();
            }
        }
    });
    
    // 处理新对话按钮
    newChatBtn.addEventListener('click', function() {
        if (confirm('确定要开始新对话吗？当前对话记录将被清除。')) {
            clearHistory();
            resetChatUI();
        }
    });
    
    // 加载历史消息
    loadHistory();
    
    // 发送消息函数
    function sendMessage() {
        if (isProcessing) return;
        
        const message = messageInput.value.trim();
        if (!message) return;
        
        // 添加用户消息到UI
        appendMessage('user', message);
        
        // 清空输入框并调整高度
        messageInput.value = '';
        messageInput.style.height = 'auto';
        sendBtn.disabled = true;
        
        // 显示加载指示器
        isProcessing = true;
        const loadingElement = appendTypingIndicator();
        
        // 发送请求到服务器
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('网络错误');
            }
            return response.json();
        })
        .then(data => {
            // 移除加载指示器
            if (loadingElement) {
                loadingElement.remove();
            }
            
            // 添加助手回复
            if (data.error) {
                appendMessage('assistant', '错误: ' + data.error);
            } else {
                appendMessage('assistant', data.response);
            }
        })
        .catch(error => {
            // 移除加载指示器
            if (loadingElement) {
                loadingElement.remove();
            }
            
            // 显示错误消息
            appendMessage('assistant', '抱歉，发生了错误: ' + error.message);
        })
        .finally(() => {
            isProcessing = false;
            
            // 如果输入框有内容，启用发送按钮
            if (messageInput.value.trim() !== '') {
                sendBtn.disabled = false;
            }
        });
    }
    
    // 添加消息到UI
    function appendMessage(role, content) {
        // 隐藏欢迎信息
        const welcomeMessage = document.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }
        
        const messageElement = document.createElement('div');
        messageElement.className = `message ${role}`;
        
        const avatarElement = document.createElement('div');
        avatarElement.className = `message-avatar ${role}`;
        avatarElement.textContent = role === 'user' ? '我' : 'AI';
        
        const contentElement = document.createElement('div');
        contentElement.className = 'message-content';
        
        // 将换行符转换为<br>标签
        const formattedContent = formatMessage(content);
        contentElement.innerHTML = formattedContent;
        
        messageElement.appendChild(avatarElement);
        messageElement.appendChild(contentElement);
        
        chatMessages.appendChild(messageElement);
        
        // 滚动到底部
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // 格式化消息内容
    function formatMessage(content) {
        // 基本的Markdown解析
        let formatted = content
            // 处理代码块
            .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
            // 处理内联代码
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            // 处理URL链接
            .replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank">$1</a>')
            // 换行符转换为<br>
            .replace(/\n/g, '<br>');
            
        return formatted;
    }
    
    // 添加正在输入指示器
    function appendTypingIndicator() {
        const indicatorElement = document.createElement('div');
        indicatorElement.className = 'message assistant';
        
        const avatarElement = document.createElement('div');
        avatarElement.className = 'message-avatar assistant';
        avatarElement.textContent = 'AI';
        
        const contentElement = document.createElement('div');
        contentElement.className = 'message-content';
        
        const typingIndicator = document.createElement('div');
        typingIndicator.className = 'typing-indicator';
        
        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('div');
            dot.className = 'typing-dot';
            typingIndicator.appendChild(dot);
        }
        
        contentElement.appendChild(typingIndicator);
        indicatorElement.appendChild(avatarElement);
        indicatorElement.appendChild(contentElement);
        
        chatMessages.appendChild(indicatorElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        return indicatorElement;
    }
    
    // 加载历史记录
    function loadHistory() {
        fetch('/api/history')
        .then(response => response.json())
        .then(data => {
            if (data.messages && data.messages.length > 0) {
                // 隐藏欢迎信息
                const welcomeMessage = document.querySelector('.welcome-message');
                if (welcomeMessage) {
                    welcomeMessage.style.display = 'none';
                }
                
                // 添加历史消息
                data.messages.forEach(msg => {
                    appendMessage(msg.role, msg.content);
                });
            }
        })
        .catch(error => {
            console.error('加载历史记录失败:', error);
        });
    }
    
    // 清除历史记录
    function clearHistory() {
        fetch('/api/clear', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            console.log('历史记录已清除');
        })
        .catch(error => {
            console.error('清除历史记录失败:', error);
        });
    }
    
    // 重置聊天UI
    function resetChatUI() {
        chatMessages.innerHTML = `
        <div class="welcome-message">
            <h1>智能聊天助手</h1>
            <p>您可以直接开始对话，也可以输入网址让我分析网页内容</p>
            <div class="examples">
                <div class="example-row">
                    <div class="example" onclick="setInput('告诉我关于人工智能的最新进展')">
                        <div class="example-title">告诉我关于人工智能的最新进展</div>
                    </div>
                    <div class="example" onclick="setInput('https://www.example.com')">
                        <div class="example-title">分析网页内容: https://www.example.com</div>
                    </div>
                </div>
                <div class="example-row">
                    <div class="example" onclick="setInput('解释量子计算的基本原理')">
                        <div class="example-title">解释量子计算的基本原理</div>
                    </div>
                    <div class="example" onclick="setInput('现在几点了？')">
                        <div class="example-title">查询当前时间</div>
                    </div>
                </div>
            </div>
        </div>
        `;
    }
});

// 设置输入框内容(用于示例点击)
function setInput(text) {
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    
    messageInput.value = text;
    messageInput.style.height = 'auto';
    messageInput.style.height = (messageInput.scrollHeight) + 'px';
    sendBtn.disabled = false;
    
    // 聚焦到输入框
    messageInput.focus();
} 