<script setup>
import HelloWorld from './components/HelloWorld.vue'
import StatusBar from './components/StatusBar.vue'
</script>

<template>
  <div id="app-container">
    <!-- AppHeader should have height: 80px; flex-shrink: 0; -->
    <AppHeader /> 

    <main>
      <!-- router-view loads MonitoringPage here -->
      <router-view />
    </main>

    <!-- StatusBar has position: fixed; height: 40px; -->
    <StatusBar />
  </div>
</template>

<style>
/* 全局样式可以放在这里，或者 src/style.css */
html, body {
  height: 100%; /* 确保 html 和 body 也是 100% 高 */
  overflow: hidden; /* 隐藏 html 和 body 的滚动条 */
  margin: 0;
  padding: 0;
}

body {
  font-family: Inter, system-ui, Avenir, Helvetica, Arial, sans-serif;
  line-height: 1.5;
  font-weight: 400;
  color-scheme: light dark;
  color: rgba(255, 255, 255, 0.87);
  background-color: var(--dark-bg); /* 基础背景色 */
  font-synthesis: none;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#app-container {
  display: flex;
  flex-direction: column;
  height: 100vh; /* 严格限制高度为视口高度 */
  width: 100vw;
  overflow: hidden; /* 隐藏容器滚动条 */
  padding: 0;
  margin: 0;
  box-sizing: border-box;
}

main {
  flex: 1; /* 让 main 占据 Header 和 Footer 之间的所有可用空间 */
  width: 100%;
  padding: 0; /* 移除所有 padding */
  padding-bottom: 40px; /* Add padding equal to StatusBar height */
  margin: 0;
  overflow: hidden; /* 防止 main 内部意外溢出导致滚动 */
  display: flex; /* 让 main 成为 flex 容器，其子元素 (router-view 加载的页面) 可以填充它 */
  box-sizing: border-box; /* Include padding in size calculation */
}

/* 视觉上隐藏滚动条 (如果某些子组件需要内部滚动但不想显示滚动条) */
::-webkit-scrollbar {
  display: none;
}
/* Firefox */
* { /* 或者更具体的选择器 */
  scrollbar-width: none;
}
/* IE and Edge */
* { /* 或者更具体的选择器 */
  -ms-overflow-style: none;
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
