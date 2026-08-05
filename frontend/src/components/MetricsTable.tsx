// Renders a TrainingResult's train/val/test metric rows (see
// logic/format.ts's buildMetricsTable). Extracted from ResultList's metrics
// dialog so ResultCompareView can reuse the exact same markup per result.
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { MetricsTableRow } from '@/logic/format'

interface MetricsTableProps {
  rows: MetricsTableRow[]
  emptyMessage?: string
}

export default function MetricsTable({ rows, emptyMessage = 'No metrics reported yet.' }: MetricsTableProps) {
  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyMessage}</p>
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Metric</TableHead>
          <TableHead className="text-right">Training</TableHead>
          <TableHead className="text-right">Validation</TableHead>
          <TableHead className="text-right">Test</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.name}>
            <TableCell className="font-medium">{row.name}</TableCell>
            <TableCell className="text-right tabular-nums">
              {row.train ?? <span className="text-muted-foreground">—</span>}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {row.val ?? <span className="text-muted-foreground">—</span>}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {row.test ?? <span className="text-muted-foreground">—</span>}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
