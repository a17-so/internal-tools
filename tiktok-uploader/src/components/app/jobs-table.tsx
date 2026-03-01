'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshCw, RotateCcw, StopCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';

export type JobView = {
  id: string;
  status: string;
  postType: string;
  mode: string;
  caption: string;
  errorMessage: string | null;
  scheduledAt?: string | null;
  nextAttemptAt?: string | null;
  connectedAccount: {
    username: string | null;
    displayName: string | null;
  };
  createdAt: string;
};

function statusClass(status: string) {
  if (status === 'queued') return 'status-pill status-queued';
  if (status === 'running') return 'status-pill status-running';
  if (status === 'failed') return 'status-pill status-failed';
  if (status === 'succeeded') return 'status-pill status-succeeded';
  return 'status-pill status-canceled';
}

export default function JobsTable({ mode, initialJobs }: { mode: 'queue' | 'history'; initialJobs: JobView[] }) {
  const [jobs, setJobs] = useState<JobView[]>(initialJobs);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');

  const refresh = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    const status = mode === 'queue' ? 'queued,running,failed' : 'succeeded,failed,canceled';
    const res = await fetch(`/api/uploads/jobs?status=${status}`);
    const data = await res.json();
    setJobs(data.jobs || []);
    setLoading(false);
  }, [mode]);

  useEffect(() => {
    if (mode !== 'queue') return;

    const id = setInterval(() => {
      void refresh(true);
    }, 5000);
    return () => clearInterval(id);
  }, [mode, refresh]);

  const filteredJobs = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return jobs;
    return jobs.filter((job) => {
      const account = job.connectedAccount.displayName || job.connectedAccount.username || '';
      return (
        job.id.toLowerCase().includes(q)
        || job.caption.toLowerCase().includes(q)
        || job.status.toLowerCase().includes(q)
        || job.postType.toLowerCase().includes(q)
        || account.toLowerCase().includes(q)
      );
    });
  }, [jobs, query]);

  const retry = async (id: string) => {
    const res = await fetch(`/api/uploads/jobs/${id}/retry`, { method: 'POST' });
    if (!res.ok) {
      const data = await res.json();
      toast.error(data.error || 'Retry failed');
      return;
    }
    toast.success('Job retried');
    void refresh();
  };

  const cancel = async (id: string) => {
    const res = await fetch(`/api/uploads/jobs/${id}/cancel`, { method: 'POST' });
    if (!res.ok) {
      const data = await res.json();
      toast.error(data.error || 'Cancel failed');
      return;
    }
    toast.success('Job canceled');
    void refresh();
  };

  return (
    <div className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100/90 p-3">
        <Input placeholder="Search jobs, caption, account, status" value={query} onChange={(e) => setQuery(e.target.value)} className="max-w-sm rounded-xl" />
        <Button variant="outline" size="sm" className="rounded-xl" onClick={() => void refresh()} disabled={loading}>
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </Button>
      </div>

      {loading ? <p className="p-4 text-sm text-slate-500">Loading jobs...</p> : null}

      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50/70 text-slate-600">
            <tr>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Account</th>
              <th className="px-3 py-2">Schedule</th>
              <th className="px-3 py-2">Caption</th>
              <th className="px-3 py-2">Created</th>
              <th className="px-3 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredJobs.map((job) => (
              <tr key={job.id} className="border-t border-slate-100 align-top">
                <td className="px-3 py-3"><span className={statusClass(job.status)}>{job.status}</span></td>
                <td className="px-3 py-3 text-slate-700">{job.postType}/{job.mode}</td>
                <td className="px-3 py-3 text-slate-700">{job.connectedAccount.displayName || job.connectedAccount.username || '-'}</td>
                <td className="px-3 py-3 text-xs text-slate-500">
                  {job.scheduledAt ? `At ${new Date(job.scheduledAt).toLocaleString()}` : 'Immediate'}
                  {job.nextAttemptAt ? <div>Retry after {new Date(job.nextAttemptAt).toLocaleTimeString()}</div> : null}
                </td>
                <td className="max-w-[340px] px-3 py-3 text-slate-700" title={job.caption}>
                  <p className="line-clamp-2">{job.caption || '-'}</p>
                </td>
                <td className="px-3 py-3 text-slate-500">{new Date(job.createdAt).toLocaleString()}</td>
                <td className="space-y-1 px-3 py-3">
                  {job.status === 'failed' ? (
                    <Button variant="outline" size="sm" className="rounded-lg" onClick={() => retry(job.id)}>
                      <RotateCcw className="h-3.5 w-3.5" />
                      Retry
                    </Button>
                  ) : null}
                  {(job.status === 'queued' || job.status === 'running') ? (
                    <Button variant="outline" size="sm" className="rounded-lg" onClick={() => cancel(job.id)}>
                      <StopCircle className="h-3.5 w-3.5" />
                      Cancel
                    </Button>
                  ) : null}
                  {job.errorMessage ? <p className="max-w-[240px] text-xs text-rose-700">{job.errorMessage}</p> : null}
                </td>
              </tr>
            ))}
            {!filteredJobs.length ? (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-sm text-slate-500">No jobs found.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
