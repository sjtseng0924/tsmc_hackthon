import { createRouter, createWebHistory } from 'vue-router'
import CaseDetailView from '../views/CaseDetailView.vue'

const routes = [
  {
    path: '/',
    redirect: '/analysis',
  },
  {
    path: '/analysis',
    name: 'analysis',
    component: () => import('../views/AnalysisView.vue'),
  },
  {
    path: '/cases/:id',
    name: 'case-detail',
    component: CaseDetailView,
    props: true,
  },
  {
    path: '/dashboard',
    redirect: '/analysis'
  },
  {
    path: '/cases',
    redirect: '/analysis'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router