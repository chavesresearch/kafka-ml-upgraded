// Test-only stand-in for the real `monaco-editor` package (aliased in via
// vite.config.ts's `test.alias`, test runs only).
//
// Real Monaco needs a browser: Workers, canvas metrics, ResizeObserver-driven
// layout. None of that is meaningful under jsdom, and the package's
// module-only (no "exports"/"main") package.json doesn't resolve under
// Vitest's SSR module graph anyway. This stub implements just enough of the
// `monaco.editor` surface that CodeEditor.vue touches, so router.test.ts can
// still lazily-import every view (including ones using CodeEditor) without
// mounting a real editor.
import { vi } from 'vitest'

class FakeModel {
  private language: string
  constructor(language: string) {
    this.language = language
  }
  getLanguage() {
    return this.language
  }
  setLanguage(language: string) {
    this.language = language
  }
}

class FakeEditor {
  private value: string
  private model: FakeModel
  private listeners: Array<() => void> = []

  constructor(value: string, language: string) {
    this.value = value
    this.model = new FakeModel(language)
  }
  getValue() {
    return this.value
  }
  setValue(value: string) {
    this.value = value
  }
  getModel() {
    return this.model
  }
  onDidChangeModelContent(listener: () => void) {
    this.listeners.push(listener)
    return { dispose: () => {} }
  }
  dispose() {}
}

export const editor = {
  create: vi.fn((_container: HTMLElement, options: { value?: string; language?: string } = {}) => {
    return new FakeEditor(options.value ?? '', options.language ?? 'plaintext')
  }),
  setTheme: vi.fn(),
  setModelLanguage: vi.fn((model: FakeModel, language: string) => model.setLanguage(language))
}
