/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const component: DefineComponent<Record<string, any>, Record<string, any>, any>
  export default component
}

declare module '@fontsource-variable/inter'

interface Window {
  MonacoEnvironment?: import('monaco-editor').Environment
}
