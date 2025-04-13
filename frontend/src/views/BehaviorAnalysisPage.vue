<template>
  <div class="behavior-analysis-page">
    <!-- <AppHeader /> -->

    <div class="content-container">
      <div class="loading-message" v-if="!wsConnected && initialLoading">
        <div class="cyber-spinner"></div>
        <p>连接实时分析服务中...</p>
      </div>
      <div class="loading-message" v-if="wsConnected && behaviorData.alerts.length === 0 && !initialLoading">
         <div class="cyber-spinner"></div>
         <p>等待实时行为数据...</p>
      </div>


      <draggable
        v-if="wsConnected || !initialLoading"
        v-model="panelOrder"
        class="analysis-container"
        item-key="id"
        :animation="200"
        handle=".panel-title"
        ghost-class="ghost-panel"
        chosen-class="chosen-panel"
        drag-class="drag-panel"
        tag="div"
        @end="savePanelOrder"
      >
        <template #item="{ element }">
          <component
            :is="getComponentName(element.id)"
            :style="getPanelStyle(element.id)"
            :class="['panel', 'cyber-panel', getPanelClass(element.id)]"
            :data-id="element.id"
            :ref="(el) => (panelRefs[element.id] = el)"
            v-bind="getComponentProps(element.id)"
            @start-resize="
              (event, direction) => startResize(event, element.id, direction)
            "
            class="draggable-item"
          />
        </template>
      </draggable>
       <div class="error-message" v-if="wsError">
         <p>连接实时分析服务失败，请检查后端服务是否运行。</p>
         <button @click="connectAlertWebSocket" class="retry-button">重试连接</button>
       </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, shallowRef, computed, watch } from "vue";
import draggable from "vuedraggable";

// Import the new components
import BAActivityHeatmap from "../components/BAActivityHeatmap.vue";
import BABehaviorList from "../components/BABehaviorList.vue";
import BABehaviorChart from "../components/BABehaviorChart.vue";
import BARealTimeMonitoring from "../components/BARealTimeMonitoring.vue";

const initialLoading = ref(true);
const MAX_ALERTS_DISPLAY = 200;

// New reactive state for behavior data
const behaviorData = ref({
  alerts: [],
  aggregated: {
    types: [],
    mostFrequentType: "无",
  },
  timeSeries: {
    labels: [],
    datasets: []
  },
  heatmapData: []
});

let alertWs = null;
const wsConnected = ref(false);
const wsError = ref(false);

// Function to extract behavior type from alert content
function extractBehaviorType(content) {
  if (!content) return "未知";
  if (content.includes("网络请求错误")) return "未知";
  if (content.includes("结束")) {
      const match = content.match(/^(.*?)结束/);
      return match ? match[1].trim() : "未知";
  } else if (content.includes("开始")) {
      const match = content.match(/^(.*?)开始/);
      return match ? match[1].trim() : "未知";
  }
  return content.split(" ")[0];
}

// Helper to get minute string (e.g., "23:41") from timestamp
function getMinuteString(timestamp) {
    try {
        const dateStr = timestamp.includes("T") ? timestamp : timestamp.replace(" ", "T") + 'Z';
        const date = new Date(dateStr);
        if (isNaN(date)) return null;
        return `${date.getHours().toString().padStart(2, "0")}:${date.getMinutes().toString().padStart(2, "0")}`;
    } catch {
        return null;
    }
}

// Map behavior types to colors (consistent with pie chart)
const behaviorColors = {
    专注工作学习: "#22d3a7",
    专注工作: "#22d3a7",
    吃东西: "#f97316",
    喝水: "#22c55e",
    玩手机: "#ef4444",
    睡觉: "#a855f7",
    default: "#9ca3af", // Slightly different default grey
};
function getBehaviorColor(type) {
    return behaviorColors[type] || behaviorColors.default;
}

// Function to get Hour (0-23) from timestamp
function getHourFromTimestamp(timestamp) {
    try {
        const dateStr = timestamp.includes("T") ? timestamp : timestamp.replace(" ", "T") + 'Z';
        const date = new Date(dateStr);
        if (isNaN(date)) return null;
        return date.getHours();
    } catch {
        return null;
    }
}

// Function to update *both* aggregated and time series data
function processAlertsAndUpdateData() {
    const typeCounts = {};
    const types = new Set();
    const timeSeriesAgg = {};
    const timeLabels = new Set();
    const hourlyCounts = {};

    const now = new Date();
    const twentyFourHoursAgo = now.getTime() - (24 * 60 * 60 * 1000);

    [...behaviorData.value.alerts].reverse().forEach(alert => {
        const type = extractBehaviorType(alert.content);
        const minuteStr = getMinuteString(alert.timestamp);
        const hour = getHourFromTimestamp(alert.timestamp);
        let alertTime = null;
         try {
             const dateStr = alert.timestamp.includes("T") ? alert.timestamp : alert.timestamp.replace(" ", "T") + 'Z';
             alertTime = new Date(dateStr);
         } catch {}

        if (type !== "未知") {
             typeCounts[type] = (typeCounts[type] || 0) + 1;
             types.add(type);
        }

        if (minuteStr && type !== "未知") {
            timeLabels.add(minuteStr);
            if (!timeSeriesAgg[minuteStr]) {
                timeSeriesAgg[minuteStr] = { total: 0 };
            }
            if (!timeSeriesAgg[minuteStr][type]) {
                 timeSeriesAgg[minuteStr][type] = 0;
             }

             timeSeriesAgg[minuteStr][type]++;
             timeSeriesAgg[minuteStr].total++;
        }

        if (hour !== null && alertTime && alertTime.getTime() >= twentyFourHoursAgo) {
             hourlyCounts[hour] = (hourlyCounts[hour] || 0) + 1;
        }
    });

    const aggregatedTypes = Object.entries(typeCounts).map(([type, count]) => ({ type, count }));
    aggregatedTypes.sort((a, b) => b.count - a.count);
    const mostFrequent = aggregatedTypes.length > 0 ? aggregatedTypes[0].type : "无";
    behaviorData.value.aggregated = {
        types: aggregatedTypes,
        mostFrequentType: mostFrequent,
    };

    const sortedLabels = Array.from(timeLabels);
    const uniqueBehaviorTypes = Array.from(types);
    const datasets = [];

    uniqueBehaviorTypes.forEach(type => {
        datasets.push({
            label: type,
            type: 'bar',
            data: sortedLabels.map(label => timeSeriesAgg[label]?.[type] || 0),
            backgroundColor: getBehaviorColor(type),
            stack: 'counts',
            order: 2
        });
    });

    datasets.push({
        label: '总次数',
        type: 'line',
        data: sortedLabels.map(label => timeSeriesAgg[label]?.total || 0),
        borderColor: 'rgba(79, 209, 197, 0.8)',
        backgroundColor: 'rgba(79, 209, 197, 0.1)',
        tension: 0.2,
        fill: false,
        borderWidth: 2,
        pointBackgroundColor: 'rgba(79, 209, 197, 1)',
        pointRadius: 3,
        order: 1
    });

    const maxTimePoints = 30;
    const startIndex = Math.max(0, sortedLabels.length - maxTimePoints);
    const slicedLabels = sortedLabels.slice(startIndex);
    const slicedDatasets = datasets.map(ds => ({
        ...ds,
        data: ds.data.slice(startIndex)
    }));

    behaviorData.value.timeSeries = {
        labels: slicedLabels,
        datasets: slicedDatasets,
    };

    const heatmapResult = [];
    for (let h = 0; h < 24; h++) {
        heatmapResult.push({
            hour: h,
            count: hourlyCounts[h] || 0
        });
    }
    behaviorData.value.heatmapData = heatmapResult;
}

// WebSocket connection function for alerts
function connectAlertWebSocket() {
  if (alertWs && (alertWs.readyState === WebSocket.OPEN || alertWs.readyState === WebSocket.CONNECTING)) {
    console.log("Alert WebSocket is already open or connecting.");
    return;
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/alerts`;
  wsError.value = false;
  initialLoading.value = true;

  console.log("Attempting to connect to Alert WebSocket:", wsUrl);
  alertWs = new WebSocket(wsUrl);

  alertWs.onopen = () => {
    console.log("Alert WebSocket 已连接");
    wsConnected.value = true;
    initialLoading.value = false;
    wsError.value = false;
  };

  alertWs.onmessage = (event) => {
    try {
      const alert = JSON.parse(event.data);
      console.log("收到行为预警:", alert);

      behaviorData.value.alerts.unshift(alert);

      if (behaviorData.value.alerts.length > MAX_ALERTS_DISPLAY) {
        behaviorData.value.alerts.pop();
      }

      processAlertsAndUpdateData();

    } catch (error) {
      console.error("处理预警消息出错:", error, "原始数据:", event.data);
    }
  };

  alertWs.onclose = (event) => {
    console.log("Alert WebSocket 已关闭. Code:", event.code, "Reason:", event.reason);
    wsConnected.value = false;
    initialLoading.value = false;

    if (event.code !== 1000) {
       wsError.value = true;
       console.error("Alert WebSocket 连接异常关闭.");
    } else {
      wsError.value = false;
    }
    alertWs = null;
  };

  alertWs.onerror = (error) => {
    console.error("Alert WebSocket 错误:", error);
    wsConnected.value = false;
    initialLoading.value = false;
    wsError.value = true;
    alertWs = null;
  };
}

// Panel order - Load from localStorage or use default
const defaultPanelOrder = [
  { id: 4 },
  { id: 2 },
  { id: 3 },
  { id: 1 },
];
const panelOrder = ref(
  JSON.parse(
    localStorage.getItem("baPanelOrder") || JSON.stringify(defaultPanelOrder)
  )
);

// Panel sizes - Load from localStorage or use default
const defaultPanelSizes = {
  1: { height: "calc(50% - 10px)" },
  2: { height: "calc(100% - 20px)" },
  3: { height: "calc(50% - 10px)" },
  4: { height: "calc(100% - 20px)" },
};
const panelSizes = ref(
  JSON.parse(
    localStorage.getItem("baPanelSizes") || JSON.stringify(defaultPanelSizes)
  )
);

// Watch panelSizes for changes and update localStorage
watch(panelSizes, (newSizes) => {
  localStorage.setItem("baPanelSizes", JSON.stringify(newSizes));
}, { deep: true });

// Store panel refs dynamically
const panelRefs = shallowRef({});

// Map panel IDs to component names and CSS classes
const componentMap = {
  1: { component: BAActivityHeatmap, class: "activity-heatmap-panel" },
  2: { component: BABehaviorList, class: "behavior-timeseries-panel" },
  3: { component: BABehaviorChart, class: "behavior-chart-panel" },
  4: { component: BARealTimeMonitoring, class: "behavior-analysis-panel" },
};

function getComponentName(panelId) {
  return componentMap[panelId]?.component;
}

function getPanelClass(panelId) {
    const baseClass = componentMap[panelId]?.class || "";
    let gridPositionClass = '';
    const panelIndex = panelOrder.value.findIndex(p => p.id === panelId);

    switch (panelIndex) {
        case 0: gridPositionClass = 'grid-item-1'; break;
        case 1: gridPositionClass = 'grid-item-2'; break;
        case 2: gridPositionClass = 'grid-item-3'; break;
        case 3: gridPositionClass = 'grid-item-4'; break;
        default: break;
    }
    return `${baseClass} ${gridPositionClass}`;
}

// Provide props to components based on new data structure
function getComponentProps(panelId) {
  switch (panelId) {
    case 1:
      return { heatmapData: behaviorData.value.heatmapData };
    case 2:
      return { timeSeriesData: behaviorData.value.timeSeries };
    case 3:
      return {
          behaviorTypes: behaviorData.value.aggregated.types,
          mostFrequent: behaviorData.value.aggregated.mostFrequentType
      };
    case 4:
      return {};
    default:
      return {};
  }
}

// --- Resizing Logic (minor adjustments might be needed for grid) ---
const resizing = ref({
  active: false,
  panelId: null,
  direction: null,
  startX: 0,
  startY: 0,
  startWidth: 0,
  startHeight: 0,
  targetElement: null,
});

function getPanelStyle(panelId) {
  const size = panelSizes.value[panelId] || defaultPanelSizes[panelId];
  return {
    height: size.height,
    position: "relative",
  };
}

function startResize(event, panelId, direction) {
  event.preventDefault();
  event.stopPropagation();

  const panelElement =
    panelRefs.value[panelId]?.$el ||
    document.querySelector(`.panel[data-id="${panelId}"]`);

  if (!panelElement) {
    console.error("Panel element not found for ID:", panelId);
    return;
  }

  const rect = panelElement.getBoundingClientRect();

  resizing.value = {
    active: true,
    panelId,
    direction,
    startX: event.clientX,
    startY: event.clientY,
    startWidth: rect.width,
    startHeight: rect.height,
    targetElement: panelElement,
  };

  panelElement.classList.add("resizing");
  document.body.style.cursor = getResizeCursor(direction);
  document.body.style.userSelect = "none";

  document.addEventListener("mousemove", handleResize);
  document.addEventListener("mouseup", stopResize);
}

function handleResize(event) {
  if (!resizing.value.active) return;

  const { panelId, direction, startY, startHeight } = resizing.value;
  let newHeight = startHeight;
  const deltaY = event.clientY - startY;

  if (direction.includes("s")) {
    newHeight = startHeight + deltaY;
  }
  if (direction.includes("n")) {
    newHeight = startHeight - deltaY;
  }

  if (direction.includes("s") || direction.includes("n")) {
       newHeight = Math.max(100, newHeight);
       panelSizes.value[panelId] = {
         ...panelSizes.value[panelId],
         height: `${newHeight}px`,
       };
  } else {
      console.log("Horizontal resizing is disabled in this grid layout.");
  }
}

function stopResize() {
  if (!resizing.value.active) return;

  if (resizing.value.targetElement) {
    resizing.value.targetElement.classList.remove("resizing");
  }

  resizing.value.active = false;
  resizing.value.targetElement = null;
  document.body.style.cursor = "";
  document.body.style.userSelect = "";

  document.removeEventListener("mousemove", handleResize);
  document.removeEventListener("mouseup", stopResize);
}

function getResizeCursor(direction) {
  if (direction.includes("n")) return "n-resize";
  if (direction.includes("s")) return "s-resize";
  return "default";
}
// --- End Resizing Logic ---

// Save panel order to localStorage
function savePanelOrder() {
  localStorage.setItem("baPanelOrder", JSON.stringify(panelOrder.value));
}

onMounted(() => {
  connectAlertWebSocket();
});

onUnmounted(() => {
  if (alertWs) {
    alertWs.onclose = null;
    alertWs.onerror = null;
    alertWs.close();
    alertWs = null;
  }
  document.removeEventListener("mousemove", handleResize);
  document.removeEventListener("mouseup", stopResize);
});
</script>

<style scoped>
/* Keep global styles for the page layout, container, loading message etc. */
.behavior-analysis-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: var(--dark-bg);
  color: var(--text-primary);
  position: relative;
  overflow: hidden;
}

/* Cyberpunk background */
.behavior-analysis-page::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: linear-gradient(
      to bottom,
      rgba(10, 25, 47, 0.8) 0%,
      rgba(10, 25, 47, 0.9) 100%
    ),
    repeating-linear-gradient(
      0deg,
      transparent,
      transparent 2px,
      rgba(79, 209, 197, 0.05) 2px,
      rgba(79, 209, 197, 0.05) 4px
    );
  z-index: -1;
}
.behavior-analysis-page::after {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: linear-gradient(
      rgba(79, 209, 197, 0.05) 1px,
      transparent 1px
    ),
    linear-gradient(90deg, rgba(79, 209, 197, 0.05) 1px, transparent 1px);
  background-size: 50px 50px;
  z-index: -1;
}

.content-container {
  flex: 1;
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto 20px;
  width: calc(100% - 40px);
  display: flex;
  flex-direction: column;
  position: relative;
}

.loading-message, .error-message {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: 200px;
  flex-grow: 1;
  text-align: center;
  color: var(--text-secondary);
  font-size: 1.1rem;
  padding: 20px;
}
.error-message p {
  margin-bottom: 15px;
  color: var(--error-color, #ff6b6b);
}
.retry-button {
    padding: 8px 15px;
    background-color: var(--cyber-neon);
    color: var(--dark-bg);
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.3s ease;
    font-weight: bold;
}
.retry-button:hover {
    background-color: #4fd1c5;
}

.cyber-spinner {
  width: 50px;
  height: 50px;
  border: 3px solid rgba(79, 209, 197, 0.3);
  border-top: 3px solid var(--cyber-neon);
  border-radius: 50%;
  margin-bottom: 20px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

.analysis-container {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: repeat(2, auto);
  gap: 20px;
  padding: 10px 0;
  flex: 1;
  min-height: 500px;
}

/* Assign grid position using classes (adjust if using grid-template-areas) */
.grid-item-1 { grid-column: 1 / 2; grid-row: 1 / 2; }
.grid-item-2 { grid-column: 2 / 3; grid-row: 1 / 2; }
.grid-item-3 { grid-column: 1 / 2; grid-row: 2 / 3; }
.grid-item-4 { grid-column: 2 / 3; grid-row: 2 / 3; }

/* Default Panel Styles */
.panel {
  margin: 0 !important;
  box-sizing: border-box;
  background-color: rgba(10, 25, 47, 0.7);
  border: 1px solid rgba(79, 209, 197, 0.3);
  border-radius: 5px;
  box-shadow: 0 0 15px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: box-shadow 0.3s ease, border-color 0.3s ease;
  position: relative;
  transform: translateZ(0);
}

.panel:hover {
  box-shadow: 0 0 20px rgba(79, 209, 197, 0.2);
  border-color: rgba(79, 209, 197, 0.5);
}

/* Cyber Panel Decoration */
.cyber-panel::before {
  content: "";
  position: absolute;
  top: -1px;
  right: -1px;
  width: 30px;
  height: 30px;
  border-top: 2px solid var(--cyber-neon);
  border-right: 2px solid var(--cyber-neon);
  opacity: 0.7;
  pointer-events: none;
  border-radius: 0 5px 0 0;
}

.cyber-panel::after {
  content: "";
  position: absolute;
  bottom: -1px;
  left: -1px;
  width: 30px;
  height: 30px;
  border-bottom: 2px solid var(--cyber-neon);
  border-left: 2px solid var(--cyber-neon);
  opacity: 0.7;
  pointer-events: none;
  border-radius: 0 0 0 5px;
}

/* Drag and Drop Styles */
.ghost-panel {
  opacity: 0.5;
  background: rgba(79, 209, 197, 0.1) !important;
  border: 1px dashed var(--cyber-neon);
}

.chosen-panel {
  box-shadow: 0 0 25px rgba(79, 209, 197, 0.6) !important;
  border-color: var(--cyber-neon) !important;
  z-index: 20;
}

.drag-panel {
  transform: scale(1.02);
  z-index: 30;
}

/* Resizing Styles */
.panel.resizing {
  transition: none !important;
  border-color: rgba(79, 209, 197, 0.8);
  box-shadow: 0 0 10px rgba(79, 209, 197, 0.5);
  z-index: 15;
}

/* Global resize handle styles (Adjusted for vertical only focus) */
.resize-handle {
  position: absolute;
  background-color: transparent;
  z-index: 10;
  transition: background-color 0.2s ease;
}
.panel:hover .resize-handle {
  background-color: rgba(79, 209, 197, 0.1);
}
.resize-handle:hover {
  background-color: rgba(79, 209, 197, 0.4) !important;
}

/* Only enable vertical resize handles visually and functionally */
.resize-s, .resize-n {
  left: 0;
  width: 100%;
  height: 8px;
}
.resize-s { bottom: 0; cursor: s-resize; }
.resize-n { top: 0; cursor: n-resize; }

/* Disable horizontal handles */
.resize-e, .resize-w { display: none; }

/* Disable corner handles or adapt them for vertical-only */
.resize-se, .resize-sw, .resize-ne, .resize-nw {
  width: 15px;
  height: 15px;
}
.resize-se { bottom: 0; right: 0; cursor: s-resize; border-radius: 0 0 5px 0; }
.resize-sw { bottom: 0; left: 0; cursor: s-resize; border-radius: 0 0 0 5px; }
.resize-ne { top: 0; right: 0; cursor: n-resize; border-radius: 0 5px 0 0; }
.resize-nw { top: 0; left: 0; cursor: n-resize; border-radius: 5px 0 0 0; }

/* Add or adjust styles for the new time series panel if needed */
.behavior-timeseries-panel {
  /* specific styles */
}

/* Specific panel classes if needed */
.activity-heatmap-panel {
  /* styles for heatmap panel */
}
.behavior-chart-panel {
  /* styles for doughnut panel */
}
.behavior-analysis-panel {
  /* styles for monitoring panel */
}
</style>
