// Side-effect module: wires Monaco's web worker under Vite, and registers
// only the languages this app actually needs (model code is Python, Tasmota
// Berry scripts get a real hand-written Berry grammar - see
// berryLanguage.ts for why this used to be mislabeled as Lua and isn't
// anymore).
//
// Deliberately importing from 'monaco-editor/esm/vs/editor/editor.api'
// (core editor only) instead of the bare 'monaco-editor' package: the
// latter resolves to editor.main.js, which unconditionally bundles every
// basic language (40+: dart, csharp, sql, php, ruby, solidity, ...) plus
// the full TypeScript/CSS/HTML/JSON rich language services — several MB
// we'd never use. Import this once, before any CodeEditor is mounted
// (done lazily from CodeEditor.tsx, not from main.tsx). Berry has no
// built-in Monaco grammar to pull in this same lazy-contribution way, so
// it's registered directly against the public monaco.languages API instead
// - this is the same 'editor.api' module CodeEditor.tsx itself imports, so
// this adds no extra bundle weight, just one more consumer of the same chunk.
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api'
import 'monaco-editor/esm/vs/basic-languages/python/python.contribution'
import { berryLanguageConfiguration, berryLanguageDefinition } from './berryLanguage'

self.MonacoEnvironment = {
  getWorker() {
    return new EditorWorker()
  },
}

monaco.languages.register({ id: 'berry', extensions: ['.be'], aliases: ['Berry', 'berry'] })
monaco.languages.setLanguageConfiguration('berry', berryLanguageConfiguration)
monaco.languages.setMonarchTokensProvider('berry', berryLanguageDefinition)
