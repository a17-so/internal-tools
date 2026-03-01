import JobsTable from '@/components/app/jobs-table';

export default function HistoryPage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold text-slate-900">History</h2>
        <p className="text-slate-600">Completed and failed upload history.</p>
      </div>
      <JobsTable mode="history" />
    </div>
  );
}
