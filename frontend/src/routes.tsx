import { lazy } from 'react'
import type { RouteObject } from 'react-router-dom'
import { Navigate } from 'react-router-dom'

// Route paths are kept identical to the old Angular/Vue frontends so
// existing links keep working. Each view is code-split via React.lazy,
// same as the Vue router's per-route dynamic import.
const ModelList = lazy(() => import('./views/ModelList'))
const ModelView = lazy(() => import('./views/ModelView'))
const ConfigurationList = lazy(() => import('./views/ConfigurationList'))
const ConfigurationView = lazy(() => import('./views/ConfigurationView'))
const DeploymentView = lazy(() => import('./views/DeploymentView'))
const DeploymentList = lazy(() => import('./views/DeploymentList'))
const ResultList = lazy(() => import('./views/ResultList'))
const InferenceView = lazy(() => import('./views/InferenceView'))
const InferenceIoTView = lazy(() => import('./views/InferenceIoTView'))
const PlotView = lazy(() => import('./views/PlotView'))
const InferenceList = lazy(() => import('./views/InferenceList'))
const DatasourceList = lazy(() => import('./views/DatasourceList'))
const VisualizationView = lazy(() => import('./views/VisualizationView'))
const IoTDeviceList = lazy(() => import('./views/IoTDeviceList'))
const IoTDeviceView = lazy(() => import('./views/IoTDeviceView'))

export const routes: RouteObject[] = [
  { path: '/', element: <Navigate to="/models" replace /> },
  { path: '/models', element: <ModelList /> },
  { path: '/model-create', element: <ModelView /> },
  { path: '/model/:id', element: <ModelView /> },
  { path: '/configurations', element: <ConfigurationList /> },
  { path: '/configuration-create', element: <ConfigurationView /> },
  { path: '/configuration/:id', element: <ConfigurationView /> },
  { path: '/deploy/:id', element: <DeploymentView /> },
  { path: '/deployments', element: <DeploymentList /> },
  { path: '/deployments/:id', element: <DeploymentList /> },
  { path: '/results', element: <ResultList /> },
  { path: '/results/:id', element: <ResultList /> },
  { path: '/results/inference/:id', element: <InferenceView /> },
  { path: '/results/inference-iot/:id', element: <InferenceIoTView /> },
  { path: '/results/chart/:id', element: <PlotView /> },
  { path: '/inferences', element: <InferenceList /> },
  { path: '/datasources', element: <DatasourceList /> },
  { path: '/visualization', element: <VisualizationView /> },
  { path: '/devices', element: <IoTDeviceList /> },
  { path: '/devices-create', element: <IoTDeviceView /> },
  { path: '/device/:id', element: <IoTDeviceView /> },
]
