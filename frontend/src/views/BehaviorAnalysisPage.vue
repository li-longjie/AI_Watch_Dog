<template>
  <div class="behavior-analysis-page">
    <AppHeader />

    <div class="content-container">
      <div class="page-header">
        <h1>行为分析页面</h1>
      </div>

      <div class="loading-message" v-if="loading">
        <div class="cyber-spinner"></div>
        <p>加载行为数据中...</p>
      </div>

      <draggable
        v-if="!loading"
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
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, shallowRef } from "vue";
import AppHeader from "../components/AppHeader.vue";
import draggable from "vuedraggable";

// Import the new components
import BABehaviorStats from "../components/BABehaviorStats.vue";
import BABehaviorList from "../components/BABehaviorList.vue";
import BABehaviorChart from "../components/BABehaviorChart.vue";
import BARealTimeMonitoring from "../components/BARealTimeMonitoring.vue";

const loading = ref(true);
const behaviorData = ref({
  behaviors: [],
  statistics: {
    total_behaviors: 0,
    unique_behaviors: 0,
    most_frequent: "",
  },
});

// Panel order - Load from localStorage or use default
const defaultPanelOrder = [
  { id: 4 }, // RealTimeMonitoring
  { id: 2 }, // BehaviorList
  { id: 3 }, // BehaviorChart
  { id: 1 }, // BehaviorStats
];
const panelOrder = ref(
  JSON.parse(
    localStorage.getItem("baPanelOrder") || JSON.stringify(defaultPanelOrder)
  )
);

// Panel sizes - Load from localStorage or use default
const defaultPanelSizes = {
  1: { width: "calc(50% - 10px)", height: "300px" },
  2: { width: "calc(50% - 10px)", height: "300px" },
  3: { width: "calc(50% - 10px)", height: "300px" },
  4: { width: "calc(50% - 10px)", height: "300px" },
};
const panelSizes = ref(
  JSON.parse(
    localStorage.getItem("baPanelSizes") || JSON.stringify(defaultPanelSizes)
  )
);

// Store panel refs dynamically
const panelRefs = shallowRef({});

// Map panel IDs to component names and CSS classes
const componentMap = {
  1: { component: BABehaviorStats, class: "behavior-stats-panel" },
  2: { component: BABehaviorList, class: "behavior-list-panel" },
  3: { component: BABehaviorChart, class: "behavior-chart-panel" },
  4: { component: BARealTimeMonitoring, class: "behavior-analysis-panel" }, // Kept old class name for now
};

function getComponentName(panelId) {
  return componentMap[panelId]?.component;
}

function getPanelClass(panelId) {
  return componentMap[panelId]?.class || "";
}

// Provide props to components
function getComponentProps(panelId) {
  switch (panelId) {
    case 1:
      return { statistics: behaviorData.value.statistics };
    case 2:
      return { behaviors: behaviorData.value.behaviors };
    case 3:
      return { behaviors: behaviorData.value.behaviors };
    case 4:
      return {}; // BARealTimeMonitoring manages its own state
    default:
      return {};
  }
}

// --- Resizing Logic (kept from original) ---
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
  // Return default if size info is missing (e.g., after clearing localStorage)
  const size = panelSizes.value[panelId] || defaultPanelSizes[panelId];
  return {
    // Width is now controlled by the grid, height is controlled by state
    // width: size.width,
    height: size.height,
    position: "relative", // Keep relative positioning for handles
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
    targetElement: panelElement, // Store the element being resized
  };

  panelElement.classList.add("resizing");
  document.body.style.cursor = getResizeCursor(direction); // Set cursor on body
  document.body.style.userSelect = "none"; // Prevent text selection during resize

  document.addEventListener("mousemove", handleResize);
  document.addEventListener("mouseup", stopResize);
}

function handleResize(event) {
  if (!resizing.value.active) return;

  const { panelId, direction, startX, startY, startWidth, startHeight } =
    resizing.value;

  let newWidth = startWidth;
  let newHeight = startHeight;
  const deltaX = event.clientX - startX;
  const deltaY = event.clientY - startY;

  if (direction.includes("e")) {
    newWidth = startWidth + deltaX;
  }
  if (direction.includes("w")) {
    newWidth = startWidth - deltaX;
    // Note: Resizing from 'w' might require position adjustments if not using grid/flex layout correctly
  }
  if (direction.includes("s")) {
    newHeight = startHeight + deltaY;
  }
  if (direction.includes("n")) {
    newHeight = startHeight - deltaY;
    // Note: Resizing from 'n' might require position adjustments
  }

  // Apply minimum dimensions
  newWidth = Math.max(250, newWidth); // Increased min width
  newHeight = Math.max(200, newHeight); // Increased min height

  // Update panel size state
  panelSizes.value[panelId] = {
    width: `${newWidth}px`,
    height: `${newHeight}px`,
  };

  // Optional: Apply style directly for smoother feedback, though Vue reactivity should handle it
  // if (resizing.value.targetElement) {
  //   resizing.value.targetElement.style.width = `${newWidth}px`;
  //   resizing.value.targetElement.style.height = `${newHeight}px`;
  // }
}

function stopResize() {
  if (!resizing.value.active) return;

  if (resizing.value.targetElement) {
    resizing.value.targetElement.classList.remove("resizing");
  }

  // Save sizes to localStorage
  localStorage.setItem("baPanelSizes", JSON.stringify(panelSizes.value));

  resizing.value.active = false;
  resizing.value.targetElement = null;
  document.body.style.cursor = ""; // Reset cursor
  document.body.style.userSelect = ""; // Reset user select

  document.removeEventListener("mousemove", handleResize);
  document.removeEventListener("mouseup", stopResize);
}

function getResizeCursor(direction) {
  switch (direction) {
    case "n":
      return "n-resize";
    case "s":
      return "s-resize";
    case "e":
      return "e-resize";
    case "w":
      return "w-resize";
    case "ne":
      return "ne-resize";
    case "nw":
      return "nw-resize";
    case "se":
      return "se-resize";
    case "sw":
      return "sw-resize";
    default:
      return "default";
  }
}

// --- End Resizing Logic ---

// Fetch initial data (kept from original, uses mock data)
async function fetchBehaviorData() {
  try {
    loading.value = true;
    // Using mock data
    await new Promise((resolve) => setTimeout(resolve, 1000));

    behaviorData.value = {
      behaviors: [
        { id: 1, type: "专注工作", count: 5, timestamp: "2025-03-28 20:10:00" },
        { id: 2, type: "吃东西", count: 3, timestamp: "2025-03-28 20:12:30" },
        { id: 3, type: "喝水", count: 2, timestamp: "2025-03-28 20:15:45" },
        { id: 4, type: "玩手机", count: 4, timestamp: "2025-03-28 20:18:20" },
        { id: 5, type: "睡觉", count: 1, timestamp: "2025-03-28 20:20:00" },
      ],
      statistics: {
        total_behaviors: 15,
        unique_behaviors: 5,
        most_frequent: "专注工作",
      },
    };
    loading.value = false;
  } catch (error) {
    console.error("获取行为数据出错:", error);
    // Load mock data even on error
    behaviorData.value = {
      behaviors: [
        { id: 1, type: "专注工作", count: 5, timestamp: "2025-03-28 20:10:00" },
        { id: 2, type: "吃东西", count: 3, timestamp: "2025-03-28 20:12:30" },
        { id: 3, type: "喝水", count: 2, timestamp: "2025-03-28 20:15:45" },
        { id: 4, type: "玩手机", count: 4, timestamp: "2025-03-28 20:18:20" },
        { id: 5, type: "睡觉", count: 1, timestamp: "2025-03-28 20:20:00" },
      ],
      statistics: {
        total_behaviors: 15,
        unique_behaviors: 5,
        most_frequent: "专注工作",
      },
    };
    loading.value = false;
  }
}

// Save panel order to localStorage
function savePanelOrder() {
  localStorage.setItem("baPanelOrder", JSON.stringify(panelOrder.value));
}

onMounted(async () => {
  await fetchBehaviorData();
  // Note: WebSocket connection is now handled within BARealTimeMonitoring
});

onUnmounted(() => {
  // Remove global listeners if they were added outside the resize logic
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
  overflow: hidden; /* Prevent body scroll */
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
  margin: -35px auto; /* Reduced top margin, kept bottom */
  width: calc(100% - 40px); /* Account for padding */
  display: flex;
  flex-direction: column;
}

.page-header {
  text-align: center;
  margin-bottom: -20px; /* Reduced space below header */
  position: relative; /* For pseudo-elements */
  width: fit-content; /* Fit content width */
  align-self: center; /* Center header */
}

.page-header h1 {
  color: var(--cyber-neon);
  font-size: 1.8rem;
  text-shadow: 0 0 10px rgba(79, 209, 197, 0.5);
  display: inline-block;
  letter-spacing: 1px;
  white-space: nowrap;
  position: relative;
  padding-bottom: 5px; /* Space for underline */
}

/* Title decoration */
.page-header h1::before {
  content: "// ";
  color: rgba(79, 209, 197, 0.7);
  font-weight: normal;
}

.page-header h1::after {
  content: "";
  position: absolute;
  bottom: 0;
  left: 50%; /* Start from center */
  transform: translateX(-50%);
  width: 80%; /* Underline width */
  height: 2px;
  background: linear-gradient(
    90deg,
    transparent,
    var(--cyber-neon),
    transparent
  );
  box-shadow: 0 0 8px var(--cyber-neon);
}

.loading-message {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 300px;
  color: var(--text-secondary);
  font-size: 1.2rem;
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
  /* display: flex; */ /* Changed from flex */
  /* flex-wrap: wrap; */
  display: grid; /* Use Grid for layout */
  grid-template-columns: repeat(2, 1fr); /* Create 2 equal columns */
  /* grid-auto-rows: minmax(200px, auto); /* Let rows grow, but have a min height */
  /* Let height be controlled by panelSizes state */
  gap: 0px 20px; /* Row gap 0, Column gap 20px */
  padding: 10px; /* Restore padding */
  flex: 1; /* Allow container to grow */
}

/* Default Panel Styles (can be overridden by components if needed) */
.panel {
  /* Removed flex width calculation, grid handles width */
  /* width and height are now set via :style binding */
  margin: 0 0 -1.1px 0 !important; /* Try slightly larger negative margin */
  box-sizing: border-box; /* Ensure padding/border are included in height */
  background-color: rgba(10, 25, 47, 0.7);
  /* border: 1px solid rgba(79, 209, 197, 0.3); */ /* Remove unified border */
  /* Apply borders individually, excluding bottom */
  border-top: 1px solid rgba(79, 209, 197, 0.3);
  border-left: 1px solid rgba(79, 209, 197, 0.3);
  border-right: 1px solid rgba(79, 209, 197, 0.3);
  border-radius: 5px;
  box-shadow: 0 0 15px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  overflow: hidden; /* Important for content clipping */
  transition: box-shadow 0.3s ease, border-color 0.3s ease;
  position: relative; /* Ensure resize handles are positioned correctly */
  transform: translateZ(0); /* Force hardware acceleration / new layer */
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
  right: -1px; /* Adjusted position */
  width: 30px;
  height: 30px;
  border-top: 2px solid var(--cyber-neon);
  border-right: 2px solid var(--cyber-neon);
  opacity: 0.7;
  pointer-events: none;
  border-radius: 0 5px 0 0; /* Match panel radius */
}

.cyber-panel::after {
  content: "";
  position: absolute;
  bottom: -1px;
  left: -1px; /* Adjusted position */
  width: 30px;
  height: 30px;
  border-bottom: 2px solid var(--cyber-neon);
  border-left: 2px solid var(--cyber-neon);
  opacity: 0.7;
  pointer-events: none;
  border-radius: 0 0 0 5px; /* Match panel radius */
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
  /* Optional: Style for the element being actively dragged */
  transform: scale(1.02);
  z-index: 30;
}

/* Resizing Styles */
.panel.resizing {
  transition: none !important; /* Disable transitions during resize */
  border-color: rgba(79, 209, 197, 0.8);
  box-shadow: 0 0 10px rgba(79, 209, 197, 0.5);
  z-index: 15; /* Ensure resizing panel is above others */
}

/* Global resize handle styles (if not fully encapsulated in components) */
.resize-handle {
  position: absolute;
  background-color: transparent; /* Make handles invisible initially */
  z-index: 10;
  transition: background-color 0.2s ease;
}
.panel:hover .resize-handle {
  background-color: rgba(79, 209, 197, 0.1); /* Show on panel hover */
}
.resize-handle:hover {
  background-color: rgba(
    79,
    209,
    197,
    0.4
  ) !important; /* Highlight handle on hover */
}

/* Specific handle positions (ensure these match component implementations) */
.resize-e {
  top: 0;
  right: 0;
  width: 8px;
  height: 100%;
  cursor: e-resize;
}
.resize-w {
  top: 0;
  left: 0;
  width: 8px;
  height: 100%;
  cursor: w-resize;
}
.resize-s {
  bottom: 0;
  left: 0;
  width: 100%;
  height: 8px;
  cursor: s-resize;
}
.resize-n {
  top: 0;
  left: 0;
  width: 100%;
  height: 8px;
  cursor: n-resize;
}
.resize-se {
  bottom: 0;
  right: 0;
  width: 15px;
  height: 15px;
  cursor: se-resize;
  border-radius: 0 0 5px 0;
}
.resize-sw {
  bottom: 0;
  left: 0;
  width: 15px;
  height: 15px;
  cursor: sw-resize;
  border-radius: 0 0 0 5px;
}
.resize-ne {
  top: 0;
  right: 0;
  width: 15px;
  height: 15px;
  cursor: ne-resize;
  border-radius: 0 5px 0 0;
}
.resize-nw {
  top: 0;
  left: 0;
  width: 15px;
  height: 15px;
  cursor: nw-resize;
  border-radius: 5px 0 0 0;
}
</style>
