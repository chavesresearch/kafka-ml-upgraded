// Monaco-backed code field, used anywhere the app needs more than a plain
// <textarea> for user-authored code (model definitions, Tasmota Berry
// scripts). Controlled component: `value`/`onChange`, follows the app's
// light/dark theme.
//
// Monaco (even the trimmed core-only build, see monacoEnvironment.ts) is a
// few hundred kB — too much to put on every page's critical path. Both the
// worker/language setup and the editor module itself are loaded with a
// runtime `import()` from a mount effect, so they only download when a
// screen that actually uses this component is visited, as their own async
// chunk (confirmed with `npm run build`'s per-chunk output — see the
// "Code editor" section of CLAUDE.md).
import { useEffect, useRef, useState } from 'react'
import type * as Monaco from 'monaco-editor/esm/vs/editor/editor.api'
import { useTheme } from '@/theme'
import { cn } from '@/lib/utils'

interface CodeEditorProps {
  value: string
  onChange: (value: string) => void
  language?: string
  height?: string
  placeholder?: string
  readOnly?: boolean
  className?: string
}

function monacoTheme(isDark: boolean): string {
  return isDark ? 'vs-dark' : 'vs'
}

export default function CodeEditor({
  value,
  onChange,
  language = 'plaintext',
  height = '260px',
  placeholder = '',
  readOnly = false,
  className,
}: CodeEditorProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const editorRef = useRef<Monaco.editor.IStandaloneCodeEditor | null>(null)
  const monacoApiRef = useRef<typeof Monaco | null>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange
  const [isEmpty, setIsEmpty] = useState(value.length === 0)
  const { isDark } = useTheme()

  // Mount: lazily load Monaco's core + language contributions, create the
  // editor instance once. Deliberately not in the deps-driven effects below
  // — this only ever runs once per mount.
  useEffect(() => {
    let cancelled = false

    Promise.all([import('../monacoEnvironment'), import('monaco-editor/esm/vs/editor/editor.api')]).then(
      ([, api]) => {
        if (cancelled || !containerRef.current) return // unmounted while the chunk was loading
        monacoApiRef.current = api

        const instance = api.editor.create(containerRef.current, {
          value,
          language,
          theme: monacoTheme(isDark),
          readOnly,
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
          scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8 },
        })
        editorRef.current = instance

        instance.onDidChangeModelContent(() => {
          const next = instance.getValue()
          setIsEmpty(next.length === 0)
          onChangeRef.current(next)
        })
      },
    )

    return () => {
      cancelled = true
      editorRef.current?.dispose()
      editorRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // External updates to `value` (e.g. loading an existing model) that didn't
  // originate from this editor's own change event.
  useEffect(() => {
    const editor = editorRef.current
    if (editor && editor.getValue() !== value) {
      editor.setValue(value)
    }
    setIsEmpty(value.length === 0)
  }, [value])

  useEffect(() => {
    const model = editorRef.current?.getModel()
    if (model && monacoApiRef.current) monacoApiRef.current.editor.setModelLanguage(model, language)
  }, [language])

  useEffect(() => {
    monacoApiRef.current?.editor.setTheme(monacoTheme(isDark))
  }, [isDark])

  return (
    <div className={cn('overflow-hidden rounded-md border', className)}>
      <div className="flex items-center justify-end border-b bg-muted/50 px-3 py-1.5">
        <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground">
          {language}
        </span>
      </div>
      <div className="relative w-full" style={{ height }}>
        <div ref={containerRef} className="h-full w-full" />
        {isEmpty && placeholder && (
          <div className="pointer-events-none absolute top-3 left-13 right-3 whitespace-pre-wrap font-mono text-[13px] text-muted-foreground opacity-65">
            {placeholder}
          </div>
        )}
      </div>
    </div>
  )
}
