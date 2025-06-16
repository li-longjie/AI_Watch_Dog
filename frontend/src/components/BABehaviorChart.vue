<template>
  <div class="behavior-chart-panel-container">
    <div class="panel-header">
      <h3 class="panel-title">
        <i class="fas fa-bullseye"></i> 行为分布
      </h3>
    </div>
    <div class="chart-container">
      <div class="chart-display-area">
        <!-- Wrapper for Doughnut Chart AND Custom Legend -->
        <div class="doughnut-wrapper">
          <canvas ref="pieChartCanvas" class="pie-chart-canvas"></canvas>
          <!-- Custom HTML Legend -->
          <div v-if="behaviorTypes && behaviorTypes.length > 0" class="custom-legend">
            <div v-for="behavior in behaviorTypes" :key="behavior.type" class="legend-item">
              <span class="legend-color-box" :style="{ backgroundColor: getChartColor(behavior.type) }"></span>
              <span class="legend-label-text">{{ behavior.type }}</span>
            </div>
          </div>
        </div>

        <!-- Wrapper for Stat Item (replaces frequent-info-box) -->
        <div class="stat-item-wrapper">
          <div class="stat-item">
            <div class="stat-value cyber-value highlight">
              {{ mostFrequent || "无" }}
            </div>
            <div class="stat-label">最频繁行为</div>
          </div>
        </div>

      </div>
      <!-- No data message remains outside the flex container or adjust as needed -->
      <div
        v-if="!behaviorTypes || behaviorTypes.length === 0"
        class="no-data"
      >
        暂无行为数据
      </div>
    </div>
    <!-- Resize Handles -->
    <div
      class="resize-handle resize-n"
      @mousedown="$emit('start-resize', $event, 'n')"
    ></div>
    <div
      class="resize-handle resize-ne"
      @mousedown="$emit('start-resize', $event, 'ne')"
    ></div>
  </div>
</template>

<script setup>
import { defineProps, defineEmits, ref, onMounted, watch, computed, onBeforeUnmount } from "vue";
import Chart from "chart.js/auto";
import ChartDataLabels from "chartjs-plugin-datalabels";

// Register the plugin globally
Chart.register(ChartDataLabels);

const props = defineProps({
  behaviorTypes: {
    type: Array,
    required: true,
    default: () => [],
  },
  mostFrequent: {
    type: String,
    default: "无",
  }
});

defineEmits(["start-resize"]);

const pieChartCanvas = ref(null);
let chartInstance = null;

const totalCount = computed(() => {
  if (!Array.isArray(props.behaviorTypes)) return 0;
  return props.behaviorTypes.reduce((sum, b) => sum + b.count, 0);
});

function getChartColor(behaviorType) {
  const colorMap = {
    专注工作学习: "#22d3a7", 专注工作: "#22d3a7", 专注: "#22d3a7", // 改为绿色
    吃东西: "#f97316", 吃: "#f97316",
    喝水: "#22c55e", 喝: "#22c55e",
    玩手机: "#ef4444", 玩: "#ef4444",
    睡觉: "#a855f7", 睡: "#a855f7",
    default: "#6b7280",
  };
   const hexColor = colorMap[behaviorType] || colorMap.default;
   const r = parseInt(hexColor.slice(1, 3), 16);
   const g = parseInt(hexColor.slice(3, 5), 16);
   const b = parseInt(hexColor.slice(5, 7), 16);
   return `rgba(${r}, ${g}, ${b}, 0.85)`;
}

// --- Updated Custom Plugin to Draw Text in Center ---
// --- Remove Most Frequent drawing logic ---
const centerTextPlugin = {
  id: 'centerText',
  afterDraw: (chart) => {
    if (chart.config.type !== 'doughnut') return;
    const ctx = chart.ctx;
    const { top, bottom, left, right, width, height } = chart.chartArea;
    const centerX = left + width / 2;
    const centerY = top + height / 2;

    const currentTotal = totalCount.value;
    // Remove: const mostFrequentText = props.mostFrequent || "无";

    ctx.save();
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    // 1. Draw Total Count
    ctx.font = `bold ${height * 0.22}px 'Orbitron', sans-serif`; // Slightly larger for 2 lines
    ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
    // Position count slightly above center
    ctx.fillText(`${currentTotal}`, centerX, centerY - (height * 0.05));

    // 2. Draw "总次数" Label
    ctx.font = `normal ${height * 0.1}px sans-serif`; // Adjust size
    ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
    // Position label below the count
    ctx.fillText('总次数', centerX, centerY + (height * 0.15)); // Adjust position

    // Remove: 3. Draw Most Frequent Behavior

    ctx.restore();
  }
};

function renderPieChart() {
  if (!pieChartCanvas.value) return;
  const ctx = pieChartCanvas.value.getContext("2d");

  if (chartInstance) {
    chartInstance.destroy();
    chartInstance = null;
  }

  if (!Array.isArray(props.behaviorTypes) || props.behaviorTypes.length === 0) {
    console.log("No behavior types data to render chart.");
     // Optionally clear canvas if needed when empty
     ctx.clearRect(0, 0, pieChartCanvas.value.width, pieChartCanvas.value.height);
    return;
  }

  chartInstance = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: props.behaviorTypes.map((b) => b.type),
      datasets: [
        {
          data: props.behaviorTypes.map((b) => b.count),
          backgroundColor: props.behaviorTypes.map((b) => getChartColor(b.type)),
          borderColor: 'transparent',
          borderWidth: 1,
          hoverOffset: 10,
          borderRadius: 5,
        },
      ],
    },
    plugins: [ChartDataLabels, centerTextPlugin], // Ensure both plugins are included
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '65%',
      layout: {
          padding: 5
      },
      plugins: {
        legend: {
          display: false, // 禁用Chart.js默认图例，使用自定义HTML图例
        },
        tooltip: {
          enabled: true,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          padding: 8,
          titleFont: { size: 12 },
          bodyFont: { size: 11 },
          usePointStyle: true,
          boxPadding: 3,
          callbacks: {
            label: function(context) {
              let label = context.dataset.label || '';
              if (context.label) { label = context.label; }
              if (label) { label += ': '; }
              const value = context.parsed;
              // Calculate percentage within the callback
              const currentTotal = context.chart.data.datasets[0].data.reduce((a, b) => a + b, 0) || 1;
              const percentage = ((value / currentTotal) * 100).toFixed(0);
              return `${label} ${value} (${percentage}%)`;
            }
          }
        },
        datalabels: {
          color: "#fff",
          font: { weight: "bold", size: 11 }, // Even smaller
          formatter: (value, context) => {
            const currentTotal = context.chart.data.datasets[0].data.reduce((a, b) => a + b, 0) || 1;
            if (currentTotal === 0) return '0%';
            const percentage = ((value / currentTotal) * 100).toFixed(0);
            return percentage > 8 ? `${percentage}%` : ''; // Show only if > 8%
          },
          display: 'auto',
          anchor: 'center',
          align: 'center',
          // Add backdrop for better readability on complex backgrounds
          // backgroundColor: 'rgba(0, 0, 0, 0.5)',
          // borderRadius: 4,
          // padding: 2,
        },
      },
      elements: {
        arc: {
            // Removed the explicit shadow from options, rely on CSS filter
        },
      },
      animation: {
        duration: 800,
        easing: 'easeOutQuart',
      }
    },
  });
}

watch(
  () => props.behaviorTypes,
  () => {
    renderPieChart();
  },
  { deep: true, immediate: true }
);

onMounted(() => {
    // Chart is rendered by the immediate watch
});

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.destroy();
    chartInstance = null;
  }
});
</script>

<style scoped>
.behavior-chart-panel-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 15px 20px;
  box-sizing: border-box;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  padding: 0;
  flex-shrink: 0;
}
.panel-title {
  font-size: 1.3rem;
  color: var(--cyber-neon);
  margin: 0;
  text-shadow: 0 0 5px rgba(79, 209, 197, 0.7);
  cursor: move;
  user-select: none;
}
.panel-title i {
    margin-right: 10px;
}

.chart-container {
  position: relative;
  width: 100%;
  height: calc(100% - 45px);
  padding: 0 0 10px 0; /* 底部增加padding为图例留空间 */
  box-sizing: border-box;
  display: flex;
  justify-content: center;
  align-items: center;
  background: transparent;
  border-radius: 0 0 12px 12px;
}

/* New Flex Container for chart and info box */
.chart-display-area {
    display: flex;
    align-items: stretch;
    justify-content: center;
    width: 100%;
    height: 100%;
    gap: 15px;
    min-height: 250px; /* 设置最小高度确保有足够显示空间 */
}

/* Wrapper for the Doughnut chart canvas */
.doughnut-wrapper {
    flex: 0 1 60%;
    display: flex;
    flex-direction: column;
    align-items: center;
    height: 100%;
    position: relative;
    min-height: 0;
    max-width: 300px;
    padding-bottom: 5px; /* 为图例预留空间 */
}

.pie-chart-canvas {
    display: block;
    max-width: 100%;
    width: auto;
    flex-grow: 1;
    max-height: calc(100% - 40px); /* 为图例预留40px空间 */
    margin-bottom: 8px; /* 增加与图例之间的间距 */
    filter: drop-shadow(0 0 8px rgba(79, 209, 197, 0.2))
            drop-shadow(0 4px 6px rgba(0, 0, 0, 0.4));
}

/* --- Styles for the new stat item wrapper and its content --- */
.stat-item-wrapper {
    flex: 0 1 auto; /* Allow shrinking, size based on content */
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100%;
    max-width: 140px; /* Increase max-width slightly */
}

.stat-item {
  text-align: center;
  padding: 20px 15px; /* Increase padding slightly */
  position: relative;
  z-index: 1;
  border-radius: 8px; /* Add border-radius */
  border: 1px solid rgba(255, 255, 255, 0.1); /* Optional subtle border */

  /* ---毛玻璃效果 Start --- */
  background-color: rgba(10, 25, 47, 0.5); /* Semi-transparent background - Adjust color/opacity */
  backdrop-filter: blur(8px); /* Apply blur - Adjust blur amount */
  -webkit-backdrop-filter: blur(8px); /* For Safari */
  /* ---毛玻璃效果 End --- */

   /* Optional: Add a subtle inner shadow or glow if needed */
   box-shadow: inset 0 0 15px rgba(79, 209, 197, 0.1);
}

.stat-value {
  font-size: 1.9rem; /* Adjust size */
  font-weight: bold;
  color: var(--cyber-neon);
  margin-bottom: 8px; /* Increase margin */
  text-shadow: 0 0 10px rgba(79, 209, 197, 0.5);
   word-break: break-word;
   line-height: 1.2;
}

.cyber-value {
  position: relative;
  display: inline-block;
   max-width: 100%;
}

/* Underline effect for cyber-value */
.cyber-value::after {
  content: "";
  position: absolute;
  bottom: -4px; /* Adjust position */
  left: 10%;
  width: 80%;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    var(--cyber-neon),
    transparent
  );
}

.stat-label {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-top: 8px; /* Increase margin */
}

/* Highlight style for the most frequent behavior value */
.highlight {
  color: #fc8181;
  text-shadow: 0 0 10px rgba(252, 129, 129, 0.5);
}
/* --- End copied styles --- */

.no-data {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: var(--text-secondary);
  font-style: italic;
}

.resize-handle {
  position: absolute;
  background-color: rgba(79, 209, 197, 0.2);
  z-index: 10;
}

.resize-handle:hover {
  background-color: rgba(79, 209, 197, 0.5);
}

.resize-e { display: none; }
.resize-n {
  top: 0; left: 0; width: 100%; height: 8px; cursor: n-resize;
}
.resize-ne {
  top: 0; right: 0; width: 15px; height: 15px; cursor: n-resize; border-radius: 0 8px 0 0;
}

/* --- Custom Legend Styles --- */
.custom-legend {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 6px 12px; /* 增加间距，避免文字挤在一起 */
    padding: 8px 4px; /* 增加内边距 */
    width: 100%;
    max-width: 280px; /* 增加最大宽度 */
    flex-shrink: 0;
    margin-top: 8px; /* 增加上边距 */
    min-height: 25px; /* 设置最小高度确保有足够空间 */
}

.legend-item {
    display: flex;
    align-items: center;
    cursor: default;
}

.legend-color-box {
    width: 10px;
    height: 10px;
    border-radius: 2px; /* Slightly rounded corners */
    margin-right: 6px;
    display: inline-block;
    /* Background color set dynamically */
}

.legend-label-text {
    font-size: 0.8rem; /* 稍微增大字体，提高可读性 */
    color: var(--text-secondary);
    white-space: nowrap;
    line-height: 1.2; /* 增加行高 */
}
/* --- End Custom Legend Styles --- */
</style>

