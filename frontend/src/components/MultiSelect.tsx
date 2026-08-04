// Minimal multi-select: a trigger showing selected items as removable chips,
// opening a filterable checkbox list in a popover. Replaces PrimeVue's
// <MultiSelect display="chip"> used in a few forms (configuration's ml_models,
// IoT inference's device_token, the metrics plot picker).
import { useState } from 'react'
import { Check, ChevronsUpDown, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export interface MultiSelectOption {
  value: string
  label: string
}

interface MultiSelectProps {
  options: MultiSelectOption[]
  value: string[]
  onChange: (value: string[]) => void
  placeholder?: string
  className?: string
}

export default function MultiSelect({ options, value, onChange, placeholder = 'Select…', className }: MultiSelectProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')

  const selected = options.filter((o) => value.includes(o.value))
  const filtered = options.filter((o) => o.label.toLowerCase().includes(search.trim().toLowerCase()))

  function toggle(optionValue: string) {
    if (value.includes(optionValue)) onChange(value.filter((v) => v !== optionValue))
    else onChange([...value, optionValue])
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn('h-auto min-h-9 w-full justify-between font-normal', className)}
        >
          <span className="flex flex-1 flex-wrap gap-1">
            {selected.length === 0 ? (
              <span className="text-muted-foreground">{placeholder}</span>
            ) : (
              selected.map((o) => (
                <Badge
                  key={o.value}
                  variant="secondary"
                  className="gap-1"
                  onClick={(e) => {
                    e.stopPropagation()
                    toggle(o.value)
                  }}
                >
                  {o.label}
                  <X className="size-3" />
                </Badge>
              ))
            )}
          </span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-(--radix-popover-trigger-width) p-0" align="start">
        <div className="p-2">
          <Input placeholder="Search…" value={search} onChange={(e) => setSearch(e.target.value)} autoFocus />
        </div>
        <div className="max-h-64 overflow-y-auto p-1">
          {filtered.length === 0 && <div className="p-2 text-sm text-muted-foreground">No options</div>}
          {filtered.map((o) => (
            <button
              key={o.value}
              type="button"
              onClick={() => toggle(o.value)}
              className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground"
            >
              <span className="flex size-4 items-center justify-center">
                {value.includes(o.value) && <Check className="size-4" />}
              </span>
              {o.label}
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}
