// 当前WebSocket连接
let videoSocket = null;

// 行为数据
let behaviorHistory = [];
let behaviorCounts = {
    "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0
};

// 图表对象
let timelineChart = null;
let distributionChart = null;

// 行为映射
const behaviorMap = {
    "1": "专注工作",
    "2": "吃东西",
    "3": "喝水",
    "4": "喝饮料",
    "5": "玩手机",
    "6": "睡觉",
    "7": "其他"
};

// 行为颜色
const behaviorColors = {
    "1": "#4CAF50",
    "2": "#FF9800",
    "3": "#2196F3",
    "4": "#9C27B0",
    "5": "#F44336",
    "6": "#607D8B",
    "7": "#795548"
};

// 连接WebSocket
function connectWebSocket() {
    if (videoSocket && videoSocket.readyState === WebSocket.OPEN) {
        return;
    }
    
    try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        videoSocket = new WebSocket(`${protocol}//${window.location.host}/video_feed`);
         
        videoSocket.onopen = function() {
            document.getElementById('status-text').textContent = '🟢 已连接到视频流';
            
            // 隐藏"无数据"提示
            document.getElementById('timeline-no-data').style.display = 'none';
            document.getElementById('distribution-no-data').style.display = 'none';
        };
        
        videoSocket.onclose = function() {
            console.log('WebSocket连接已关闭');
            document.getElementById('status-text').textContent = '🔴 视频连接已断开';
        };
        
        videoSocket.onerror = function(error) {
            console.error('WebSocket错误:', error);
            document.getElementById('status-text').textContent = '🔴 连接错误';
        };
        
        videoSocket.onmessage = function(event) {
            // 处理图像数据
            if (event.data instanceof Blob) {
                event.data.arrayBuffer().then(buffer => {
                    const blob = new Blob([buffer], {type: 'image/jpeg'});
                    document.getElementById('camera-feed').src = URL.createObjectURL(blob);
                });
                return;
            }
            
            // 处理JSON数据
            try {
                const data = JSON.parse(event.data);
                
                if (data.type === 'behavior') {
                    // 从content字段中提取行为编号
                    let behaviorNum = '7'; // 默认其他
                     
                    if (data.content && typeof data.content === 'string') {
                        const match = data.content.match(/检测到行为: (\d+)/);
                        if (match && match[1]) {
                            behaviorNum = match[1];
                        }
                    }
                     
                    // 从details字段中提取行为
                    if (data.details && typeof data.details === 'string') {
                        if (data.details.includes('专注工作')) behaviorNum = '1';
                        else if (data.details.includes('吃东西')) behaviorNum = '2';
                        else if (data.details.includes('喝水')) behaviorNum = '3';
                        else if (data.details.includes('喝饮料')) behaviorNum = '4';
                        else if (data.details.includes('玩手机')) behaviorNum = '5';
                        else if (data.details.includes('睡觉')) behaviorNum = '6';
                    }
                    
                    updateBehaviorData(behaviorNum);
                } else {
                    // 尝试解析异常检测结果
                    try {
                        if (data.data && typeof data.data === 'string' && data.data.includes('reason')) {
                            const jsonMatch = data.data.match(/```json\s*({[^}]+})\s*```/);
                            if (jsonMatch && jsonMatch[1]) {
                                const result = JSON.parse(jsonMatch[1]);
                                if (result.reason) {
                                    // 匹配行为关键词
                                    let behaviorNum = '7'; // 默认其他
                                    if (result.reason.includes('专注工作')) behaviorNum = '1';
                                    else if (result.reason.includes('吃东西')) behaviorNum = '2';
                                    else if (result.reason.includes('喝水')) behaviorNum = '3';
                                    else if (result.reason.includes('喝饮料')) behaviorNum = '4';
                                    else if (result.reason.includes('玩手机')) behaviorNum = '5';
                                    else if (result.reason.includes('睡觉')) behaviorNum = '6';
                                    
                                    updateBehaviorData(behaviorNum);
                                }
                            }
                        }
                    } catch (e) {
                        console.error('解析异常检测结果错误:', e);
                    }
                }
            } catch (error) {
                // 尝试直接从文本中提取行为信息
                try {
                    const text = event.data;
                    if (typeof text === 'string') {
                        // 查找行为关键词
                        let behaviorNum = '7'; // 默认其他
                        if (text.includes('专注工作')) behaviorNum = '1';
                        else if (text.includes('吃东西')) behaviorNum = '2';
                        else if (text.includes('喝水')) behaviorNum = '3';
                        else if (text.includes('喝饮料')) behaviorNum = '4';
                        else if (text.includes('玩手机')) behaviorNum = '5';
                        else if (text.includes('睡觉')) behaviorNum = '6';
                        
                        updateBehaviorData(behaviorNum);
                    }
                } catch (e) {
                    console.error('处理文本数据错误:', e);
                }
            }
        };
    } catch (error) {
        console.error('WebSocket连接失败:', error);
        document.getElementById('status-text').textContent = '🔴 连接失败';
    }
}

// 更新行为数据
function updateBehaviorData(behaviorNum) {
    // 更新当前行为显示
    const behaviorDesc = behaviorMap[behaviorNum];
    document.getElementById('current-behavior').textContent = `当前行为: ${behaviorDesc}`;
    document.getElementById('current-behavior').style.color = behaviorColors[behaviorNum];
                       
    // 添加到历史记录
    behaviorHistory.push({
        behavior: behaviorNum,
        timestamp: new Date()
    });
     
    // 限制历史记录长度
    if (behaviorHistory.length > 30) {
        behaviorHistory.shift();
    }
     
    // 更新计数
    behaviorCounts[behaviorNum]++;
     
    // 更新统计显示
    document.getElementById('work-count').textContent = `${behaviorCounts["1"]} 次`;
    document.getElementById('eat-count').textContent = `${behaviorCounts["2"]} 次`;
    document.getElementById('water-count').textContent = `${behaviorCounts["3"]} 次`;
    document.getElementById('drink-count').textContent = `${behaviorCounts["4"]} 次`;
    document.getElementById('phone-count').textContent = `${behaviorCounts["5"]} 次`;
    document.getElementById('sleep-count').textContent = `${behaviorCounts["6"]} 次`;
    document.getElementById('other-count').textContent = `${behaviorCounts["7"]} 次`;
    
    // 更新图表
    updateCharts();
}

// 重置数据
function resetData() {
    behaviorHistory = [];
    behaviorCounts = {
        "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0
    };
    
    document.getElementById('work-count').textContent = '0 次';
    document.getElementById('eat-count').textContent = '0 次';
    document.getElementById('water-count').textContent = '0 次';
    document.getElementById('drink-count').textContent = '0 次';
    document.getElementById('phone-count').textContent = '0 次';
    document.getElementById('sleep-count').textContent = '0 次';
    document.getElementById('other-count').textContent = '0 次';
    
    document.getElementById('current-behavior').textContent = '当前行为: 等待检测...';
    document.getElementById('current-behavior').style.color = '';
    
    updateCharts();
    
    document.getElementById('timeline-no-data').style.display = 'block';
    document.getElementById('distribution-no-data').style.display = 'block';
     
    document.getElementById('status-text').textContent = "🟢 数据已重置";
}

// 初始化图表
function initCharts() {
    // 时间线图表
    const timelineCtx = document.getElementById('timeline-chart').getContext('2d');
    timelineChart = new Chart(timelineCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '行为',
                data: [],
                backgroundColor: function(context) {
                    const index = context.dataIndex;
                    const value = context.dataset.data[index];
                    return behaviorColors[value] || 'rgba(79, 209, 197, 1)';
                },
                borderColor: function(context) {
                    const index = context.dataIndex;
                    const value = context.dataset.data[index];
                    return behaviorColors[value] || 'rgba(79, 209, 197, 1)';
                },
                pointBorderColor: 'rgba(255, 255, 255, 0.8)',
                pointRadius: 5,
                tension: 0.2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    min: 0.5,
                    max: 7.5,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.7)',
                        callback: function(value) {
                            return behaviorMap[value] || '';
                        },
                        font: {
                            size: 11 // 减小字体大小
                        },
                        padding: 8 // 增加标签间距
                    }
                },
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.7)',
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const behavior = behaviorMap[context.raw] || '未知';
                            return `行为: ${behavior}`;
                        }
                    }
                }
            }
        }
    });
    
    // 分布图
    const distributionCtx = document.getElementById('distribution-chart').getContext('2d');
    distributionChart = new Chart(distributionCtx, {
        type: 'doughnut',
        data: {
            labels: Object.values(behaviorMap),
            datasets: [{
                data: Object.values(behaviorCounts),
                backgroundColor: Object.values(behaviorColors),
                borderColor: 'rgba(25, 41, 68, 0.8)',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.raw || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = total > 0 ? Math.round((value / total) * 100) : 0;
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            },
            cutout: '60%'
        }
    });
    
    // 显示"无数据"提示
    document.getElementById('timeline-no-data').style.display = 'block';
    document.getElementById('distribution-no-data').style.display = 'block';
}

// 更新图表时，清除演示数据
function updateBehaviorData(behaviorNum) {
    // 如果是第一个真实数据点，清除演示数据
    if (behaviorHistory.length === 0) {
        // 清除演示数据
        timelineChart.data.labels = [];
        timelineChart.data.datasets[0].data = [];
        
        // 重置分布图数据
        distributionChart.data.datasets[0].data = Object.values(behaviorCounts);
        distributionChart.update();
    }
    
    // ...现有的更新逻辑保持不变...
}

// 更新图表
function updateCharts() {
    if (!timelineChart || !distributionChart) return;
    
    // 更新时间线图表
    timelineChart.data.labels = behaviorHistory.map(item => {
        const time = item.timestamp;
        return `${time.getHours()}:${time.getMinutes().toString().padStart(2, '0')}:${time.getSeconds().toString().padStart(2, '0')}`;
    });
    timelineChart.data.datasets[0].data = behaviorHistory.map(item => item.behavior);
    timelineChart.update();
    
    // 更新分布图
    distributionChart.data.datasets[0].data = Object.values(behaviorCounts);
    distributionChart.update();
    
    // 更新"无数据"提示
    document.getElementById('timeline-no-data').style.display = behaviorHistory.length === 0 ? 'block' : 'none';
    document.getElementById('distribution-no-data').style.display = 
        Object.values(behaviorCounts).every(count => count === 0) ? 'block' : 'none';
}

// 添加按钮事件
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('refresh-stats-btn').addEventListener('click', resetData);
});

// 更新时间
function updateTime() {
    const now = new Date();
    const timeStr = `${now.getFullYear()}/` + 
                   `${(now.getMonth()+1).toString().padStart(2, '0')}/` + 
                   `${now.getDate().toString().padStart(2, '0')} ` + 
                   `${now.getHours().toString().padStart(2, '0')}:` + 
                   `${now.getMinutes().toString().padStart(2, '0')}:` + 
                   `${now.getSeconds().toString().padStart(2, '0')}`;
    const timeElement = document.getElementById('current-time');
    if (timeElement) {
        timeElement.textContent = timeStr;
    }
}

// 更新系统状态信息
function updateSystemStats() {
    // 随机生成内存和网络使用率
    const memUsage = Math.floor(Math.random() * 30) + 20; // 20-50%范围
    const netUsage = (Math.random() * 10 + 1).toFixed(1); // 1.0-11.0 Mbps范围
    
    // 更新DOM
    document.getElementById('memory-usage').textContent = `内存: ${memUsage}%`;
    document.getElementById('network-usage').textContent = `网络: ${netUsage} Mbps`;
}

// 页面加载时初始化
window.addEventListener('load', function() {
    initCharts();
    connectWebSocket();
    updateTime(); // 立即执行一次
    setInterval(updateTime, 1000);
    // 初始更新系统状态
    updateSystemStats();
    // 设置定时更新系统状态
    setInterval(updateSystemStats, 1000);
});

// 页面关闭时清理
window.addEventListener('beforeunload', function() {
    if (videoSocket) {
        videoSocket.close();
    }
});