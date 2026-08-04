// Small wrapper over PrimeVue's toast, replacing Angular's MatSnackBar usage.
import { useToast } from 'primevue/usetoast'

export interface Notifier {
  ok(message: string): void
  error(message: string): void
}

export function useNotify(): Notifier {
  const toast = useToast()
  return {
    ok(message: string) {
      toast.add({ severity: 'success', summary: message, life: 3000 })
    },
    error(message: string) {
      toast.add({ severity: 'error', summary: message, life: 4000 })
    }
  }
}
