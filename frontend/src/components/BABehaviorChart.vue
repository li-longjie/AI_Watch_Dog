<template>
  <div>
    <div class="panel-title">
      <span class="panel-icon">📈</span>
      行为趋势
      <div class="panel-decoration"></div>
    </div>
    <div class="chart-container">
      <div class="cyber-chart">
        <canvas ref="pieChartCanvas" class="pie-chart-canvas"></canvas>
        <div v-if="!behaviors || behaviors.length === 0" class="no-data">
          暂无行为数据
        </div>
      </div>
    </div>
    <!-- Resize Handles -->
    <div
      class="resize-handle resize-e"
      @mousedown="$emit('start-resize', $event, 'e')"
    ></div>
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
import { defineProps, defineEmits, ref, onMounted, watch, computed } from "vue";
import Chart from "chart.js/auto"; // 确保已安装 chart.js
import ChartDataLabels from "chartjs-plugin-datalabels"; // 直接导入插件

const props = defineProps({
  behaviors: {
    type: Array,
    required: true,
    default: () => [],
  },
});

defineEmits(["start-resize"]);

// Canvas 引用
const pieChartCanvas = ref(null);
let chartInstance = null;

// 计算总和以便计算百分比
const totalCount = computed(() => {
  return props.behaviors.reduce((sum, b) => sum + b.count, 0) || 1; // 避免除以 0
});

// 获取图表颜色（匹配图片中的颜色）
function getChartColor(behaviorType) {
  const colorMap = {
    专注工作: "#1e3a8a", // 深蓝色 (33%)
    吃东西: "#f97316", // 橙色 (27%)
    喝水: "#22c55e", // 绿色 (20%)
    玩手机: "#ef4444", // 红色 (13%)
    睡觉: "#a855f7", // 紫色 (7%)
    default: "#d1d5db", // 灰色
  };
  return colorMap[behaviorType] || colorMap.default;
}

// 初始化或更新饼图
function renderPieChart() {
  const ctx = pieChartCanvas.value.getContext("2d");

  // 如果已有图表实例，先销毁
  if (chartInstance) {
    chartInstance.destroy();
  }

  chartInstance = new Chart(ctx, {
    type: "pie", // 使用 pie 类型
    data: {
      labels: props.behaviors.map((b) => b.type),
      datasets: [
        {
          data: props.behaviors.map((b) => b.count),
          backgroundColor: props.behaviors.map((b) => getChartColor(b.type)),
          borderColor: "transparent", // 去掉边框颜色
          borderWidth: 0, // 移除边框宽度
          offset: 10, // 增加扇形分离效果，增强立体感
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      rotation: -30, // 轻微旋转，模拟立体视角
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: "rgba(255, 255, 255, 0.8)",
            font: {
              size: 12,
              weight: "bold", // 图例字体加粗
            },
            boxWidth: 12, // 图例颜色块宽度
            boxHeight: 12, // 图例颜色块高度
            padding: 10,
            usePointStyle: true, // 使用点样式（圆形），避免边框
            pointStyle: "rect", // 设置为方形（匹配图片）
          },
        },
        tooltip: {
          enabled: false, // 禁用鼠标悬停提示
        },
        datalabels: {
          // 使用 chartjs-plugin-datalabels 显示百分比
          color: "#fff",
          font: {
            weight: "bold", // 百分比标签字体加粗
            size: 14,
          },
          formatter: (value) => {
            const percentage = ((value / totalCount.value) * 100).toFixed(0);
            return `${percentage}%`;
          },
          textShadow: "0 0 3px rgba(0, 0, 0, 0.5)", // 添加文字阴影
        },
      },
      // 添加阴影以增强立体感
      elements: {
        arc: {
          shadowOffsetX: 3,
          shadowOffsetY: 3,
          shadowBlur: 10,
          shadowColor: "rgba(0, 0, 0, 0.5)",
        },
      },
    },
  });
}

// 当 behaviors 变化时更新图表
watch(
  () => props.behaviors,
  () => {
    if (pieChartCanvas.value) {
      renderPieChart();
    }
  },
  { deep: true }
);

onMounted(() => {
  // 注册 chartjs-plugin-datalabels
  Chart.register(ChartDataLabels);
  renderPieChart();
});
</script>

<style scoped>
.panel-title {
  padding: 10px 15px;
  font-size: 1.1rem;
  color: var(--cyber-neon);
  border-bottom: 1px solid rgba(79, 209, 197, 0.3);
  display: flex;
  align-items: center;
  position: relative;
  letter-spacing: 1px;
  text-shadow: 0 0 5px rgba(79, 209, 197, 0.3);
  cursor: move;
  user-select: none;
  z-index: 5;
}

.panel-icon {
  margin-right: 8px;
}

.chart-container {
  position: relative;
  width: 100%;
  height: calc(100% - 45px);
  padding: 20px;
  box-sizing: border-box;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: rgba(10, 25, 47, 0.7);
  border-radius: 0 0 5px 5px;
}

.cyber-chart {
  position: relative;
  width: 100%;
  max-width: 400px;
  height: 100%;
}

.pie-chart-canvas {
  width: 100%;
  height: 100%;
  filter: drop-shadow(
    0 4px 8px rgba(0, 0, 0, 0.3)
  ); /* 添加 CSS 阴影，增强立体感 */
}

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

.resize-e {
  top: 0;
  right: 0;
  width: 5px;
  height: 100%;
  cursor: e-resize;
}

.resize-n {
  top: 0;
  left: 0;
  width: 100%;
  height: 5px;
  cursor: n-resize;
}

.resize-ne {
  top: 0;
  right: 0;
  width: 15px;
  height: 15px;
  cursor: ne-resize;
  border-radius: 0 5px 0 0;
}
</style>
