import JobsTable from '@/components/app/jobs-table';

export default function QueuePage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold text-slate-900">Queue</h2>
        <p className="text-slate-600">Live queued/running/failed jobs with controls.</p>
      </div>
      <JobsTable mode="queue" />
    </div>
  );
}
