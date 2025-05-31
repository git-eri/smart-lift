import { createRouter, createWebHistory } from 'vue-router'
import MainView from './views/MainView.vue'
import SimulatorView from './views/SimulatorView.vue'
import AdminPanel from './views/AdminPanel.vue'

const routes = [
  { path: '/', component: MainView },
  { path: '/simulator', component: SimulatorView },
  { path: '/admin', component: AdminPanel }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
