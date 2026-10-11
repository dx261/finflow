import { createApp } from 'vue'
import { createPinia } from 'pinia'
import {
  Calendar,
  Checked,
  Document,
  List,
  Odometer,
  PieChart,
  Setting,
  TrendCharts,
  UploadFilled,
  Wallet,
} from '@element-plus/icons-vue'

import './style.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)
const icons = {
  Calendar,
  Checked,
  Document,
  List,
  Odometer,
  PieChart,
  Setting,
  TrendCharts,
  UploadFilled,
  Wallet,
}
for (const [key, component] of Object.entries(icons)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.mount('#app')
