<template>
  <el-container style="min-height: 100vh;">
    <!-- 顶部导航栏 -->
    <el-header height="60px" style="background: #545c64; color: #fff; display: flex; align-items: center; padding: 0 20px;">
      <!-- 左侧标题区域，固定宽度防止挤压 -->
      <div style="min-width: 220px; margin-right: 10px;">
        <h3 style="margin: 0; white-space: nowrap;">📈 价值投资选股系统</h3>
      </div>

      <el-menu
        :default-active="activeMenu"
        mode="horizontal"
        router
        background-color="#545c64"
        text-color="#ddd"
        active-text-color="#ffd04b"
        style="flex: 1; border-bottom: none; justify-content: flex-start;"
      >
        <!-- 行情数据 -->
        <el-menu-item index="/market-data">
          <el-icon><TrendCharts /></el-icon>
          <span>行情数据</span>
        </el-menu-item>

        <!-- 财务数据（二级菜单） -->
        <el-sub-menu index="financial">
          <template #title>
            <el-icon><Money /></el-icon>
            <span>财务数据</span>
          </template>
          <el-menu-item index="/financial-data">
            <el-icon><Coin /></el-icon>
            <span>数据采集</span>
          </el-menu-item>
          <el-menu-item index="/financial-config">
            <el-icon><Setting /></el-icon>
            <span>数据映射</span>
          </el-menu-item>
        </el-sub-menu>

        <!-- 参数配置 -->
        <el-menu-item index="/params">
          <el-icon><Tools /></el-icon>
          <span>参数配置</span>
        </el-menu-item>

        <!-- 审计日志 -->
        <el-menu-item index="/audit">
          <el-icon><Monitor /></el-icon>
          <span>审计日志</span>
        </el-menu-item>

        <!-- 选股查询 -->
        <el-menu-item index="/stock-screen" disabled>
          <el-icon><Search /></el-icon>
          <span>选股查询</span>
        </el-menu-item>

        <!-- 持仓管理 -->
        <el-menu-item index="/portfolio" disabled>
          <el-icon><PieChart /></el-icon>
          <span>持仓管理</span>
        </el-menu-item>
      </el-menu>
    </el-header>

    <!-- 主体内容区域 -->
    <el-main>
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  TrendCharts, Money, Coin, Setting,
  Tools, Monitor, Search, PieChart
} from '@element-plus/icons-vue'

const route = useRoute()
const activeMenu = computed(() => route.path)
</script>

<style>
html, body, #app {
  margin: 0;
  padding: 0;
  height: 100%;
}
</style>
