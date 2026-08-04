// Imperative confirm-dialog hook, mirroring PrimeVue's `useConfirm()` used
// throughout the old frontend's delete/stop flows: `confirm({header, message,
// accept})` opens an AlertDialog; `accept()` runs only if the user confirms.
import { useCallback, useState } from 'react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

interface ConfirmOptions {
  header: string
  message: string
  accept: () => void
}

export function useConfirm() {
  const [options, setOptions] = useState<ConfirmOptions | null>(null)

  const confirm = useCallback((opts: ConfirmOptions) => setOptions(opts), [])

  const dialog = (
    <AlertDialog open={options != null} onOpenChange={(open) => !open && setOptions(null)}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{options?.header}</AlertDialogTitle>
          <AlertDialogDescription>{options?.message}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={() => {
              options?.accept()
              setOptions(null)
            }}
          >
            Confirm
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )

  return { confirm, dialog }
}
