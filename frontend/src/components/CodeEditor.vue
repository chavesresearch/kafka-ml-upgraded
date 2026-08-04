<script setup lang="ts">
// Monaco-backed code field, used anywhere the app previously used a plain
// <textarea> for user-authored code (model definitions, Tasmota Berry
// scripts). Syncs with v-model and follows the app's light/dark theme.
//
// Monaco (even the trimmed core-only build, see monacoEnvironment.ts) is a
// few hundred kB — too much to put on every page's critical path. Both the
// worker/language setup and the editor module itself are loaded with a
// runtime `import()` from onMounted, so they only download when a screen
// that actually uses this component is visited, as their own async chunk.
import { ref, shallowRef, onMounted, onBeforeUnmount, watch } from 'vue'
import type * as Monaco from 'monaco-editor/esm/vs/editor/editor.api'
import { useTheme } from '../theme'

const props = withDefaults(
  defineProps<{
    modelValue: string
    language?: string
    height?: string
    placeholder?: string
    readOnly?: boolean
  }>(),
  {
    language: 'plaintext',
    height: '260px',
    placeholder: '',
    readOnly: false
  }
)

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const container = ref<HTMLDivElement | null>(null)
const editor = shallowRef<Monaco.editor.IStandaloneCodeEditor | null>(null)
const isEmpty = ref(props.modelValue.length === 0)
const { isDark } = useTheme()

let monacoApi: typeof Monaco | null = null

function monacoTheme(): string {
  return isDark.value ? 'vs-dark' : 'vs'
}

onMounted(async () => {
  const [, api] = await Promise.all([
    import('../monacoEnvironment'),
    import('monaco-editor/esm/vs/editor/editor.api')
  ])
  monacoApi = api
  if (!container.value) return // unmounted while the chunk was loading

  const instance = monacoApi.editor.create(container.value, {
    value: props.modelValue,
    language: props.language,
    theme: monacoTheme(),
    readOnly: props.readOnly,
    minimap: { enabled: false },
    fontSize: 13,
    fontFamily: "'SFMono-Regular', ui-monospace, Menlo, Consolas, monospace",
    lineNumbersMinChars: 3,
    scrollBeyondLastLine: false,
    automaticLayout: true,
    tabSize: 4,
    padding: { top: 12, bottom: 12 },
    renderLineHighlight: 'none',
    overviewRulerLanes: 0,
    hideCursorInOverviewRuler: true,
    scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8 }
  })
  editor.value = instance

  instance.onDidChangeModelContent(() => {
    const value = instance.getValue()
    isEmpty.value = value.length === 0
    emit('update:modelValue', value)
  })
})

onBeforeUnmount(() => {
  editor.value?.dispose()
})

// External updates to modelValue (e.g. loading an existing model) that
// didn't originate from this editor's own change event.
watch(
  () => props.modelValue,
  (value) => {
    if (editor.value && editor.value.getValue() !== value) {
      editor.value.setValue(value)
    }
    isEmpty.value = value.length === 0
  }
)

watch(
  () => props.language,
  (language) => {
    const model = editor.value?.getModel()
    if (model && monacoApi) monacoApi.editor.setModelLanguage(model, language)
  }
)

watch(isDark, () => {
  monacoApi?.editor.setTheme(monacoTheme())
})
</script>

<template>
  <div class="code-field">
    <div class="code-field-header">
      <span class="lang-badge">{{ language }}</span>
    </div>
    <div class="code-editor-wrap" :style="{ height }">
      <div ref="container" class="code-editor"></div>
      <div v-if="isEmpty && placeholder" class="code-placeholder">{{ placeholder }}</div>
    </div>
  </div>
</template>

<style scoped>
.code-editor-wrap {
  position: relative;
  width: 100%;
}

.code-editor {
  width: 100%;
  height: 100%;
}

.code-placeholder {
  position: absolute;
  top: 12px;
  left: 52px;
  right: 12px;
  color: var(--text-color-secondary);
  font-family: 'SFMono-Regular', ui-monospace, Menlo, Consolas, monospace;
  font-size: 13px;
  white-space: pre-wrap;
  pointer-events: none;
  opacity: 0.65;
}
</style>
