import { createRouter, createWebHistory } from 'vue-router'
import CaseListView from '../views/CaseListView.vue'
import CaseDetailView from '../views/CaseDetailView.vue'

const routes = [
  {
    path: '/',
    redirect: '/cases',
  },
  {
    path: '/cases',
    name: 'cases',
    component: CaseListView,
  },
  {
    path: '/cases/:id',
    name: 'case-detail',
    component: CaseDetailView,
    props: true,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router