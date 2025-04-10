<template>
  <div>
    <div class="panel-title">
      <span class="panel-icon">📊</span>
      行为统计
      <div class="panel-decoration"></div>
    </div>
    <div class="stats-content">
      <div class="stat-item">
        <div class="stat-value cyber-value">
          {{ statistics?.total_behaviors || 0 }}
        </div>
        <div class="stat-label">总行为数</div>
      </div>
      <div class="stat-item">
        <div class="stat-value cyber-value">
          {{ statistics?.unique_behaviors || 0 }}
        </div>
        <div class="stat-label">行为类型</div>
      </div>
      <div class="stat-item">
        <div class="stat-value cyber-value highlight">
          {{ statistics?.most_frequent || "无" }}
        </div>
        <div class="stat-label">最频繁行为</div>
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
import { defineProps, defineEmits } from "vue";

defineProps({
  statistics: {
    type: Object,
    required: true,
    default: () => ({
      // Provide a default structure
      total_behaviors: 0,
      unique_behaviors: 0,
      most_frequent: "无",
    }),
  },
});

defineEmits(["start-resize"]);
</script>

<style scoped>
/* Styles extracted from BehaviorAnalysisPage.vue related to the stats panel */

.panel-title {
  /* Basic structure provided */
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

.stats-content {
  display: flex;
  justify-content: space-around;
  align-items: center;
  flex: 1;
  height: calc(100% - 45px); /* Fill remaining height */
  overflow: auto;
  padding: 15px;
  background-color: rgba(10, 25, 47, 0.7);
  border-radius: 0 0 5px 5px;
}

.stat-item {
  text-align: center;
  padding: 15px;
  position: relative;
  z-index: 1;
}

/* 统计项装饰 */
.stat-item::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(79, 209, 197, 0.05);
  border-radius: 8px;
  z-index: -1;
  transform: scale(0.9);
  transition: all 0.3s ease;
}

.stat-item:hover::before {
  transform: scale(1);
  background: rgba(79, 209, 197, 0.1);
}

.stat-value {
  font-size: 2.5rem;
  font-weight: bold;
  color: var(--cyber-neon);
  margin-bottom: 5px;
  text-shadow: 0 0 10px rgba(79, 209, 197, 0.5);
}

/* 数值动画效果 */
.cyber-value {
  position: relative;
  display: inline-block;
}

.cyber-value::after {
  content: "";
  position: absolute;
  bottom: -3px;
  left: 0;
  width: 100%;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    var(--cyber-neon),
    transparent
  );
}

.stat-label {
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.highlight {
  color: #fc8181; /* Use a specific highlight color or variable */
  text-shadow: 0 0 10px rgba(252, 129, 129, 0.5);
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

.resize-e {
  top: 0;
  right: 0;
  width: 5px;
  height: 100%;
  cursor: e-resize;
}

.resize-s {
  bottom: 0;
  left: 0;
  width: 100%;
  height: 5px;
  cursor: s-resize;
}

.resize-se {
  bottom: 0;
  right: 0;
  width: 15px;
  height: 15px;
  cursor: se-resize;
  border-radius: 0 0 5px 0;
}
</style>
