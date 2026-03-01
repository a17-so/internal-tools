'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

type Job = {
  id: string;
  status: string;
  postType: string;
  mode: string;
  caption: string;
  errorMessage: string | null;
  connectedAccount: {
    username: string | null;
    displayName: string | null;
  };
  createdAt: string;
};

export default function JobsTable({ mode }: { mode: 'queue' | 'history' }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    const status = mode === 'queue' ? 'queued,running,failed' : 'succeeded,failed,canceled';
    const res = await fetch(`/api/uploads/jobs?status=${status}`);
    const data = await res.json();
    setJobs(data.jobs || []);
    setLoading(false);
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [mode]);

  const retry = async (id: string) => {
    const res = await fetch(`/api/uploads/jobs/${id}/retry`, { method: 'POST' });
    if (!res.ok) {
      const data = await res.json();
      toast.error(data.error || 'Retry failed');
      return;
    }
    toast.success('Job retried');
    refresh();
  };

  const cancel = async (id: string) => {
    const res = await fetch(`/api/uploads/jobs/${id}/cancel`, { method: 'POST' });
    if (!res.ok) {
      const data = await res.json();
      toast.error(data.error || 'Cancel failed');
      return;
    }
    toast.success('Job canceled');
    refresh();
  };

  if (loading) return <p className="text-slate-500">Loading jobs...</p>;

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Type</th>
            <th className="px-3 py-2">Account</th>
            <th className="px-3 py-2">Caption</th>
            <th className="px-3 py-2">Created</th>
            <th className="px-3 py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id} className="border-t border-slate-100 align-top">
              <td className="px-3 py-2 font-medium text-slate-900">{job.status}</td>
              <td className="px-3 py-2 text-slate-600">{job.postType}/{job.mode}</td>
              <td className="px-3 py-2 text-slate-600">{job.connectedAccount.displayName || job.connectedAccount.username || '-'}</td>
              <td className="max-w-[360px] truncate px-3 py-2 text-slate-600" title={job.caption}>{job.caption || '-'}</td>
              <td className="px-3 py-2 text-slate-500">{new Date(job.createdAt).toLocaleString()}</td>
              <td className="space-x-2 px-3 py-2">
                {job.status === 'failed' ? <Button variant="outline" onClick={() => retry(job.id)}>Retry</Button> : null}
                {(job.status === 'queued' || job.status === 'running') ? <Button variant="outline" onClick={() => cancel(job.id)}>Cancel</Button> : null}
                {job.errorMessage ? <p className="mt-1 max-w-[220px] text-xs text-red-600">{job.errorMessage}</p> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
