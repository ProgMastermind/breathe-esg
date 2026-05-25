type Status = 'pending' | 'flagged' | 'approved' | 'rejected' | 'processing' | 'completed' | 'failed'

const styles: Record<Status, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  flagged: 'bg-orange-100 text-orange-800',
  approved: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
  processing: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
}

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const cls = styles[status as Status] ?? 'bg-gray-100 text-gray-700'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {label ?? status}
    </span>
  )
}
