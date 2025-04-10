<template>
  <div>
    <div class="panel-title">
      <span class="panel-icon">📝</span>
      行为记录
      <div class="panel-decoration"></div>
    </div>
    <div class="behavior-list">
      <div
        v-for="behavior in behaviors"
        :key="behavior.id"
        class="behavior-item cyber-list-item"
      >
        <div class="behavior-time">{{ formatTime(behavior.timestamp) }}</div>
        <div class="behavior-type">{{ behavior.type }}</div>
        <div class="behavior-bar-container">
          <div
            class="behavior-bar"
            :style="{ width: calculateBarWidth(behavior.count) }"
            :title="`${behavior.count}次`"
          >
            <span class="bar-value-label">{{ behavior.count }}</span>
          </div>
        </div>
      </div>
      <div v-if="!behaviors || behaviors.length === 0" class="no-data">
        暂无行为数据
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
import { defineProps, defineEmits, computed } from "vue";

const props = defineProps({
  behaviors: {
    type: Array,
    required: true,
    default: () => [],
  },
});

defineEmits(["start-resize"]);

const maxCount = computed(() => {
  if (!props.behaviors || props.behaviors.length === 0) return 10;
  return Math.max(...props.behaviors.map((b) => b.count), 1);
});

function calculateBarWidth(count) {
  const scaleFactor = 90;
  const percentage = (count / maxCount.value) * scaleFactor;
  return `${Math.max(percentage, 15)}%`;
}

function formatTime(timestamp) {
  if (!timestamp) return "";
  try {
    const dateStr = timestamp.includes("T")
      ? timestamp
      : timestamp.replace(" ", "T");
    const date = new Date(dateStr);
    if (isNaN(date)) {
      console.warn("Invalid date format for timestamp:", timestamp);
      return timestamp;
    }
    return `${date.getHours().toString().padStart(2, "0")}:${date
      .getMinutes()
      .toString()
      .padStart(2, "0")}`;
  } catch (error) {
    console.error("Error formatting time:", timestamp, error);
    return timestamp;
  }
}
</script>

<style scoped>
/* Panel Title and List Styles remain the same */
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
.behavior-list {
  overflow-y: auto;
  height: calc(100% - 45px);
  flex-grow: 1;
  scrollbar-width: thin;
  scrollbar-color: var(--cyber-neon) rgba(13, 25, 42, 0.5);
  background-color: rgba(10, 25, 47, 0.7);
  border-radius: 0 0 5px 5px;
}
.behavior-list::-webkit-scrollbar {
  width: 6px;
}
.behavior-list::-webkit-scrollbar-track {
  background: rgba(13, 25, 42, 0.5);
}
.behavior-list::-webkit-scrollbar-thumb {
  background-color: var(--cyber-neon);
  border-radius: 3px;
}
.behavior-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 15px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  transition: background-color 0.2s ease;
  gap: 15px;
}
.behavior-item:hover {
  background-color: rgba(79, 209, 197, 0.1);
}
.cyber-list-item {
  position: relative;
  overflow: visible;
}
.cyber-list-item::before {
  content: ">";
  position: absolute;
  left: 5px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--cyber-neon);
  opacity: 0;
  transition: opacity 0.2s ease;
}
.cyber-list-item:hover::before {
  opacity: 1;
}
.behavior-time {
  color: var(--text-secondary);
  font-family: monospace;
  min-width: 50px;
  flex-shrink: 0;
}
.behavior-type {
  font-weight: bold;
  color: var(--text-primary);
  flex-grow: 1;
  margin: 0;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Bar chart styles: RTL Growth, Label inside Start */
.behavior-bar-container {
  width: 120px;
  height: 18px;
  border-radius: 9px;
  position: relative;
  flex-shrink: 0;
  background-color: rgba(0, 0, 0, 0.2); /* Track color */
  overflow: hidden; /* Clip the bar */
}

.behavior-bar {
  height: 100%;
  background: linear-gradient(90deg, #1e6bdf, #4fd1c5);
  border-radius: 9px;
  transition: width 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
  box-shadow: inset 0 1px 2px rgba(255, 255, 255, 0.1),
    inset 0 -1px 2px rgba(0, 0, 0, 0.2);
  margin-left: auto; /* RTL Growth */
  display: flex;
  align-items: center;
  justify-content: flex-start; /* Position label at the start (left) */
}

.bar-value-label {
  font-size: 0.85em;
  color: rgba(255, 255, 255, 0.9);
  font-weight: bold;
  line-height: 1;
  white-space: nowrap;
  flex-shrink: 0;
  padding-left: 6px; /* Padding from the left edge */
  text-shadow: 0 0 2px rgba(0, 0, 0, 0.5);
}

.no-data {
  text-align: center;
  padding: 30px;
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
.resize-w {
  top: 0;
  left: 0;
  width: 5px;
  height: 100%;
  cursor: w-resize;
}
.resize-s {
  bottom: 0;
  left: 0;
  width: 100%;
  height: 5px;
  cursor: s-resize;
}
.resize-sw {
  bottom: 0;
  left: 0;
  width: 15px;
  height: 15px;
  cursor: sw-resize;
  border-radius: 0 0 0 5px;
}
</style>
