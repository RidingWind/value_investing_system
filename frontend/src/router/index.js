import { createRouter, createWebHistory } from 'vue-router'

// 懒加载页面组件
const ParamsManagement = () => import('@/views/ParamsManagement.vue')
const AuditLog = () => import('@/views/AuditLog.vue')

const routes = [
  {
    path: '/',
    redirect: '/params'  // 默认跳转到参数管理页面
  },
  {
    path: '/params',
    name: 'ParamsManagement',
    component: () => import('@/views/ParamsManagement.vue'),
    meta: { title: '参数配置' }
  },
  {
    path: '/audit',
    name: 'AuditLog',
    component: () => import('@/views/AuditLog.vue'),
    meta: { title: '审计日志' }
  },
  {
    path: '/market-data',
    name: 'marketData',
    component: () => import('@/views/MarketData.vue'),
    meta: { title: '行情数据管理' }
  },
  {
    path: '/financial-data',
    name: 'FinancialData',
    component: () => import('@/views/FinancialData.vue'),
    meta: { title: '财务数据采集' }
  },
  {
    path: '/financial-config',
    name: 'FinancialConfig',
    component: () => import('@/views/FinancialConfig.vue'),
    meta: { title: '财务数据映射' }
  },
  // router/index.js
  {
    path: '/stock/daily',
    name: 'StockDaily',
    component: () => import('@/views/StockDaily.vue'),
    props: route => ({ symbol: route.query.symbol })
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router

