import type { ComponentProps } from 'react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

interface TooltipIconButtonProps extends ComponentProps<typeof Button> {
  tooltip: string
}

// Every icon-only action button in the app used a bare `title` attribute -
// correct for the accessible name (via the HTML title-fallback rule), but
// the native browser tooltip it also produces is slow to appear and
// unstyled. This swaps in shadcn's Tooltip (already wired up globally via
// <TooltipProvider> in main.tsx, just unused until now) for the visible
// hover UI - but Radix's Tooltip does NOT wire its content into the
// trigger's accessible name by default (only `aria-describedby` while
// open), so `aria-label` is set explicitly here to preserve the same
// accessible-name contract `title` used to provide. A caller that needs a
// different accessible name than the visible tooltip text (e.g. one badge
// showing state, one showing the action) can still pass its own
// `aria-label` to override this default.
// Composes with a Button that's itself `asChild`-wrapping a Link (e.g.
// `<TooltipIconButton asChild><Link>...`) via nested Radix Slot, same as
// any other Radix asChild composition.
export default function TooltipIconButton({
  tooltip,
  size = 'icon',
  'aria-label': ariaLabel,
  ...props
}: TooltipIconButtonProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button size={size} aria-label={ariaLabel ?? tooltip} {...props} />
      </TooltipTrigger>
      <TooltipContent>{tooltip}</TooltipContent>
    </Tooltip>
  )
}
