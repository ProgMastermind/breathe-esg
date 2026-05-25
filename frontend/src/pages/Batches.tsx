import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Upload, ChevronRight, AlertCircle } from 'lucide-react'
import { ingestion } from '../api/endpoints'
import { StatusBadge } from '../components/StatusBadge'
import { format } from 'date-fns'

const SOURCE_TYPES = [
  { value: 'sap_fuel', label: 'SAP — Fuel' },
  { value: 'sap_procurement', label: 'SAP — Procurement' },
  { value: 'utility_electricity', label: 'Utility — Electricity' },
  { value: 'travel_flight', label: 'Corporate Travel' },
]

export function Batches() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [uploading, setUploading] = useState(false)
  const [sourceType, setSourceType] = useState('sap_fuel')
  const [uploadError, setUploadError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const { data } = useQuery({
    queryKey: ['batches'],
    queryFn: () => ingestion.batches().then((r) => r.data.results),
  })

  const upload = useMutation({
    mutationFn: ({ file, sourceType }: { file: File; sourceType: string }) =>
      ingestion.upload(file, sourceType),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['batches'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      setUploading(false)
      setUploadError('')
      if (fileRef.current) fileRef.current.value = ''
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error ?? 'Upload failed.'
      setUploadError(msg)
      setUploading(false)
    },
  })

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadError('')
    setUploading(true)
    upload.mutate({ file, sourceType })
  }

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Data Uploads</h1>
          <p className="text-sm text-gray-500 mt-1">Upload CSV files from SAP, utility portals, or corporate travel platforms</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
          >
            {SOURCE_TYPES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
          <label className="cursor-pointer flex items-center gap-2 bg-green-700 hover:bg-green-800 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
            <Upload className="h-4 w-4" />
            {uploading ? 'Uploading…' : 'Upload CSV'}
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.tsv,.txt"
              className="hidden"
              onChange={handleFileChange}
              disabled={uploading}
            />
          </label>
        </div>
      </div>

      {uploadError && (
        <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {uploadError}
        </div>
      )}

      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Source</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">File</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Uploaded</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Rows</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Errors</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Status</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {!data?.length && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400 text-sm">
                  No uploads yet. Upload a CSV file to get started.
                </td>
              </tr>
            )}
            {data?.map((batch) => (
              <tr
                key={batch.id}
                onClick={() => navigate(`/batches/${batch.id}`)}
                className="hover:bg-gray-50 cursor-pointer transition-colors"
              >
                <td className="px-4 py-3 font-medium text-gray-900">{batch.source_type_display}</td>
                <td className="px-4 py-3 text-gray-600 max-w-xs truncate">{batch.file_name}</td>
                <td className="px-4 py-3 text-gray-500">
                  {format(new Date(batch.ingested_at), 'dd MMM yyyy HH:mm')}
                </td>
                <td className="px-4 py-3 text-right text-gray-700">{batch.row_count}</td>
                <td className="px-4 py-3 text-right">
                  <span className={batch.error_count > 0 ? 'text-red-600 font-medium' : 'text-gray-400'}>
                    {batch.error_count}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={batch.status} label={batch.status_display} />
                </td>
                <td className="px-4 py-3 text-gray-400">
                  <ChevronRight className="h-4 w-4" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
