import { UploadJob } from '@prisma/client';
import { db } from '@/lib/db';

function getWebhookTargets() {
  const raw = process.env.UPLOAD_FAILURE_WEBHOOK_URLS || process.env.UPLOAD_FAILURE_WEBHOOK_URL || '';
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

export async function notifyJobFailed(job: UploadJob, reason: string) {
  const targets = getWebhookTargets();
  if (targets.length === 0) return;

  const eventPayload = {
    event: 'upload.job.failed',
    timestamp: new Date().toISOString(),
    job: {
      id: job.id,
      userId: job.userId,
      batchId: job.batchId,
      provider: job.provider,
      postType: job.postType,
      mode: job.mode,
      attemptCount: job.attemptCount,
      maxRetries: job.maxRetries,
      errorMessage: reason,
      scheduledAt: job.scheduledAt,
    },
  };

  await Promise.all(
    targets.map(async (target) => {
      const isSlackWebhook = /hooks\\.slack\\.com/i.test(target);
      const payload = isSlackWebhook
        ? {
          text: `Upload failed (${job.provider})`,
          blocks: [
            {
              type: 'header',
              text: { type: 'plain_text', text: 'Uploader Job Failed' },
            },
            {
              type: 'section',
              fields: [
                { type: 'mrkdwn', text: `*Provider*\\n${job.provider}` },
                { type: 'mrkdwn', text: `*Job ID*\\n${job.id}` },
                { type: 'mrkdwn', text: `*Batch ID*\\n${job.batchId || '-'}` },
                { type: 'mrkdwn', text: `*Mode / Type*\\n${job.mode} / ${job.postType}` },
                { type: 'mrkdwn', text: `*Attempts*\\n${job.attemptCount}/${job.maxRetries}` },
                { type: 'mrkdwn', text: `*Scheduled*\\n${job.scheduledAt ? new Date(job.scheduledAt).toISOString() : 'Immediate'}` },
              ],
            },
            {
              type: 'section',
              text: { type: 'mrkdwn', text: `*Error*\\n${reason}` },
            },
          ],
          metadata: eventPayload,
        }
        : eventPayload;

      try {
        const response = await fetch(target, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        await db.uploadNotification.create({
          data: {
            uploadJobId: job.id,
            type: 'failure_webhook',
            target,
            status: response.ok ? 'sent' : 'failed',
            message: response.ok ? 'OK' : `HTTP ${response.status}`,
            payloadJson: JSON.stringify(payload),
          },
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        await db.uploadNotification.create({
          data: {
            uploadJobId: job.id,
            type: 'failure_webhook',
            target,
            status: 'failed',
            message,
            payloadJson: JSON.stringify(payload),
          },
        });
      }
    })
  );
}
