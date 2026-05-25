import { useQuery } from '@tanstack/react-query'
import { review } from '../api/endpoints'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { CheckCircle, Clock, AlertTriangle, XCircle } from 'lucide-react'

const scopeColors: Record<string, string> = { '1': '#ef4444', '2': '#8b5cf6', '3': '#6366f1' }
const scopeLabels: Record<string, string> = { '1': 'Scope 1 (Direct)', '2': 'Scope 2 (Electricity)', '3': 'Scope 3 (Travel)' }

export function Dashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => review.dashboard().then((r) => r.data),
  })

  if (isLoading) return <div className="p-8 text-sm text-gray-500">Loading…</div>
  if (!data) return null

  const statusCards = [
    { label: 'Pending Review', value: data.by_status.pending ?? 0, icon: Clock, color: 'text-yellow-600 bg-yellow-50' },
    { label: 'Flagged', value: data.by_status.flagged ?? 0, icon: AlertTriangle, color: 'text-orange-600 bg-orange-50' },
    { label: 'Approved', value: data.by_status.approved ?? 0, icon: CheckCircle, color: 'text-green-600 bg-green-50' },
    { label: 'Rejected', value: data.by_status.rejected ?? 0, icon: XCircle, color: 'text-red-600 bg-red-50' },
  ]

  const totalCO2 = Object.values(data.by_scope).reduce((s, v) => s + v.co2e_kg, 0)

  const scopeChartData = Object.entries(data.by_scope).map(([scope, v]) => ({
    scope: scopeLabels[scope],
    co2e: Math.round(v.co2e_kg),
    color: scopeColors[scope],
  }))

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">
          {data.total} total records — {(totalCO2 / 1000).toFixed(2)} tCO₂e total
        </p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {statusCards.map((card) => (
          <div key={card.label} className="bg-white border border-gray-200 rounded-xl p-4 flex items-center gap-3">
            <div className={`p-2 rounded-lg ${card.color}`}>
              <card.icon className="h-5 w-5" />
            </div>
            <div>
              <div className="text-2xl font-bold text-gray-900">{card.value}</div>
              <div className="text-xs text-gray-500">{card.label}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 bg-white border border-gray-200 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">CO₂e by Scope (kg)</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={scopeChartData} barSize={40}>
              <XAxis dataKey="scope" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [`${Number(v).toLocaleString()} kg`, 'CO₂e']} />
              <Bar dataKey="co2e" radius={[4, 4, 0, 0]}>
                {scopeChartData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">By Data Source</h2>
          <div className="space-y-3">
            {data.by_source.map((src) => (
              <div key={src.source_type} className="flex justify-between items-center text-sm">
                <span className="text-gray-600 truncate max-w-[120px]" title={src.label}>{src.label}</span>
                <div className="text-right">
                  <div className="font-medium text-gray-900">{src.count} records</div>
                  <div className="text-xs text-gray-400">{Math.round(src.co2e_kg)} kg CO₂e</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
