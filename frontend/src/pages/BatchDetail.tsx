import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, CheckCircle, XCircle, ChevronDown, ChevronUp } from 'lucide-react'
import { review, ingestion } from '../api/endpoints'
import { StatusBadge } from '../components/StatusBadge'
import { ScopeBadge } from '../components/ScopeBadge'
import { FlagList } from '../components/FlagList'
import type { NormalizedRecord } from '../api/types'
import { format } from 'date-fns'

function formatCO2(val: string | null) {
  if (!val) return '—'
  const n = parseFloat(val)
  if (n >= 1000) return `${(n / 1000).toFixed(3)} tCO₂e`
  return `${n.toFixed(2)} kgCO₂e`
}

function RecordRow({
  record,
  selected,
  onToggleSelect,
  onAction,
}: {
  record: NormalizedRecord
  selected: boolean
  onToggleSelect: () => void
  onAction: (id: number, action: 'approve' | 'reject') => void
}) {
  const [expanded, setExpanded] = useState(false)

  const flagCount = record.flags.length
  const errorFlags = record.flags.filter((f) => f.severity === 'error')
  const warnFlags = record.flags.filter((f) => f.severity !== 'error')

  return (
    <>
      <tr className={`border-b border-gray-100 hover:bg-gray-50 transition-colors ${selected ? 'bg-green-50' : ''}`}>
        <td className="px-3 py-3">
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggleSelect}
            disabled={record.is_locked}
            className="rounded text-green-600"
          />
        </td>
        <td className="px-3 py-3 text-sm text-gray-600">
          {record.activity_date ? format(new Date(record.activity_date), 'dd MMM yyyy') : '—'}
        </td>
        <td className="px-3 py-3 text-sm text-gray-900 max-w-[200px]">
          <span className="truncate block" title={record.description}>{record.description || '—'}</span>
        </td>
        <td className="px-3 py-3 text-sm text-gray-700 text-right tabular-nums whitespace-nowrap">
          {record.quantity ? `${parseFloat(record.quantity).toLocaleString()} ${record.unit}` : '—'}
        </td>
        <td className="px-3 py-3 text-sm font-medium text-gray-900 text-right tabular-nums whitespace-nowrap">
          {formatCO2(record.co2e_kg)}
        </td>
        <td className="px-3 py-3"><ScopeBadge scope={record.scope} /></td>
        <td className="px-3 py-3">
          {flagCount > 0 ? (
            <button
              onClick={() => setExpanded((p) => !p)}
              className="flex items-center gap-1 text-xs font-medium"
            >
              {errorFlags.length > 0 ? (
                <span className="text-red-600">{errorFlags.length} error{errorFlags.length > 1 ? 's' : ''}</span>
              ) : null}
              {warnFlags.length > 0 ? (
                <span className="text-orange-500">{warnFlags.length} warn</span>
              ) : null}
              {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            </button>
          ) : (
            <span className="text-xs text-gray-300">—</span>
          )}
        </td>
        <td className="px-3 py-3">
          <StatusBadge status={record.status} label={record.status_display} />
        </td>
        <td className="px-3 py-3">
          {!record.is_locked && (
            <div className="flex gap-1">
              {record.status !== 'approved' && (
                <button
                  onClick={() => onAction(record.id, 'approve')}
                  title="Approve"
                  className="p-1 text-green-600 hover:bg-green-50 rounded transition-colors"
                >
                  <CheckCircle className="h-4 w-4" />
                </button>
              )}
              {record.status !== 'rejected' && (
                <button
                  onClick={() => onAction(record.id, 'reject')}
                  title="Reject"
                  className="p-1 text-red-500 hover:bg-red-50 rounded transition-colors"
                >
                  <XCircle className="h-4 w-4" />
                </button>
              )}
            </div>
          )}
          {record.is_locked && <span className="text-xs text-gray-300">Locked</span>}
        </td>
      </tr>
      {expanded && (
        <tr className="bg-orange-50 border-b border-gray-100">
          <td colSpan={9} className="px-6 py-3">
            <FlagList flags={record.flags} />
          </td>
        </tr>
      )}
    </>
  )
}

export function BatchDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [statusFilter, setStatusFilter] = useState('')
  const [scopeFilter, setScopeFilter] = useState('')
  const [flagsOnly, setFlagsOnly] = useState(false)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [page, setPage] = useState(1)

  const { data: batchData } = useQuery({
    queryKey: ['batch', id],
    queryFn: () => ingestion.batches().then((r) => r.data.results.find((b) => b.id === Number(id))),
  })

  const { data: recordsData } = useQuery({
    queryKey: ['records', id, statusFilter, scopeFilter, flagsOnly, page],
    queryFn: () =>
      review.records({
        batch: Number(id),
        status: statusFilter || undefined,
        scope: scopeFilter || undefined,
        has_flags: flagsOnly || undefined,
        page,
      }).then((r) => r.data),
  })

  const records = recordsData?.results ?? []

  const actionMutation = useMutation({
    mutationFn: ({ recordId, action }: { recordId: number; action: 'approve' | 'reject' }) =>
      review.updateRecord(recordId, { status: action }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['records', id] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  const bulkMutation = useMutation({
    mutationFn: ({ ids, action }: { ids: number[]; action: 'approve' | 'reject' }) =>
      review.bulkAction(ids, action),
    onSuccess: () => {
      setSelected(new Set())
      qc.invalidateQueries({ queryKey: ['records', id] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  const allIds = records.map((r) => r.id)
  const allSelected = allIds.length > 0 && allIds.every((id) => selected.has(id))

  const toggleAll = () => {
    if (allSelected) {
      setSelected(new Set())
    } else {
      setSelected(new Set(allIds))
    }
  }

  const toggleOne = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const totalPages = recordsData ? Math.ceil(recordsData.count / 50) : 1

  return (
    <div className="p-8 space-y-5">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/batches')}
          className="text-gray-400 hover:text-gray-600 transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-xl font-bold text-gray-900">
            {batchData?.source_type_display ?? 'Batch'} — {batchData?.file_name}
          </h1>
          <p className="text-sm text-gray-500">
            {batchData?.row_count} rows ingested · {recordsData?.count ?? 0} normalized records
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="flagged">Flagged</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
        <select
          value={scopeFilter}
          onChange={(e) => { setScopeFilter(e.target.value); setPage(1) }}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
        >
          <option value="">All scopes</option>
          <option value="1">Scope 1</option>
          <option value="2">Scope 2</option>
          <option value="3">Scope 3</option>
        </select>
        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
          <input
            type="checkbox"
            checked={flagsOnly}
            onChange={(e) => { setFlagsOnly(e.target.checked); setPage(1) }}
            className="rounded text-green-600"
          />
          Flagged only
        </label>

        {selected.size > 0 && (
          <div className="ml-auto flex items-center gap-2">
            <span className="text-sm text-gray-500">{selected.size} selected</span>
            <button
              onClick={() => bulkMutation.mutate({ ids: [...selected], action: 'approve' })}
              disabled={bulkMutation.isPending}
              className="flex items-center gap-1 text-sm bg-green-600 hover:bg-green-700 text-white px-3 py-1.5 rounded-lg transition-colors"
            >
              <CheckCircle className="h-3.5 w-3.5" />
              Approve all
            </button>
            <button
              onClick={() => bulkMutation.mutate({ ids: [...selected], action: 'reject' })}
              disabled={bulkMutation.isPending}
              className="flex items-center gap-1 text-sm bg-red-50 hover:bg-red-100 text-red-700 px-3 py-1.5 rounded-lg border border-red-200 transition-colors"
            >
              <XCircle className="h-3.5 w-3.5" />
              Reject all
            </button>
          </div>
        )}
      </div>

      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-3 py-3 w-8">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleAll}
                  className="rounded text-green-600"
                />
              </th>
              <th className="text-left px-3 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Date</th>
              <th className="text-left px-3 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Description</th>
              <th className="text-right px-3 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Quantity</th>
              <th className="text-right px-3 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">CO₂e</th>
              <th className="text-left px-3 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Scope</th>
              <th className="text-left px-3 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Flags</th>
              <th className="text-left px-3 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Status</th>
              <th className="px-3 py-3 w-16" />
            </tr>
          </thead>
          <tbody>
            {records.length === 0 && (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-gray-400 text-sm">
                  No records match the current filter.
                </td>
              </tr>
            )}
            {records.map((record) => (
              <RecordRow
                key={record.id}
                record={record}
                selected={selected.has(record.id)}
                onToggleSelect={() => toggleOne(record.id)}
                onAction={(rid, action) => actionMutation.mutate({ recordId: rid, action })}
              />
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => p - 1)}
            disabled={page === 1}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50"
          >
            Previous
          </button>
          <span className="text-sm text-gray-500">Page {page} of {totalPages}</span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={page === totalPages}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
