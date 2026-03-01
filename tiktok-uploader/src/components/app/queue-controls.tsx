'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

type QueueControl = {
  paused: boolean;
  dispatchMode: 'due_only' | 'all_queued';
  updatedAt?: string;
};

export default function QueueControls({ initialControl }: { initialControl: QueueControl }) {
  const [control, setControl] = useState<QueueControl>(initialControl);
  const [loading, setLoading] = useState(false);

  const updateControl = async (patch: Partial<QueueControl>) => {
    setLoading(true);
    const res = await fetch('/api/queue/control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    });
    const data = await res.json();
    if (!res.ok) {
      toast.error(data.error || 'Failed to update queue control');
      setLoading(false);
      return;
    }
    setControl(data.control);
    setLoading(false);
  };

  const runDispatch = async (mode: 'due_only' | 'all_queued', forcePaused = false) => {
    setLoading(true);
    const res = await fetch('/api/dispatcher/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode, forcePaused }),
    });
    const data = await res.json();
    if (!res.ok) {
      toast.error(data.error || 'Dispatch run failed');
      setLoading(false);
      return;
    }

    toast.success(`Dispatch processed ${data.processed} job(s)`);
    setLoading(false);
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900">Queue Controls</h3>
        <span className="text-xs text-slate-500">Mode: {control.dispatchMode}</span>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button variant="outline" disabled={loading} onClick={() => void updateControl({ paused: !control.paused })}>
          {control.paused ? 'Resume Queue' : 'Pause Queue'}
        </Button>

        <Button
          variant="outline"
          disabled={loading}
          onClick={() => void updateControl({ dispatchMode: control.dispatchMode === 'due_only' ? 'all_queued' : 'due_only' })}
        >
          Toggle Mode ({control.dispatchMode === 'due_only' ? 'Switch to all queued' : 'Switch to due only'})
        </Button>

        <Button disabled={loading} onClick={() => void runDispatch('due_only')}>
          Drain Due Jobs
        </Button>

        <Button variant="outline" disabled={loading} onClick={() => void runDispatch('all_queued')}>
          Drain All Queued
        </Button>

        {control.paused ? (
          <Button variant="outline" disabled={loading} onClick={() => void runDispatch(control.dispatchMode, true)}>
            Run Once While Paused
          </Button>
        ) : null}
      </div>
    </div>
  );
}
