<template>
  <div class="monitoring-page">
    <!-- <AppHeader /> -->

    <draggable 
      v-model="panelOrder" 
      class="container"
      item-key="id"
      :animation="200"
      handle=".panel-title"
      ghost-class="ghost-panel"
      chosen-class="chosen-panel"
      drag-class="drag-panel"
      @end="handleDragEnd"
    >
      <template #item="{element}">
        <div :class="['panel', getPanelClass(element.id)]" 
             :style="getPanelStyle(element.id)" 
             :ref="`panel${element.id}`">
          <CombinedMonitorPanel v-if="element.id === 1" :videoSrc="videoFeedUrl" :videoWs="videoWs" :deviceWs="deviceWs" />
          <AlertReplayPanel v-else-if="element.id === 5" :alerts="alerts" :wsConnection="alertsWs" />
          <QAPanel v-else-if="element.id === 4" />
          
          <div class="resize-handle resize-e" @mousedown="startResize($event, element.id, 'e')"></div>
          <div class="resize-handle resize-s" @mousedown="startResize($event, element.id, 's')"></div>
          <div class="resize-handle resize-w" @mousedown="startResize($event, element.id, 'w')"></div>
          <div class="resize-handle resize-n" @mousedown="startResize($event, element.id, 'n')"></div>
          <div class="resize-handle resize-se" @mousedown="startResize($event, element.id, 'se')"></div>
          <div class="resize-handle resize-sw" @mousedown="startResize($event, element.id, 'sw')"></div>
          <div class="resize-handle resize-ne" @mousedown="startResize($event, element.id, 'ne')"></div>
          <div class="resize-handle resize-nw" @mousedown="startResize($event, element.id, 'nw')"></div>
        </div>
      </template>
    </draggable>

    <!-- <StatusBar /> -->
  </div>
</template>

<script setup>
// 这里将添加页面的逻辑，例如 WebSocket 连接、数据获取等
import { onMounted, onUnmounted, ref, watch } from 'vue';
// import AppHeader from '../components/AppHeader.vue'; // 移除 Header 导入
// import StatusBar from '../components/AppFooter.vue'; // 移除 StatusBar 导入

import CombinedMonitorPanel from '../components/CombinedMonitorPanel.vue'; // 新的组合面板
import QAPanel from '../components/QAPanel.vue';
import AlertReplayPanel from '../components/AlertReplayPanel.vue'; // *** 导入新组件 ***
import draggable from 'vuedraggable';

const videoFeedUrl = ref(''); // 用于存储视频流 URL
let videoWs = ref(null); // 使用 ref 使得子组件可以响应式地接收 WebSocket 对象
const alerts = ref([]); // 存储预警信息列表
let alertsWs = ref(null); // 使用 ref
let deviceWs = ref(null); // 设备列表的WebSocket连接
const MAX_DISPLAY_ALERTS = 50; // 前端最多显示多少条预警

// 面板位置映射 (更新为新的网格区域)
const panelPositions = ref({
  1: 'left-top',    // 监控面板位于左上
  5: 'left-bottom', // 预警面板位于左下
  4: 'right'        // 问答面板位于右侧(占两行)
});

const panelOrder = ref([
  { id: 1 }, // 合并的监控面板
  { id: 5 }, // 预警面板
  { id: 4 }  // 智能问答面板
]);

// 更新面板大小状态 - 移除设备列表面板
const panelSizes = ref({
  1: { width: '100%', height: '339.13px' }, // 调整合并面板尺寸
  4: { width: '100%', height: '100%' },
  5: { width: '100%', height: '100%' }
});

const resizing = ref({
  active: false,
  panelId: null,
  direction: null,
  startX: 0,
  startY: 0,
  startWidth: 0,
  startHeight: 0,
  containerWidth: 0,
  initialColumns: '',
  currentRowTemplate: '60vh 40vh'
});

// 获取面板类名
function getPanelClass(panelId) {
  const classes = ['panel-custom'];
  
  // 添加对应的面板类型类名
  if (panelId === 1) classes.push('combined-monitor-panel');
  else if (panelId === 5) classes.push('alert-replay-panel');
  else if (panelId === 4) classes.push('qa-panel');
  
  // 添加网格区域类名
  const position = panelPositions.value[panelId];
  if (position) {
    // 根据布局模式动态分配区域
    if (layoutMode.value === 'vertical' && panelId === 4) {
      classes.push('grid-area-main');
    } else if (layoutMode.value === 'vertical') {
      // 其他面板在垂直模式下分配到sub区域
      const otherPanels = Object.keys(panelPositions.value).filter(id => id != 4);
      const idx = otherPanels.indexOf(panelId.toString());
      classes.push(idx === 0 ? 'grid-area-sub-1' : 'grid-area-sub-2');
    } else {
      // 水平模式直接使用position值
      classes.push(`grid-area-${position}`);
    }
  }
  
  return classes;
}

// 获取面板样式
function getPanelStyle(panelId) {
    // 检查 panelSizes 中是否存在该 panelId
    if (!panelSizes.value[panelId]) {
        console.warn(`Panel size for ID ${panelId} not found. Using default.`);
        return { width: '100%', height: '100%', position: 'relative' };
    }
    return {
        width: panelSizes.value[panelId].width,
        height: panelSizes.value[panelId].height,
        position: 'relative'
    };
}

// 开始调整大小
function startResize(event, panelId, direction) {
  event.preventDefault();
  event.stopPropagation();
  
  // 更准确地获取面板元素
  const panel = document.querySelector(`.panel[ref="panel${panelId}"]`) || 
                document.querySelector(`.panel.${panelId === 1 ? 'combined-monitor-panel' : panelId === 4 ? 'qa-panel' : 'alert-replay-panel'}`);
  
  if (!panel) {
    console.error(`找不到面板: ${panelId}`);
    return;
  }
  
  const rect = panel.getBoundingClientRect();
  
  // 获取container元素，提前准备好用于后续resize
  const container = document.querySelector('.container');
  const containerWidth = container.clientWidth;
  
  resizing.value = {
    active: true,
    panelId,
    direction,
    startX: event.clientX,
    startY: event.clientY,
    startWidth: rect.width,
    startHeight: rect.height,
    containerWidth, // 存储容器宽度
    initialColumns: window.getComputedStyle(container).gridTemplateColumns // 存储初始列配置
  };
  
  document.addEventListener('mousemove', handleResize);
  document.addEventListener('mouseup', stopResize);
  
  // 添加一个 class 到 panel 以禁用过渡效果
  panel.classList.add('resizing');
  
  // 禁用容器的hover效果和过渡
  container.classList.add('resizing-active');
}

// 处理调整大小
function handleResize(event) {
  if (!resizing.value.active) return;
  
  const { panelId, direction, startX, startY, startWidth, startHeight, containerWidth } = resizing.value;
  
  let newWidth = startWidth;
  let newHeight = startHeight;
  
  const deltaX = event.clientX - startX;
  const deltaY = event.clientY - startY;
  
  // 根据拖动方向计算新尺寸
  if (direction.includes('e')) {
    newWidth = startWidth + deltaX;
  } else if (direction.includes('w')) {
    newWidth = startWidth - deltaX;
    
    // 智能问答面板向左扩展时
    if (panelId === 4) {
      const container = document.querySelector('.container');
      if (container) {
        // 计算新的比例
        const qaColumnWidth = Math.max(200, newWidth);
        const qaColumnPercentage = (qaColumnWidth / containerWidth) * 100;
        
        // 如果问答面板宽度超过总宽度的75%，切换到垂直布局
        if (qaColumnPercentage > 75 && layoutMode.value === 'horizontal') {
          layoutMode.value = 'vertical';
          updateGridTemplate();
          return;
        } 
        // 如果宽度回到小于70%，恢复水平布局
        else if (qaColumnPercentage <= 70 && layoutMode.value === 'vertical') {
          // 在垂直模式下，宽度的变化可能不准确，所以我们基于拖动方向判断
          if (deltaX > 0) { // 向右拖动（缩小问答面板）
            layoutMode.value = 'horizontal';
            updateGridTemplate();
            
            // 重置宽度以适应新布局
            setTimeout(() => {
              const newQaPanel = document.querySelector('.qa-panel');
              if (newQaPanel) {
                const newRect = newQaPanel.getBoundingClientRect();
                panelSizes.value[4] = {
                  width: `${newRect.width}px`,
                  height: `${newRect.height}px`
                };
              }
            }, 50);
            return;
          }
        }
        
        // 在水平布局时调整列宽
        if (layoutMode.value === 'horizontal') {
          const leftColumnPercentage = Math.max(20, 100 - qaColumnPercentage - 5);
          container.style.gridTemplateColumns = `${leftColumnPercentage}% 40px ${qaColumnPercentage}%`;
        }
        
        return;
      }
    }
  }
  
  // 改进垂直布局下的高度调整逻辑，确保下方面板不被压缩
  if (direction.includes('s')) {
    newHeight = startHeight + deltaY;
    
    // 在垂直布局下，调整智能问答面板高度时，同时调整容器高度而不是压缩下方面板
    if (layoutMode.value === 'vertical' && panelId === 4) {
      const container = document.querySelector('.container');
      if (container) {
        // 获取下方面板的当前高度
        const subPanels = document.querySelectorAll('.grid-area-sub-1, .grid-area-sub-2');
        let subPanelHeight = 0;
        
        if (subPanels.length > 0) {
          // 使用第一个下方面板的高度作为基准
          const subPanelRect = subPanels[0].getBoundingClientRect();
          subPanelHeight = subPanelRect.height;
        } else {
          // 默认最小高度
          subPanelHeight = 200;
        }
        
        // 设置间距
        const gap = 30;
        
        // 计算QA面板的新高度，单位为像素
        const qaHeight = Math.max(300, newHeight);
        
        // 计算容器的总高度 = QA面板高度 + 间距 + 下方面板高度
        const containerHeightPx = qaHeight + gap + subPanelHeight;
        
        // 计算行模板，使用像素单位以确保精确定位
        const rowTemplate = `${qaHeight}px ${subPanelHeight}px`;
        
        // 保存当前行高
        resizing.value.currentRowTemplate = rowTemplate;
        
        // 设置容器高度
        container.style.height = `${containerHeightPx + gap}px`;
        container.style.gridTemplateRows = rowTemplate;
        container.style.gap = `${gap}px`;
        
        // 防止被约束在视口内
        container.style.minHeight = `${containerHeightPx + gap}px`;
        
        // 更新QA面板的尺寸
        panelSizes.value[4] = {
          width: '100%',
          height: `${qaHeight}px`
        };
        
        return;
      }
    }
  } else if (direction.includes('n')) {
    newHeight = startHeight - deltaY;
  }
  
  // 设置最小尺寸
  newWidth = Math.max(200, newWidth);
  newHeight = Math.max(150, newHeight);
  
  // 更新面板尺寸
  panelSizes.value[panelId] = {
    width: `${newWidth}px`,
    height: `${newHeight}px`
  };
}

// 停止调整大小
function stopResize() {
  if (!resizing.value.active) return;
  
  const container = document.querySelector('.container');
  if (container) {
    container.classList.remove('resizing-active');
    
    // 如果是垂直布局并且已经调整了行高，保存这个设置
    if (layoutMode.value === 'vertical' && resizing.value.currentRowTemplate) {
      // 保存当前行高到一个持久变量
      savedRowTemplate.value = resizing.value.currentRowTemplate;
      
      // 确保滚动正常显示全部内容
      if (container.offsetHeight > window.innerHeight) {
        document.body.style.overflowY = 'auto';
        document.documentElement.style.overflowY = 'auto';
      }
    }
  }
  
  const panels = document.querySelectorAll('.panel.resizing');
  panels.forEach(panel => panel.classList.remove('resizing'));
  
  resizing.value.active = false;
  document.removeEventListener('mousemove', handleResize);
  document.removeEventListener('mouseup', stopResize);
}

// 修改处理拖拽结束事件函数，确保保持面板大小
function handleDragEnd(event) {
  // 获取拖拽前和拖拽后的索引
  const { oldIndex, newIndex } = event;
  if (oldIndex === newIndex) return; // 没有变化
  
  // 获取当前的面板ID
  const draggedPanelId = panelOrder.value[newIndex].id;
  const targetPanelId = panelOrder.value[oldIndex].id;
  
  // 确定是左右互换还是上下互换
  const isQAPanelInvolved = draggedPanelId === 4 || targetPanelId === 4;
  
  // 保存所有面板的原始尺寸和样式
  const originalSizes = {};
  const originalStyles = {};
  panelOrder.value.forEach(panel => {
    const id = panel.id;
    // 保存尺寸
    originalSizes[id] = {...panelSizes.value[id]};
    
    // 保存元素当前样式，用于后续恢复
    const panelElement = document.querySelector(`.panel.${id === 1 ? 'combined-monitor-panel' : id === 4 ? 'qa-panel' : 'alert-replay-panel'}`);
    if (panelElement) {
      originalStyles[id] = {
        width: panelElement.style.width,
        height: panelElement.style.height,
        style: window.getComputedStyle(panelElement)
      };
    }
  });
  
  // 保存原始位置
  const originalPositions = {...panelPositions.value};
  
  // 保存是否是垂直布局
  const wasVertical = layoutMode.value === 'vertical';
  
  // 如果涉及到智能问答面板(ID=4)，进行左右互换逻辑
  if (isQAPanelInvolved) {
    // 获取所有面板ID
    const panelIds = panelOrder.value.map(panel => panel.id);
    const otherPanelIds = panelIds.filter(id => id !== 4);
    
    // 记录智能问答面板当前位置
    const qaCurrentPosition = panelPositions.value[4];
    const isQAOnLeft = qaCurrentPosition === 'left';
    
    // 根据当前位置重新设置网格区域
    if (isQAOnLeft) {
      // QA面板在左侧，需要移动到右侧
      panelPositions.value[4] = 'right';
      panelPositions.value[otherPanelIds[0]] = 'left-top';
      panelPositions.value[otherPanelIds[1]] = 'left-bottom';
    } else {
      // QA面板在右侧，需要移动到左侧
      panelPositions.value[4] = 'left';
      panelPositions.value[otherPanelIds[0]] = 'right-top';
      panelPositions.value[otherPanelIds[1]] = 'right-bottom';
    }
    
    // 使用水平布局
    layoutMode.value = 'horizontal';
  } else {
    // 仅左侧两个面板之间的上下互换
    const temp = panelPositions.value[draggedPanelId];
    panelPositions.value[draggedPanelId] = panelPositions.value[targetPanelId];
    panelPositions.value[targetPanelId] = temp;
  }
  
  // 更新网格模板
  updateGridTemplate();
  
  // 在布局更新后延迟恢复原始尺寸，确保网格布局已经应用
  setTimeout(() => {
    // 遍历并应用正确的尺寸
    panelOrder.value.forEach(panel => {
      const id = panel.id;
      
      // 智能问答模块(ID=4)特殊处理 - 无论如何都保持原始尺寸
      if (id === 4) {
        // 保持原始尺寸
        const qaOriginalSize = originalSizes[id];
        
        // 从垂直布局切换到水平布局时调整高度
        if (wasVertical) {
          qaOriginalSize.height = '100%';
        }
        
        // 更新尺寸
        panelSizes.value[id] = {...qaOriginalSize};
      } else {
        // 其他面板处理：如果位置类型改变，调整尺寸以适应新容器
        const wasOnRight = originalPositions[id].includes('right');
        const isNowOnRight = panelPositions.value[id].includes('right');
        
        if (wasOnRight !== isNowOnRight) {
          // 位置类型变化，使用适应新位置的尺寸
          panelSizes.value[id] = { width: '100%', height: '100%' };
        } else {
          // 保持原始尺寸
          panelSizes.value[id] = {...originalSizes[id]};
        }
      }
    });
    
    // 调整列宽度比例
    const container = document.querySelector('.container');
    if (container && layoutMode.value === 'horizontal') {
      // 获取QA面板当前位置和尺寸
      const qaPanel = document.querySelector('.panel.qa-panel');
      if (qaPanel) {
        const qaWidth = qaPanel.offsetWidth;
        const containerWidth = container.offsetWidth;
        const gapWidth = 40; // 中间间隔宽度
        
        // 计算QA面板宽度百分比
        const qaWidthPercentage = (qaWidth / containerWidth) * 100;
        const gapWidthPercentage = (gapWidth / containerWidth) * 100;
        const otherWidthPercentage = 100 - qaWidthPercentage - gapWidthPercentage;
        
        // 根据QA面板位置设置列宽
        if (panelPositions.value[4] === 'right') {
          container.style.gridTemplateColumns = `${otherWidthPercentage}% ${gapWidth}px ${qaWidthPercentage}%`;
        } else if (panelPositions.value[4] === 'left') {
          container.style.gridTemplateColumns = `${qaWidthPercentage}% ${gapWidth}px ${otherWidthPercentage}%`;
        }
      }
    }
  }, 100);
}

// 添加一个新的响应式变量跟踪布局模式
const layoutMode = ref('horizontal'); // 'horizontal' 或 'vertical'

// 添加一个新的响应式变量保存行高模板
const savedRowTemplate = ref('60vh 40vh'); // 默认值

// 修改网格模板函数，支持保持智能问答模块大小
function updateGridTemplate() {
  const container = document.querySelector('.container');
  if (!container) return;
  
  if (layoutMode.value === 'horizontal') {
    // 获取智能问答面板的位置
    const qaPosition = panelPositions.value[4];
    const isQAOnRight = qaPosition === 'right';
    const isQAOnLeft = qaPosition === 'left';
    
    // 设置网格区域
    container.style.gridTemplateAreas = `
      "left-top    .    right-top"
      "left-bottom .    right-bottom"
    `;
    
    // 初始列宽配置
    let leftWidth = '2fr';
    let gapWidth = '40px';
    let rightWidth = '1fr';
    
    // 查找智能问答面板元素，获取其当前宽度
    const qaPanel = document.querySelector('.panel.qa-panel');
    if (qaPanel) {
      const qaStyle = window.getComputedStyle(qaPanel);
      const qaWidth = parseFloat(qaStyle.width);
      
      if (!isNaN(qaWidth) && qaWidth > 0) {
        const containerWidth = container.clientWidth;
        const qaPercentage = Math.min(70, Math.max(30, (qaWidth / containerWidth) * 100));
        const gapPercentage = (40 / containerWidth) * 100;
        const otherPercentage = 100 - qaPercentage - gapPercentage;
        
        if (isQAOnRight) {
          leftWidth = `${otherPercentage}%`;
          rightWidth = `${qaPercentage}%`;
        } else if (isQAOnLeft) {
          leftWidth = `${qaPercentage}%`;
          rightWidth = `${otherPercentage}%`;
        }
      }
    }
    
    // 应用列宽
    container.style.gridTemplateColumns = `${leftWidth} ${gapWidth} ${rightWidth}`;
    
    // 行高设置
    container.style.gridTemplateRows = '40vh 40vh';
    container.style.height = '80vh';
    container.style.gap = '20px';
    container.style.minHeight = '600px';
    
  } else {
    // 垂直布局逻辑保持不变
    container.style.gridTemplateAreas = `
      "main main main"
      "sub-1 . sub-2"
    `;
    container.style.gridTemplateColumns = '1fr 40px 1fr';
    
    // 获取下方面板的默认高度 (像素单位)
    const subPanelDefaultHeight = 300;
    
    // 计算QA面板的初始高度 (像素单位)
    const qaInitialHeight = 500;
    
    // 设置间距
    const gap = 30;
    
    // 使用保存的行高或计算默认行高
    if (savedRowTemplate.value && !savedRowTemplate.value.includes('undefined')) {
      container.style.gridTemplateRows = savedRowTemplate.value;
    } else {
      // 为新的垂直布局设置默认行高 (像素单位)
      container.style.gridTemplateRows = `${qaInitialHeight}px ${subPanelDefaultHeight}px`;
      savedRowTemplate.value = `${qaInitialHeight}px ${subPanelDefaultHeight}px`;
    }
    
    // 计算初始容器高度
    const containerInitialHeight = qaInitialHeight + gap + subPanelDefaultHeight + gap;
    
    // 设置容器高度，确保足够高
    container.style.height = `${containerInitialHeight}px`;
    container.style.minHeight = `${containerInitialHeight}px`;
    
    // 增加垂直间距，防止重叠
    container.style.gap = `${gap}px`;
  }
  
  // 添加过渡效果
  container.style.transition = 'grid-template-rows 0.3s ease, grid-template-columns 0.3s ease, height 0.3s ease, gap 0.3s ease';
}

// 初始化视频 WebSocket
const initVideoWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/video_feed`;

  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log('视频 WebSocket 已连接');
    videoWs.value = ws; // 将实例赋给 ref
  };

  ws.onmessage = (event) => {
    if (event.data instanceof Blob) {
      if (videoFeedUrl.value && videoFeedUrl.value.startsWith('blob:')) {
        URL.revokeObjectURL(videoFeedUrl.value);
      }
      videoFeedUrl.value = URL.createObjectURL(event.data);
    }
  };

  ws.onerror = (error) => {
    console.error('视频 WebSocket 错误:', error);
    videoWs.value = null; // 连接错误时清空 ref
  };

  ws.onclose = () => {
    console.log('视频 WebSocket 已关闭');
    videoWs.value = null; // 关闭时清空 ref
    if (videoFeedUrl.value && videoFeedUrl.value.startsWith('blob:')) {
      URL.revokeObjectURL(videoFeedUrl.value);
      videoFeedUrl.value = '';
    }
    // 可以在这里添加重连逻辑
  };
};

// 关闭视频 WebSocket
const closeVideoWebSocket = () => {
  if (videoWs.value) {
    videoWs.value.close();
    videoWs.value = null;
  }
  if (videoFeedUrl.value && videoFeedUrl.value.startsWith('blob:')) {
    URL.revokeObjectURL(videoFeedUrl.value);
    videoFeedUrl.value = '';
  }
};

// 初始化预警 WebSocket
const initAlertsWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/alerts`;

  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log('预警 WebSocket 已连接');
    alertsWs.value = ws; // 将实例赋给 ref
  };

  ws.onmessage = (event) => {
    try {
      const alertData = JSON.parse(event.data);
      if (alertData.type === 'alert') {
        console.log('收到新预警:', alertData);
        alerts.value.unshift(alertData); // 最新的放前面
        if (alerts.value.length > MAX_DISPLAY_ALERTS) {
          alerts.value.pop();
        }
      } else if (alertData.type === 'recent_alerts') {
         // 处理首次连接时收到的历史预警
         console.log('收到历史预警:', alertData.data.length, '条');
         // 假设 data 是按时间顺序（旧->新）发送的，所以需要反转
         alerts.value = [...alertData.data.reverse(), ...alerts.value];
         // 去重和限制长度可以在这里做，或者信任后端的逻辑
         if (alerts.value.length > MAX_DISPLAY_ALERTS) {
             alerts.value = alerts.value.slice(0, MAX_DISPLAY_ALERTS);
         }
      }
    } catch (error) {
      console.error('处理预警消息失败:', error);
    }
  };

  ws.onerror = (error) => {
    console.error('预警 WebSocket 错误:', error);
    alertsWs.value = null; // 连接错误时清空 ref
  };

  ws.onclose = () => {
    console.log('预警 WebSocket 已关闭');
    alertsWs.value = null; // 关闭时清空 ref
    // 可以在这里添加重连逻辑
  };
};

// 关闭预警 WebSocket
const closeAlertsWebSocket = () => {
  if (alertsWs.value) {
    alertsWs.value.close();
    alertsWs.value = null;
  }
};

onMounted(() => {
  console.log('主监控页面已挂载');
  initVideoWebSocket();
  initAlertsWebSocket();
  
  // 初始化网格布局
  updateGridTemplate();
  
  // 添加视口大小变化监听
  window.addEventListener('resize', checkScrollNeeded);
  
  // 检查初始状态
  setTimeout(checkScrollNeeded, 300);
});

onUnmounted(() => {
  console.log('主监控页面已卸载');
  closeVideoWebSocket();
  closeAlertsWebSocket();
  document.removeEventListener('mousemove', handleResize);
  document.removeEventListener('mouseup', stopResize);
  window.removeEventListener('resize', checkScrollNeeded);
});

// 检查是否需要滚动
function checkScrollNeeded() {
  const container = document.querySelector('.container');
  if (!container) return;
  
  // 检查是否垂直布局
  if (layoutMode.value === 'vertical') {
    const containerHeight = container.offsetHeight;
    const viewportHeight = window.innerHeight;
    
    if (containerHeight > viewportHeight * 0.9) {
      container.classList.add('vertical-scroll');
      // 确保整个页面可以滚动
      document.documentElement.style.overflow = 'auto';
    } else {
      container.classList.remove('vertical-scroll');
    }
  } else {
    container.classList.remove('vertical-scroll');
  }
}

// 修改布局模式变化时的处理
watch(layoutMode, (newMode) => {
  updateGridTemplate();
  // 布局变化后，检查滚动需求
  setTimeout(checkScrollNeeded, 300);
});
</script>

<style scoped>
.monitoring-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: var(--dark-bg);
  width: 100vw;
  overflow-x: hidden;
  overflow-y: auto; /* 允许垂直滚动 */
  scroll-behavior: smooth; /* 平滑滚动 */
  /* 移除垂直居中，让内容从顶部开始 */
  /* justify-content: center; */
  /* 确保没有边距和内边距导致的空白 */
  margin: 0;
  padding: 0;
  --vertical-panel-gap: 30px; /* 定义间距变量方便使用 */
}

.container {
  /* 恢复grid布局 */
  display: grid;
  /* 宽度缩减并居中 */
  width: 90%;
  max-width: 1600px;
  margin: 0 auto;
  /* 比例保持不变，但调整格式添加空列作为间距 */
  grid-template-columns: 2fr 40px 1fr;
  /* 调整高度，确保一屏内完全显示 */
  grid-template-rows: 40vh 40vh;
  gap: 20px;
  grid-template-areas:
    "monitor .     qa"
    "alert   .     qa";
  /* 内边距适当缩减 */
  padding: 10px 0;
  box-sizing: border-box;
  transition: grid-template-columns 0.1s ease; /* 添加过渡效果 */
  transition: grid-template-rows 0.3s ease, grid-template-columns 0.3s ease, height 0.3s ease, gap 0.3s ease;
}

/* 定义网格区域 */
.grid-area-monitor { grid-area: monitor; }
.grid-area-alert { grid-area: alert; }
.grid-area-qa { grid-area: qa; }

/* 网格区域动态分配 - 修改为更灵活的布局 */
/* 水平布局 (左右两栏) */
.grid-area-left-top { grid-area: left-top; }
.grid-area-left-bottom { grid-area: left-bottom; }
.grid-area-right-top { grid-area: right-top; }
.grid-area-right-bottom { grid-area: right-bottom; }
.grid-area-left { grid-area: left-top / left-top / left-bottom / left-top; } /* 占据左侧两行 */
.grid-area-right { grid-area: right-top / right-top / right-bottom / right-top; } /* 占据右侧两行 */

/* 垂直布局 (上下两栏) */
.grid-area-main { grid-area: main; }
.grid-area-sub-1 { grid-area: sub-1; }
.grid-area-sub-2 { grid-area: sub-2; }

/* 响应式调整 */
@media (max-width: 900px) {
  .container {
    width: 95%;
    grid-template-columns: 1fr;
    grid-template-rows: auto auto auto;
    grid-template-areas:
      "monitor"
      "alert"
      "qa";
    gap: 15px;
  }
  
  .panel {
    max-height: 50vh;
  }
}

.panel {
  background-color: rgba(15, 23, 42, 0.75); /* Slightly less transparent */
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-radius: 6px; /* Slightly smaller radius */
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(79, 209, 197, 0.15);
  padding: 15px;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden; /* 保持隐藏，手柄使用 z-index */
  height: 100%; /* 默认占满单元格 */
  width: 100%; /* 默认占满单元格 */
  transition: transform 0.25s ease, box-shadow 0.25s ease, width 0.3s ease, height 0.3s ease;
  border: 1px solid rgba(79, 209, 197, 0.1); /* Subtler border */
  min-width: 200px;
  min-height: 150px;
  box-sizing: border-box; /* 确保边框和内边距不会增加宽高 */
  margin-bottom: 0; /* 移除可能存在的底部边距 */
}

.panel:hover {
  transform: translateY(-5px) scale(1.01); /* Subtler hover effect */
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3), 0 0 15px rgba(79, 209, 197, 0.3);
  border-color: rgba(79, 209, 197, 0.4);
  z-index: 10; /* Bring panel to front on hover */
}

.panel-title {
  font-size: 1.1rem;
  font-weight: 600;
  margin: -15px -15px 15px -15px; /* Extend to edges */
  padding: 10px 15px; /* Adjust padding */
  color: var(--primary, #4fd1c5);
  border-bottom: 1px solid rgba(79, 209, 197, 0.3); /* Lighter border */
  display: flex;
  align-items: center;
  letter-spacing: 1px;
  text-shadow: 0 0 5px rgba(79, 209, 197, 0.3);
  cursor: move;
  user-select: none;
  background-color: rgba(10, 25, 47, 0.5); /* Add slight background to title */
  border-radius: 6px 6px 0 0; /* Match panel radius */
  flex-shrink: 0; /* Prevent shrinking */
}

.panel-title::before {
  content: "⋮⋮";
  margin-right: 10px; /* More space */
  opacity: 0.6;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5); /* Make handle more visible */
}
.panel-title:hover::before {
  opacity: 1;
  color: rgba(255, 255, 255, 0.8);
}

/* Top glow effect */
.panel::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 3px;
  background: linear-gradient(90deg, transparent, rgba(79, 209, 197, 0.6), transparent);
  opacity: 0.6; /* Slightly dimmer */
  z-index: 3;
}
/* Specific glow colors remain */
.combined-monitor-panel::before { background: linear-gradient(90deg, transparent, rgba(79, 209, 197, 0.6), transparent); }
.qa-panel::before { background: linear-gradient(90deg, transparent, rgba(128, 90, 213, 0.6), transparent); }
/* New combined panel glow */
.alert-replay-panel::before { background: linear-gradient(90deg, transparent, rgba(255, 165, 0, 0.6), transparent); } /* Example: Orange glow */

/* Panel content areas */
.panel > div:not(.panel-title):not(.resize-handle) {
  flex-grow: 1; /* Allow content div to grow */
  overflow: hidden; /* Let children handle scroll */
  border-radius: 0 0 6px 6px; /* Radius for content area below title */
}

/* Adjust specific panel spans/borders if needed (grid-area handles layout) */
.combined-monitor-panel { border-color: rgba(79, 209, 197, 0.2); }
.alert-replay-panel { border-color: rgba(255, 165, 0, 0.2); } /* Orange border */
.qa-panel { border-color: rgba(128, 90, 213, 0.2); }

/* Background grid and scanline remain the same */
.monitoring-page::before {
  content: "";
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: 
      linear-gradient(rgba(10, 25, 47, 0.8), rgba(10, 25, 47, 0.8)),
      repeating-linear-gradient(transparent, transparent 50px, rgba(79, 209, 197, 0.1) 50px, rgba(79, 209, 197, 0.1) 51px),
      repeating-linear-gradient(90deg, transparent, transparent 50px, rgba(79, 209, 197, 0.1) 50px, rgba(79, 209, 197, 0.1) 51px);
  z-index: -1;
  opacity: 0.5;
  pointer-events: none;
}
.monitoring-page::after {
  content: "";
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 3px;
  background: linear-gradient(90deg, transparent, var(--cyber-neon), transparent);
  box-shadow: 0 0 15px 2px var(--cyber-neon);
  z-index: 999;
  animation: scanline 8s linear infinite;
  opacity: 0.5;
}

@keyframes scanline {
  0% { top: -10px; }
  100% { top: 100vh; }
}

/* Draggable styles remain the same */
.ghost-panel { 
  opacity: 0.5; 
  background: rgba(0, 0, 0, 0.2) !important;
  transform: scale(0.95);
  border: 2px dashed rgba(79, 209, 197, 0.5) !important;
}

.chosen-panel { 
  box-shadow: 0 0 30px rgba(79, 209, 197, 0.8) !important; 
  z-index: 20;
  opacity: 0.9;
}

.drag-panel { 
  transform: rotate(2deg) scale(1.02); 
  z-index: 30;
  cursor: grabbing !important;
}

/* Resize Handle Styles */
.resize-handle {
  position: absolute;
  background-color: transparent;
  z-index: 20; /* 提高z-index确保在面板内容之上 */
  transition: background-color 0.1s ease;
}

.panel:hover .resize-handle {
   /* Show handles only on panel hover */
   /* background-color: rgba(79, 209, 197, 0.1); */ /* Very subtle */
}

.resize-handle:hover {
  background-color: rgba(79, 209, 197, 0.4); /* Highlight on handle hover */
}

/* Directions */
.resize-e { top: 0; right: -2px; width: 8px; height: 100%; cursor: e-resize; }
.resize-w { top: 0; left: -5px; width: 10px; height: 100%; cursor: w-resize; }
.resize-s { bottom: -2px; left: 0; width: 100%; height: 8px; cursor: s-resize; }
.resize-n { top: -2px; left: 0; width: 100%; height: 8px; cursor: n-resize; }

/* Corners */
.resize-se { bottom: -2px; right: -2px; width: 12px; height: 12px; cursor: se-resize; border-radius: 0 0 4px 0; }
.resize-sw { bottom: -2px; left: -2px; width: 12px; height: 12px; cursor: sw-resize; border-radius: 0 0 0 4px; }
.resize-ne { top: -2px; right: -2px; width: 12px; height: 12px; cursor: ne-resize; border-radius: 0 4px 0 0; }
.resize-nw { top: -2px; left: -2px; width: 12px; height: 12px; cursor: nw-resize; border-radius: 4px 0 0 0; }

/* Resizing state */
.panel.resizing {
  transition: none !important;
  user-select: none;
  box-shadow: 0 0 0 2px rgba(79, 209, 197, 0.5) !important;
}

/* Global disable pointer events on panel content during resize */
.panel.resizing > *:not(.resize-handle) {
  pointer-events: none;
}

/* 修改AppHeader组件相关样式，如果存在的话 */
:deep(.header) {
  margin: 0;
  padding: 0;
}

/* 调整resize handle的触摸区域和可见性 */
.qa-panel:hover .resize-w {
  background-color: rgba(128, 90, 213, 0.2); /* 增加可见性 */
}

/* 当调整大小时禁用过渡效果 */
.container.resizing-active {
  transition: none !important;
}

/* 当调整大小时禁用面板的hover效果 */
.container.resizing-active .panel:hover {
  transform: none;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(79, 209, 197, 0.15);
  border-color: rgba(79, 209, 197, 0.1);
}

/* 突出显示左侧调整手柄 */
.resize-w {
  top: 0;
  left: -5px;
  width: 10px;
  height: 100%;
  cursor: w-resize;
}

.qa-panel .resize-w {
  background-color: rgba(128, 90, 213, 0.1); /* 始终显示一点颜色 */
}

.qa-panel .resize-w:hover,
.qa-panel .resize-w:active {
  background-color: rgba(128, 90, 213, 0.4); /* 悬停或激活状态更明显 */
}

/* 修改垂直布局下的间距 */
.container {
  /* 其他样式保持不变 */
  transition: grid-template-rows 0.3s ease, grid-template-columns 0.3s ease, height 0.3s ease, gap 0.3s ease;
}

/* 垂直布局时为下方面板添加上边距 */
.grid-area-sub-1, 
.grid-area-sub-2 {
  margin-top: 10px; /* 额外增加上边距 */
}

/* 确保面板内容不会溢出 */
.panel {
  /* 其他样式保持不变 */
  box-sizing: border-box; /* 确保边框和内边距不会增加宽高 */
  margin-bottom: 0; /* 移除可能存在的底部边距 */
}

/* 改进垂直模式下的视觉分隔 */
.monitoring-page {
  /* 其他样式保持不变 */
  --vertical-panel-gap: 30px; /* 定义间距变量方便使用 */
}

/* 增加拖拽时的视觉反馈 */
.qa-panel.chosen-panel {
  box-shadow: 0 0 30px rgba(128, 90, 213, 0.8) !important;
  border-color: rgba(128, 90, 213, 0.4) !important;
}

/* 确保QA面板在水平布局中显示正确 */
.grid-area-left.qa-panel,
.grid-area-right.qa-panel {
  height: 100% !important; /* 确保高度占满网格区域 */
}

/* 调整拖拽过程中的面板样式 */
.container.resizing-active .panel.qa-panel {
  transition: none !important; /* 拖拽时禁用过渡 */
}

/* 在水平布局中增强QA面板边界视觉效果 */
.panel.qa-panel {
  z-index: 5; /* 确保QA面板在其他面板之上 */
}

/* 改进QA面板在左侧时的样式 */
.grid-area-left.qa-panel {
  z-index: 6; /* 提高层级，确保可见 */
  height: 100% !important;
}

/* 强化拖动状态的视觉反馈 */
.qa-panel.chosen-panel {
  box-shadow: 0 0 30px rgba(128, 90, 213, 0.8) !important;
  border-color: rgba(128, 90, 213, 0.4) !important;
  opacity: 0.95 !important;
}

/* 添加拖动指示器，使拖拽方向更明显 */
.panel-title::after {
  content: "";
  display: inline-block;
  width: 6px;
  height: 10px;
  margin-left: auto;
  background-color: rgba(255, 255, 255, 0.2);
  clip-path: polygon(0% 0%, 100% 50%, 0% 100%);
  opacity: 0;
  transition: opacity 0.2s ease;
}

.panel-title:hover::after {
  opacity: 0.6;
}

/* 增强水平布局下的面板间隔 */
.container {
  /* 其他样式保持不变 */
  gap: 20px !important; /* 确保间距始终存在 */
}
</style> 