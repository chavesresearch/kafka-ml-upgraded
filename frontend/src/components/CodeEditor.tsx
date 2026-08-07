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
  /** Accessible name for Monaco's hidden screen-reader input - the visible
   * <Label> above this field isn't associated via htmlFor/id (Monaco has no
   * plain <input> to point it at), so without this every instance is
   * announced identically as a generic, unlabeled editor. */
  ariaLabel?: string
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
  ariaLabel = 'Code editor',
}: CodeEditorProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const editorRef = useRef<Monaco.editor.IStandaloneCodeEditor | null>(null)
  const monacoApiRef = useRef<typeof Monaco | null>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange
  const ariaLabelRef = useRef(ariaLabel)
  ariaLabelRef.current = ariaLabel
  // Mirrors `value` for the mount effect below to read from - that effect's
  // own `value` closure is captured once, at the first render, but Monaco's
  // chunk is loaded with an async import() that can resolve well after a
  // later render already updated `value` (e.g. ModelView's edit form: mounts
  // with value="" before `getModel()` resolves, then re-renders with the
  // real code once it does). Reading `valueRef.current` instead of the
  // closured `value` at editor-creation time picks up whatever the latest
  // value actually is, not whatever it was when this effect first ran.
  const valueRef = useRef(value)
  valueRef.current = value
  // The last value the editor itself produced (echoed up via onChange).
  // Lets the [value]-sync effect below tell "value changed because the
  // editor just reported it" apart from a genuinely external change (e.g.
  // loading a different model to edit) by comparing values directly,
  // rather than a one-shot flag - see that effect's own comment for why
  // a flag alone isn't reliable here.
  const lastEditorValueRef = useRef(value)
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
          value: valueRef.current,
          language,
          theme: monacoTheme(isDark),
          readOnly,
          ariaLabel: ariaLabelRef.current,
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
        lastEditorValueRef.current = valueRef.current
        setIsEmpty(valueRef.current.length === 0)

        instance.onDidChangeModelContent(() => {
          const next = instance.getValue()
          setIsEmpty(next.length === 0)
          lastEditorValueRef.current = next
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
  //
  // Real bug, found via an actual Playwright run typing multi-line
  // indented Python into this field (e2e/golden-path.spec.ts) - not
  // hypothetical, and not fully fixed by the first attempt at this fix
  // (a one-shot "did this change come from the editor" boolean ref) -
  // that version still intermittently hit the same crash (~2 times in 5
  // real runs), because the flag can be reset by this effect running for
  // an *earlier* editor-originated change before a *later* one (Monaco's
  // auto-indent/auto-closing-bracket behavior can fire a second
  // onDidChangeModelContent for a single keystroke) has had a chance to
  // set it again - a real ordering race under fast typing, not just a
  // one-off timing fluke. Comparing against `lastEditorValueRef` instead
  // is race-free: it's a value check, not a consumed one-shot flag, so
  // it stays correct no matter how many editor-originated changes land
  // between renders. Without either fix: `editor.getValue() !== value`
  // goes spuriously true, `editor.setValue(value)` rolls the live editor
  // content *backwards* to a stale value, which fires another content
  // event, calls onChange again, and round-trips back into this same
  // effect - "Maximum update depth exceeded" (React's own infinite-loop
  // guard, confirmed in a real browser console, not a hang).
  useEffect(() => {
    if (value === lastEditorValueRef.current) {
      // This value update just echoes what the editor already has -
      // nothing to sync, and no reason to fight with in-progress typing.
      setIsEmpty(value.length === 0)
      return
    }
    const editor = editorRef.current
    if (editor && editor.getValue() !== value) {
      editor.setValue(value)
      lastEditorValueRef.current = value
    }
    setIsEmpty(value.length === 0)
  }, [value])

  useEffect(() => {
    editorRef.current?.updateOptions({ ariaLabel })
  }, [ariaLabel])

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
