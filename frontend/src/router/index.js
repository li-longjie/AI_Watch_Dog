import { createRouter, createWebHistory } from 'vue-router'
import MonitoringPage from '../views/MonitoringPage.vue' // 我们稍后会创建这个文件
import BehaviorAnalysisPage from '../views/BehaviorAnalysisPage.vue' // 我们稍后会创建这个文件

const routes = [
  {
    path: '/',
    name: 'Monitoring',
    component: MonitoringPage
  },
  {
    path: '/behavior', // 匹配后端 /behavior_analysis 对应的页面
    name: 'BehaviorAnalysis',
    component: BehaviorAnalysisPage
  },
  {
    path: '/behavior-analysis',
    name: 'behavior-analysis',
    component: BehaviorAnalysisPage
  }
  // 未来可以添加更多路由
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

export default router 