'use client';

import { PauseCircle, PlayCircle, Power, TimerReset } from 'lucide-react';
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
    <div className="panel p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">Queue Controls</h3>
          <p className="text-xs text-muted-foreground">Dispatch mode: {control.dispatchMode === 'due_only' ? 'Due jobs only' : 'All queued jobs'}</p>
        </div>
        <span className={`status-pill ${control.paused ? 'status-failed' : 'status-succeeded'}`}>{control.paused ? 'paused' : 'active'}</span>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button variant="outline" className="rounded-xl" disabled={loading} onClick={() => void updateControl({ paused: !control.paused })}>
          {control.paused ? <PlayCircle className="h-4 w-4" /> : <PauseCircle className="h-4 w-4" />}
          {control.paused ? 'Resume Queue' : 'Pause Queue'}
        </Button>

        <Button
          variant="outline"
          className="rounded-xl"
          disabled={loading}
          onClick={() => void updateControl({ dispatchMode: control.dispatchMode === 'due_only' ? 'all_queued' : 'due_only' })}
        >
          <Power className="h-4 w-4" />
          {control.dispatchMode === 'due_only' ? 'Switch to all queued' : 'Switch to due only'}
        </Button>

        <Button className="rounded-xl" disabled={loading} onClick={() => void runDispatch('due_only')}>
          Drain Due Jobs
        </Button>

        <Button variant="outline" className="rounded-xl" disabled={loading} onClick={() => void runDispatch('all_queued')}>
          <TimerReset className="h-4 w-4" />
          Drain All Queued
        </Button>

        {control.paused ? (
          <Button variant="outline" className="rounded-xl" disabled={loading} onClick={() => void runDispatch(control.dispatchMode, true)}>
            Run Once While Paused
          </Button>
        ) : null}
      </div>
    </div>
  );
}
