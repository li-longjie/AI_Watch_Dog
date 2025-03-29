// 行为分析页面脚本
document.addEventListener('DOMContentLoaded', function() {
    // 加载行为数据
    loadBehaviorData();
    
    // 设置按钮点击事件
    document.getElementById('apply-filters').addEventListener('click', function() {
        loadBehaviorData();
    });
    
    // 更新系统状态
    updateSystemStatus();
    
    // 返回主页按钮
    document.getElementById('behaviorAnalysisBtn').addEventListener('click', function() {
        window.location.href = '/';
    });
});

// 加载行为数据
async function loadBehaviorData() {
    try {
        const response = await fetch('/api/behavior-data');
        const data = await response.json();
        
        if (data.status === 'success') {
            // 更新统计信息
            document.getElementById('total-behaviors').textContent = data.data.statistics.total_behaviors;
            document.getElementById('unique-behaviors').textContent = data.data.statistics.unique_behaviors;
            document.getElementById('most-frequent').textContent = data.data.statistics.most_frequent;
            
            // 更新表格
            updateBehaviorTable(data.data.behaviors);
            
            // 生成图表
            generateBehaviorChart(data.data.behaviors);
        }
    } catch (error) {
        console.error('获取行为数据失败:', error);
    }
}

// 更新行为表格
function updateBehaviorTable(behaviors) {
    const tbody = document.querySelector('#behavior-table tbody');
    tbody.innerHTML = '';
    
    behaviors.forEach(behavior => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${behavior.id}</td>
            <td>${behavior.type}</td>
            <td>${behavior.count}</td>
            <td>${behavior.timestamp}</td>
            <td><button class="view-btn">查看详情</button></td>
        `;
        tbody.appendChild(row);
    });
    
    // 为每个"查看详情"按钮添加点击事件
    document.querySelectorAll('.view-btn').forEach((btn, index) => {
        btn.addEventListener('click', function() {
            alert(`查看行为ID: ${behaviors[index].id} 的详情`);
            // 这里可以实现打开详情模态框或跳转到详情页的逻辑
        });
    });
}

// 生成行为趋势图表
function generateBehaviorChart(behaviors) {
    const chartContainer = document.getElementById('behavior-chart');
    chartContainer.innerHTML = '';
    
    // 这里应该使用图表库如Chart.js或Echarts
    // 下面是简单的示例HTML表示
    chartContainer.innerHTML = `
        <div style="width:100%; height:100%; display:flex; justify-content:center; align-items:center; color:#8892b0;">
            <div>
                <p style="text-align:center; margin-bottom:15px;">行为趋势图 (示例)</p>
                <div style="display:flex; align-items:flex-end; height:200px; gap:20px; justify-content:space-around;">
                    <div style="display:flex; flex-direction:column; align-items:center;">
                        <div style="width:30px; background-color:#0e86ca; height:${behaviors[0].count * 40}px;"></div>
                        <p style="margin-top:5px;">${behaviors[0].type}</p>
                    </div>
                    <div style="display:flex; flex-direction:column; align-items:center;">
                        <div style="width:30px; background-color:#0e86ca; height:${behaviors[1].count * 40}px;"></div>
                        <p style="margin-top:5px;">${behaviors[1].type}</p>
                    </div>
                    <div style="display:flex; flex-direction:column; align-items:center;">
                        <div style="width:30px; background-color:#0e86ca; height:${behaviors[2].count * 40}px;"></div>
                        <p style="margin-top:5px;">${behaviors[2].type}</p>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// 更新系统状态信息
function updateSystemStatus() {
    // 模拟系统状态更新
    setInterval(() => {
        document.getElementById('cpu-usage').textContent = `${Math.floor(Math.random() * 30) + 10}%`;
        document.getElementById('mem-usage').textContent = `${Math.floor(Math.random() * 30) + 10}%`;
        document.getElementById('net-usage').textContent = `${(Math.random() * 2).toFixed(1)} Mbps`;
        
        const now = new Date();
        const timeStr = `${now.getFullYear()}/${padZero(now.getMonth() + 1)}/${padZero(now.getDate())} ${padZero(now.getHours())}:${padZero(now.getMinutes())}:${padZero(now.getSeconds())}`;
        document.getElementById('server-time').textContent = timeStr;
    }, 1000);
}

// 补零函数
function padZero(num) {
    return num.toString().padStart(2, '0');
} 