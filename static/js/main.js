// WebSocket连接
let videoWs;
let alertWs;

function initWebSockets() {
    // 视频连接
    videoWs = new WebSocket(`ws://${window.location.host}/video_feed`);
    videoWs.onopen = function() {
    };
    videoWs.onclose = function() {
        setTimeout(initWebSockets, 5000); // 5秒后重连
    };
    videoWs.onerror = function(error) {
        console.error("视频WebSocket连接错误:", error);
    };
    videoWs.onmessage = function(event) {
        if (event.data instanceof Blob) {
            event.data.arrayBuffer().then(buffer => {
                const blob = new Blob([buffer], {type: 'image/jpeg'});
                videoElement.src = URL.createObjectURL(blob);
            });
        }
    };
    
    // 警报连接
    alertWs = new WebSocket(`ws://${window.location.host}/alerts`);
    setupAlertHandlers(alertWs);
}

// 初始化WebSocket
initWebSockets();

const videoElement = document.getElementById('video-feed');
const warningVideoElement = document.getElementById('warning-video');
const warningVideoSource = document.getElementById('warning-video-source');
const alertsDiv = document.getElementById('alerts');
const qaHistory = document.getElementById('qa-history');
const currentTimeElement = document.getElementById('current-time');
const serverTimeElement = document.getElementById('server-time');
const alertCountElement = document.getElementById('alert-count');
const askTextElement = document.getElementById('ask-text');
const askLoaderElement = document.getElementById('ask-loader');

let alertCount = 0;

// 更新时间显示
function updateTime() {
    const now = new Date();
    const timeStr = `${now.getFullYear()}/` + 
                   `${(now.getMonth()+1).toString().padStart(2, '0')}/` + 
                   `${now.getDate().toString().padStart(2, '0')} ` + 
                   `${now.getHours().toString().padStart(2, '0')}:` + 
                   `${now.getMinutes().toString().padStart(2, '0')}:` + 
                   `${now.getSeconds().toString().padStart(2, '0')}`;
    
    // 更新状态栏时间
    const timeElement = document.getElementById('current-time');
    if (timeElement) {
        timeElement.textContent = timeStr;
    }
    
    // 更新视频时间戳
    const timestampElement = document.getElementById('video-timestamp');
    if (timestampElement) {
        timestampElement.textContent = timeStr;
    }
}

videoElement.onload = function() {
    if (videoElement.src.startsWith('blob:')) {
        URL.revokeObjectURL(videoElement.src);
    }
};

// 更新预警视频
function updateWarningVideo() {
    const timestamp = new Date().getTime();
    warningVideoSource.src = `/video_warning/output.mp4?t=${timestamp}`;
    warningVideoElement.load();
    warningVideoElement.play().catch(e => console.log("自动播放失败，可能需要用户交互:", e));
    
    // 添加脉冲动画效果
    warningVideoElement.parentElement.classList.add('pulse');
    setTimeout(() => {
        warningVideoElement.parentElement.classList.remove('pulse');
    }, 3000);
}

// WebSocket连接处理
function setupWebSocketReconnection(socket, name) {
    socket.onclose = function(event) {
        console.log(`${name} 连接关闭，尝试重新连接...`);
        setTimeout(function() {
            console.log(`尝试重新连接 ${name}...`);
            if (name === '预警消息') {
                alertWs = new WebSocket(`ws://${window.location.host}/alerts`);
                setupWebSocketReconnection(alertWs, name);
                setupAlertHandlers(alertWs);
            } else {
                videoWs = new WebSocket(`ws://${window.location.host}/video_feed`);
                setupWebSocketReconnection(videoWs, name);
                setupVideoHandlers(videoWs);
            }
        }, 3000);
    };
}

// 预警消息处理
function setupAlertHandlers(ws) {
    ws.onmessage = function(event) {
        console.log("收到WebSocket消息:", event.data);
        
        // 删除"暂无预警信息"提示
        const noDataDiv = document.querySelector('.alerts-panel .no-data');
        if (noDataDiv) {
            noDataDiv.remove();
        }
        
        try {
            const data = JSON.parse(event.data);
            console.log("解析后数据:", data);
            
            // 更新预警计数
            alertCount++;
            alertCountElement.textContent = alertCount;
            alertCountElement.style.display = 'flex';
            
            // 创建预警元素
            const alertDiv = document.createElement('div');
            
            // 根据消息类型设置不同的样式
            let className = 'alert';
            let icon = 'ℹ️';
            
            if (data.level === "important" || data.content.includes("人员进行了")) {
                className = 'alert important';
                icon = '⚠️';
            } 
            else if (data.level === "warning") {
                className = 'alert';
                icon = '❗';
            }
            
            alertDiv.className = className;
            
            alertDiv.innerHTML = `
                <div class="alert-time">
                    <span class="alert-icon">${icon}</span>
                    ${new Date(data.timestamp).toLocaleString()}
                </div>
                <div class="alert-content">${data.content}</div>
                ${data.details ? `<div class="alert-details">${data.details.substring(0, 80)}...</div>` : ''}
            `;
            
            // 添加到预警区域顶部
            alertsDiv.insertBefore(alertDiv, alertsDiv.firstChild);
            
            // 添加动画效果
            alertDiv.style.opacity = '0';
            alertDiv.style.transform = 'translateX(-20px)';
            setTimeout(() => {
                alertDiv.style.transition = 'all 0.3s ease';
                alertDiv.style.opacity = '1';
                alertDiv.style.transform = 'translateX(0)';
            }, 10);
            
            // 更新预警视频
            if (data.image_url) {
                updateWarningVideo();
            }
            
            // 限制显示的预警数量
            if (alertsDiv.children.length > 20) {
                alertsDiv.removeChild(alertsDiv.lastChild);
            }
            
            // 播放通知声音
            playNotificationSound();
            
        } catch(e) {
            console.error("JSON解析错误:", e);
        }
    };
}

// 播放通知声音
function playNotificationSound() {
    const audio = new Audio('https://assets.mixkit.co/sfx/preview/mixkit-alarm-digital-clock-beep-989.mp3');
    audio.volume = 0.3;
    audio.play().catch(e => console.log("音频播放失败:", e));
}

// 应用连接机制
setupWebSocketReconnection(videoWs, '视频流');
setupWebSocketReconnection(alertWs, '预警消息');
setupAlertHandlers(alertWs);

// 问答功能
async function askQuestion() {
    const questionInput = document.getElementById('question');
    const question = questionInput.value.trim();
    if (!question) return;

    // 显示加载状态
    askTextElement.style.display = 'none';
    askLoaderElement.style.display = 'block';
    
    // 添加问题到历史记录
    const questionDiv = document.createElement('div');
    questionDiv.className = 'question';
    questionDiv.textContent = question;
    qaHistory.insertBefore(questionDiv, qaHistory.firstChild);
    
    // 滚动到最新问题
    qaHistory.scrollTop = 0;

    try {
        const response = await fetch('http://localhost:8085/search/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: question,
                k: 3
            })
        });

        const result = await response.json();
        
        // 恢复按钮状态
        askTextElement.style.display = 'block';
        askLoaderElement.style.display = 'none';
        
        if (result.status === 'success') {
            // 添加回答到历史记录
            const answerDiv = document.createElement('div');
            answerDiv.className = 'answer';
            answerDiv.textContent = result.answer;
            qaHistory.insertBefore(answerDiv, questionDiv.nextSibling);
        } else {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'answer';
            errorDiv.textContent = `错误：${result.message || '查询失败'}`;
            qaHistory.insertBefore(errorDiv, questionDiv.nextSibling);
        }

    } catch (error) {
        console.error('问答出错:', error);
        // 恢复按钮状态
        askTextElement.style.display = 'block';
        askLoaderElement.style.display = 'none';
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'answer';
        errorDiv.textContent = `错误：${error.message}`;
        qaHistory.insertBefore(errorDiv, questionDiv.nextSibling);
    }

    // 清空输入框
    questionInput.value = '';
}

// 回车键提交问题
document.getElementById('question').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        askQuestion();
    }
});

// 加载历史预警信息
fetch('/alerts')
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success' && data.alerts.length > 0) {
            // 清除"暂无预警信息"提示
            const noDataDiv = document.querySelector('.alerts-panel .no-data');
            if (noDataDiv) {
                noDataDiv.remove();
            }
            
            alertCount = data.alerts.length;
            alertCountElement.textContent = alertCount;
            alertCountElement.style.display = 'flex';
            
            data.alerts.forEach(alert => {
                const isImportant = alert.content.includes("人员进行了") || alert.level === "important";
                const icon = isImportant ? '⚠️' : '❗';
                
                const alertDiv = document.createElement('div');
                alertDiv.className = isImportant ? 'alert important' : 'alert';
                
                alertDiv.innerHTML = `
                    <div class="alert-time">
                        <span class="alert-icon">${icon}</span>
                        ${new Date(alert.timestamp).toLocaleString()}
                    </div>
                    <div class="alert-content">${alert.content}</div>
                    ${alert.details ? `<div class="alert-details">${alert.details.substring(0, 80)}...</div>` : ''}
                `;
                alertsDiv.appendChild(alertDiv);
            });
            
            // 更新预警视频
            updateWarningVideo();
        }
    });
    
// 模拟一些系统通知
setTimeout(() => {
    const sampleAlerts = [
        {
            timestamp: new Date().toISOString(),
            content: "系统自检完成，所有功能正常",
            level: "info"
        },
        {
            timestamp: new Date().toISOString(),
            content: "检测到摄像头已连接", /* 移除了"3个" */
            level: "info"
        }
    ];
    
    sampleAlerts.forEach(alert => {
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert';
        alertDiv.innerHTML = `
            <div class="alert-time">
                <span class="alert-icon">ℹ️</span>
                ${new Date(alert.timestamp).toLocaleString()}
            </div>
            <div class="alert-content">${alert.content}</div>
        `;
        alertsDiv.insertBefore(alertDiv, alertsDiv.firstChild);
    });
    
    // 移除"暂无预警信息"提示
    const noDataDiv = document.querySelector('.alerts-panel .no-data');
    if (noDataDiv) {
        noDataDiv.remove();
    }
}, 2000);

// 更新系统状态信息
function updateSystemStats() {
    // 随机生成内存和网络使用率
    const memUsage = Math.floor(Math.random() * 30) + 20; // 20-50%范围
    const netUsage = (Math.random() * 10 + 1).toFixed(1); // 1.0-11.0 Mbps范围
    
    // 更新DOM
    document.getElementById('memory-usage').textContent = `内存: ${memUsage}%`;
    document.getElementById('network-usage').textContent = `网络: ${netUsage} Mbps`;
}

// 页面加载时执行
document.addEventListener('DOMContentLoaded', function() {
    // 初始更新系统状态
    updateSystemStats();
    
    // 启动时间更新
    updateTime(); // 立即执行一次
    setInterval(updateTime, 1000);
    
    setInterval(updateSystemStats, 1000);
});