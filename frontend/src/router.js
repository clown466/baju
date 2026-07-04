import { createRouter, createWebHashHistory } from 'vue-router'
import ProjectDetail from './views/ProjectDetail.vue'
import ProjectList from './views/ProjectList.vue'

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: ProjectList },
    { path: '/projects/:pid', component: ProjectDetail, props: true },
  ],
})
