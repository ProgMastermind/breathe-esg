import type { ValidationFlag } from '../api/types'
import { AlertTriangle, AlertCircle, Info } from 'lucide-react'

const severityIcon: Record<string, React.ReactNode> = {
  error: <AlertCircle className="h-3.5 w-3.5 text-red-500 shrink-0" />,
  warn: <AlertTriangle className="h-3.5 w-3.5 text-orange-400 shrink-0" />,
  info: <Info className="h-3.5 w-3.5 text-blue-400 shrink-0" />,
}

export function FlagList({ flags }: { flags: ValidationFlag[] }) {
  if (!flags.length) return null
  return (
    <ul className="space-y-1">
      {flags.map((f) => (
        <li key={f.id} className="flex items-start gap-1.5 text-xs text-gray-700">
          {severityIcon[f.severity]}
          <span>{f.message}</span>
        </li>
      ))}
    </ul>
  )
}
