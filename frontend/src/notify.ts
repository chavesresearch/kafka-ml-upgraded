// Toast notifications, backed by sonner (shadcn's toast library).
import { toast } from 'sonner'

export function useNotify() {
  return {
    ok: (message: string) => toast.success(message),
    error: (message: string) => toast.error(message),
  }
}
