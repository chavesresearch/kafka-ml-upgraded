// Side-effect module: wires Monaco's web worker under Vite, and registers
// only the languages this app actually needs (model code is Python, Tasmota
// Berry scripts are highlighted as Lua — closest built-in grammar).
//
// Deliberately importing from 'monaco-editor/esm/vs/editor/editor.api'
// (core editor only) instead of the bare 'monaco-editor' package: the
// latter resolves to editor.main.js, which unconditionally bundles every
// basic language (40+: dart, csharp, sql, php, ruby, solidity, ...) plus
// the full TypeScript/CSS/HTML/JSON rich language services — several MB
// we'd never use. Import this once, before any CodeEditor is mounted
// (done lazily from CodeEditor.tsx, not from main.tsx).
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import 'monaco-editor/esm/vs/basic-languages/python/python.contribution'
import 'monaco-editor/esm/vs/basic-languages/lua/lua.contribution'

self.MonacoEnvironment = {
  getWorker() {
    return new EditorWorker()
  },
}
