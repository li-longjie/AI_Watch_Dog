<template>
  <div>
    <div class="panel-title">
      <span class="panel-icon">⏱️</span>
      行为时间趋势
      <div class="panel-decoration"></div>
    </div>
    <div class="chart-container">
      <canvas ref="timeSeriesChartCanvas"></canvas>
      <div v-if="!hasData" class="no-data">
        等待行为数据...
      </div>
    </div>
    <!-- Resize Handles -->
    <div
      class="resize-handle resize-w"
      @mousedown="$emit('start-resize', $event, 'w')"
    ></div>
    <div
      class="resize-handle resize-s"
      @mousedown="$emit('start-resize', $event, 's')"
    ></div>
    <div
      class="resize-handle resize-sw"
      @mousedown="$emit('start-resize', $event, 'sw')"
    ></div>
  </div>
</template>

<script setup>
import { defineProps, defineEmits, ref, watch, onMounted, onBeforeUnmount, computed } from "vue";
import Chart from 'chart.js/auto';
import 'chartjs-adapter-date-fns'; // Import adapter if using time scale

const props = defineProps({
  timeSeriesData: {
    type: Object,
    required: true,
    default: () => ({ labels: [], datasets: [] }), // { labels: string[], datasets: ChartDataset[] }
  },
});

defineEmits(["start-resize"]);

const timeSeriesChartCanvas = ref(null);
let chartInstance = null;

// 将"专注工作学习"的颜色设为绿色
const behaviorColors = {
  专注工作学习: "#22d3a7",
  专注工作: "#22d3a7",
  专注: "#22d3a7",
  吃东西: "#f97316",
  喝水: "#22c55e",
  玩手机: "#ef4444", 
  睡觉: "#a855f7",
  default: "#6b7280"
};

// Check if there's valid data to display
const hasData = computed(() => {
    return props.timeSeriesData &&
           Array.isArray(props.timeSeriesData.labels) &&
           props.timeSeriesData.labels.length > 0 &&
           Array.isArray(props.timeSeriesData.datasets) &&
           props.timeSeriesData.datasets.length > 0;
});

function renderChart() {
  if (!timeSeriesChartCanvas.value) return;
  const ctx = timeSeriesChartCanvas.value.getContext("2d");

  if (chartInstance) {
    // More efficient update instead of destroy/recreate
    chartInstance.data.labels = props.timeSeriesData.labels;
    
    // 在更新图表之前应用颜色
    if (props.timeSeriesData.datasets && Array.isArray(props.timeSeriesData.datasets)) {
      const updatedDatasets = [...props.timeSeriesData.datasets];
      for (let i = 0; i < updatedDatasets.length; i++) {
        if (updatedDatasets[i].type === 'bar') {
          updatedDatasets[i] = {
            ...updatedDatasets[i],
            backgroundColor: behaviorColors[updatedDatasets[i].label] || behaviorColors.default
          };
        }
      }
      chartInstance.data.datasets = updatedDatasets;
    } else {
      chartInstance.data.datasets = props.timeSeriesData.datasets;
    }
    
    chartInstance.update(); // Use Chart.js update method
    return;
  }

   // Only create chart if data exists
   if (!hasData.value) {
       console.log("No time series data to render.");
       return;
   }

  // 确保在创建图表之前应用颜色
  const datasets = [];
  if (props.timeSeriesData.datasets && Array.isArray(props.timeSeriesData.datasets)) {
    for (const dataset of props.timeSeriesData.datasets) {
      if (dataset.type === 'bar') {
        datasets.push({
          ...dataset,
          backgroundColor: behaviorColors[dataset.label] || behaviorColors.default
        });
      } else {
        datasets.push(dataset);
      }
    }
  }

  chartInstance = new Chart(ctx, {
    // Type needs to be 'bar' or 'line' initially, datasets specify their own type
     type: 'bar', // Set a base type, but datasets will override
    data: {
      labels: props.timeSeriesData.labels,
      datasets: datasets.length > 0 ? datasets : props.timeSeriesData.datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { // Improve tooltip interaction
          mode: 'index', // Show tooltips for all datasets at that index
          intersect: false,
      },
      plugins: {
        legend: {
          position: 'top', // Move legend to top
          labels: {
             color: 'rgba(255, 255, 255, 0.8)',
             font: { size: 11 },
             boxWidth: 10,
             boxHeight: 10,
             padding: 8,
             usePointStyle: true,
             pointStyle: 'rectRounded',
          },
        },
        tooltip: { // Customize tooltips
            enabled: true,
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            titleColor: 'rgba(255, 255, 255, 0.9)',
            bodyColor: 'rgba(255, 255, 255, 0.8)',
            padding: 10,
            borderColor: 'rgba(79, 209, 197, 0.5)',
            borderWidth: 1,
            usePointStyle: true,
            callbacks: {
                // Optional: customize tooltip content
                // title: function(context) { return `Time: ${context[0].label}`; },
                // label: function(context) {
                //     let label = context.dataset.label || '';
                //     if (label) { label += ': '; }
                //     if (context.parsed.y !== null) { label += context.parsed.y; }
                //     return label;
                // }
            }
        },
         // Datalabels might be too cluttered on this chart, disable for now
        // datalabels: {
        //    display: false,
        // },
      },
      scales: {
        x: {
          stacked: true, // Stack bars on X-axis
          grid: {
            color: 'rgba(255, 255, 255, 0.1)', // Lighter grid lines
          },
          ticks: {
            color: 'rgba(255, 255, 255, 0.7)',
            maxRotation: 0, // Prevent label rotation
            autoSkip: true, // Skip labels if too crowded
            maxTicksLimit: 10 // Limit number of visible ticks
          },
        },
        y: {
          stacked: true, // Stack bars on Y-axis
          beginAtZero: true,
          grid: {
            color: 'rgba(255, 255, 255, 0.1)',
          },
          ticks: {
            color: 'rgba(255, 255, 255, 0.7)',
             stepSize: 1 // Ensure integer steps for counts
          },
          title: {
              display: true,
              text: '行为次数',
              color: 'rgba(255, 255, 255, 0.7)',
              font: { size: 12 }
          }
        },
      },
    },
  });
}

watch(
  () => props.timeSeriesData,
  () => {
    renderChart();
  },
  { deep: true } // No immediate needed if we rely on parent sending initial data
);

onMounted(() => {
  // Initial render attempt - might be empty if WS hasn't sent data yet
  renderChart();
});

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.destroy();
    chartInstance = null;
  }
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

/* Reuse chart container style */
.chart-container {
  position: relative;
  width: 100%;
  height: calc(100% - 45px); /* Adjust based on title height */
  padding: 15px; /* Add padding around the chart */
  box-sizing: border-box;
  background-color: rgba(10, 25, 47, 0.7); /* Same background */
  border-radius: 0 0 5px 5px; /* Match panel rounding */
  display: flex; /* Center canvas if needed, though chartjs handles size */
  justify-content: center;
  align-items: center;
}

canvas {
  width: 100%;
  height: 100%;
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

/* Resize handle styles */
.resize-handle {
  position: absolute;
  background-color: rgba(79, 209, 197, 0.2);
  z-index: 10;
}
.resize-handle:hover {
  background-color: rgba(79, 209, 197, 0.5);
}
.resize-w { display: none; }
.resize-s {
  bottom: 0; left: 0; width: 100%; height: 8px; cursor: s-resize;
}
.resize-sw {
  bottom: 0; left: 0; width: 15px; height: 15px; cursor: s-resize; border-radius: 0 0 0 5px;
}

</style>
