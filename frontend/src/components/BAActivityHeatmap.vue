<template>
  <div class="heatmap-panel-container">
    <div class="panel-title">
      <span class="panel-icon">🔥</span>
      活动热力图 (近24h)
      <div class="panel-decoration"></div>
    </div>
    <div class="heatmap-content" ref="heatmapContainer">
      <div v-if="heatmapData && heatmapData.length === 24" class="heatmap-grid">
        <div
          v-for="item in heatmapData"
          :key="item.hour"
          class="heatmap-cell"
          :style="{ backgroundColor: getHeatmapColor(item.count) }"
          :title="`${item.hour}:00 - ${item.hour}:59\n次数: ${item.count}`"
        >
          <span class="heatmap-hour-label">{{ item.hour }}</span>
          <!-- <span class="heatmap-count-label">{{ item.count }}</span> -->
        </div>
      </div>
      <div v-else class="no-data">
        等待热力图数据...
      </div>
      <!-- Optional: Add legend -->
       <div class="heatmap-legend">
           <span class="legend-label">低</span>
           <div class="legend-gradient"></div>
           <span class="legend-label">高</span>
       </div>
    </div>
    <!-- Resize Handles -->
    <div
      class="resize-handle resize-e"
      @mousedown="$emit('start-resize', $event, 'e')"
    ></div>
    <div
      class="resize-handle resize-s"
      @mousedown="$emit('start-resize', $event, 's')"
    ></div>
    <div
      class="resize-handle resize-se"
      @mousedown="$emit('start-resize', $event, 'se')"
    ></div>
  </div>
</template>

<script setup>
import { defineProps, defineEmits, computed, ref } from 'vue';

const props = defineProps({
  heatmapData: { // Expects array: [{ hour: 0, count: 5 }, ...] (24 items)
    type: Array,
    required: true,
    default: () => [],
  },
});

defineEmits(['start-resize']);

const heatmapContainer = ref(null);

// Find max count for color scaling
const maxCount = computed(() => {
    if (!props.heatmapData || props.heatmapData.length === 0) return 1; // Avoid division by zero
    // Ensure all counts are numbers before using Math.max
    const counts = props.heatmapData.map(item => Number(item.count) || 0);
    return Math.max(...counts, 1); // Ensure max is at least 1
});

// Simple color interpolation: transparent -> light blue -> cyan -> neon green
function getHeatmapColor(count) {
    // Ensure count is a number
    const numericCount = Number(count) || 0;
    const currentMax = maxCount.value; // Use the computed max value
    // Avoid division by zero if maxCount is 0 or 1 and count is also low
    const intensity = currentMax > 0 ? numericCount / currentMax : 0;

    if (intensity <= 0) {
        return 'rgba(13, 25, 42, 0.5)'; // Dark background for zero activity
    } else if (intensity <= 0.25) {
        // Interpolate between dark bg and light blue
        const alpha = intensity / 0.25;
        return `rgba(100, 180, 255, ${0.2 + alpha * 0.4})`; // Light blue, increasing opacity
    } else if (intensity <= 0.6) {
         // Interpolate between light blue and cyan
         const alpha = (intensity - 0.25) / (0.6 - 0.25);
         // Simple linear interpolation for RGB (adjust as needed)
         const r = Math.round(100 + (79 - 100) * alpha); // 100 -> 79
         const g = Math.round(180 + (209 - 180) * alpha); // 180 -> 209
         const b = Math.round(255 + (197 - 255) * alpha); // 255 -> 197
         return `rgba(${r}, ${g}, ${b}, 0.8)`; // Cyanish, fixed opacity
    } else {
        // Interpolate between cyan and bright neon green (more intense)
        // Clamp intensity to 1 for color calculation if it somehow exceeds maxCount
        const clampedIntensity = Math.min(intensity, 1.0);
        const alpha = (clampedIntensity - 0.6) / (1.0 - 0.6);
        const r = Math.round(79 + (50 - 79) * alpha); // 79 -> 50 (less red)
        const g = Math.round(209 + (255 - 209) * alpha); // 209 -> 255 (more green)
        const b = Math.round(197 + (50 - 197) * alpha); // 197 -> 50 (less blue)
        return `rgba(${r}, ${g}, ${b}, ${0.8 + alpha * 0.2})`; // Neon green ish, increasing opacity slightly
    }
}
</script>

<style scoped>
.heatmap-panel-container {
    display: flex;
    flex-direction: column;
    height: 100%; /* Ensure container takes full panel height */
}
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
  flex-shrink: 0; /* Prevent title from shrinking */
}
.panel-icon {
  margin-right: 8px;
}

.heatmap-content {
    flex-grow: 1; /* Allow content to fill remaining space */
    padding: 15px;
    box-sizing: border-box;
    background-color: rgba(10, 25, 47, 0.7);
    border-radius: 0 0 5px 5px;
    display: flex;
    flex-direction: column; /* Stack grid and legend */
    overflow: hidden; /* Hide overflow */
}

.heatmap-grid {
    display: grid;
    /* Create a 4x6 grid for 24 hours */
    grid-template-columns: repeat(6, 1fr);
    grid-template-rows: repeat(4, 1fr);
    gap: 5px; /* Gap between cells */
    width: 100%;
    flex-grow: 1; /* Grid takes up most space */
}

.heatmap-cell {
    background-color: rgba(255, 255, 255, 0.05); /* Default background */
    border-radius: 3px;
    display: flex;
    justify-content: center;
    align-items: center;
    position: relative;
    transition: background-color 0.3s ease, transform 0.2s ease;
    cursor: default; /* Indicate non-interactive or add tooltip interaction */
    overflow: hidden; /* Clip labels if they overflow */
    border: 1px solid rgba(255, 255, 255, 0.1); /* Subtle border */
}
.heatmap-cell:hover {
    transform: scale(1.05);
    z-index: 1; /* Bring to front on hover */
    box-shadow: 0 0 8px rgba(79, 209, 197, 0.5);
}


.heatmap-hour-label {
    font-size: 0.7rem;
    color: rgba(255, 255, 255, 0.7);
    position: absolute;
    top: 3px;
    left: 4px;
    line-height: 1;
     pointer-events: none; /* Prevent label from interfering with hover */
}

/* Optional: display count inside cell */
/* .heatmap-count-label {
    font-size: 0.9rem;
    font-weight: bold;
    color: rgba(255, 255, 255, 0.9);
} */


.no-data {
  text-align: center;
  padding: 30px;
  color: var(--text-secondary);
  font-style: italic;
  flex-grow: 1;
  display: flex;
  justify-content: center;
  align-items: center;
}

.heatmap-legend {
    display: flex;
    align-items: center;
    justify-content: center;
    margin-top: 10px; /* Space above legend */
    flex-shrink: 0; /* Prevent legend from shrinking */
    padding-bottom: 5px;
}

.legend-label {
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin: 0 8px;
}

.legend-gradient {
    width: 100px;
    height: 10px;
    border-radius: 5px;
    /* Updated gradient to better match the calculated colors */
    background: linear-gradient(to right,
        rgba(13, 25, 42, 0.5), /* Start color (intensity 0) */
        rgba(100, 180, 255, 0.4), /* ~ Intensity 0.25 */
        rgba(79, 209, 197, 0.8),  /* ~ Intensity 0.6 */
        rgba(50, 255, 50, 1)   /* ~ Intensity 1.0 */
    );
    border: 1px solid rgba(255, 255, 255, 0.2);
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
.resize-e { display: none; }
.resize-s {
  bottom: 0; left: 0; width: 100%; height: 8px; cursor: s-resize;
}
.resize-se {
   bottom: 0; right: 0; width: 15px; height: 15px; cursor: s-resize; border-radius: 0 0 5px 0;
}

</style> 