<script setup>
import HelloWorld from './components/HelloWorld.vue'
import StatusBar from './components/StatusBar.vue'
</script>

<template>
  <div id="app-container">
    <!-- 这里可以放置全局 Header (如果需要) -->
    <!-- <AppHeader /> -->

    <main>
      <!-- 路由匹配到的组件将在这里渲染 -->
      <router-view />
    </main>

    <!-- 全局状态栏 -->
    <StatusBar />
  </div>
</template>

<style>
/* 全局样式可以放在这里，或者 src/style.css */
body {
  margin: 0;
  font-family: Inter, system-ui, Avenir, Helvetica, Arial, sans-serif;
  line-height: 1.5;
  font-weight: 400;
  color-scheme: light dark;
  color: rgba(255, 255, 255, 0.87);
  background-color: #242424; /* 基础背景色 */

  font-synthesis: none;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  width: 100vw;
}

#app-container {
  display: flex;
  flex-direction: column;
  flex-grow: 1; /* 使容器填满剩余空间 */
  width: 100%;
  max-width: 100%;
  padding: 0;
  margin: 0;
}

main {
  flex-grow: 1; /* 主要内容区域填满 Header 和 Footer 之间的空间 */
  padding-bottom: 50px; /* 为固定在底部的状态栏留出空间 */
  width: 100%;
  max-width: 100%;
  padding-left: 0;
  padding-right: 0;
  margin: 0;
}

/* 可以从旧的 main.css 或 behavior.css 迁移一些基础样式 */
:root {
  --primary: #4fd1c5;
  --dark-bg: #0a192f;
  --panel-bg: #172a45;
  --text-primary: #e6f1ff;
}

body {
  background-color: var(--dark-bg);
  color: var(--text-primary);
}

/* 可以在 src/style.css 中导入旧的 CSS 文件，或者逐步迁移样式 */
</style>
