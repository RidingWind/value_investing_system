import { createApp } from 'vue'
import App from './App.vue'
import router from './router'            // 引入路由
import ElementPlus from 'element-plus'    // UI 框架
import 'element-plus/dist/index.css'      // 样式文件
import * as ElementPlusIconsVue from '@element-plus/icons-vue'  // 图标库（如需）

const app = createApp(App)

// 注册所有图标（可选）
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(ElementPlus)    // 注册 Element Plus
app.use(router)         // 注册路由

app.mount('#app')
