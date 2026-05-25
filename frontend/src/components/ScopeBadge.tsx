const styles: Record<string, string> = {
  '1': 'bg-red-100 text-red-800',
  '2': 'bg-purple-100 text-purple-800',
  '3': 'bg-indigo-100 text-indigo-800',
}
const labels: Record<string, string> = {
  '1': 'Scope 1',
  '2': 'Scope 2',
  '3': 'Scope 3',
}

export function ScopeBadge({ scope }: { scope: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${styles[scope] ?? 'bg-gray-100 text-gray-700'}`}>
      {labels[scope] ?? scope}
    </span>
  )
}
