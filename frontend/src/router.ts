import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

// Route paths are kept identical to the Angular app so existing links keep working.
const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/models' },
  { path: '/models', component: () => import('./views/ModelList.vue') },
  { path: '/model-create', component: () => import('./views/ModelView.vue') },
  { path: '/model/:id', component: () => import('./views/ModelView.vue') },
  { path: '/configurations', component: () => import('./views/ConfigurationList.vue') },
  { path: '/configuration-create', component: () => import('./views/ConfigurationView.vue') },
  { path: '/configuration/:id', component: () => import('./views/ConfigurationView.vue') },
  { path: '/deploy/:id', component: () => import('./views/DeploymentView.vue') },
  { path: '/deployments', component: () => import('./views/DeploymentList.vue') },
  { path: '/deployments/:id', component: () => import('./views/DeploymentList.vue') },
  { path: '/results', component: () => import('./views/ResultList.vue') },
  { path: '/results/:id', component: () => import('./views/ResultList.vue') },
  { path: '/results/inference/:id', component: () => import('./views/InferenceView.vue') },
  { path: '/results/inference-iot/:id', component: () => import('./views/InferenceIoTView.vue') },
  { path: '/results/chart/:id', component: () => import('./views/PlotView.vue') },
  { path: '/inferences', component: () => import('./views/InferenceList.vue') },
  { path: '/datasources', component: () => import('./views/DatasourceList.vue') },
  { path: '/visualization', component: () => import('./views/VisualizationView.vue') },
  { path: '/devices', component: () => import('./views/IoTDeviceList.vue') },
  { path: '/devices-create', component: () => import('./views/IoTDeviceView.vue') },
  { path: '/device/:id', component: () => import('./views/IoTDeviceView.vue') }
]

export default createRouter({
  history: createWebHistory(),
  routes
})
