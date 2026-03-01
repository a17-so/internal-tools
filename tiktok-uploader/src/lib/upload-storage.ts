import fs from 'fs/promises';
import path from 'path';
import crypto from 'crypto';

const UPLOAD_DIR = process.env.UPLOADS_DIR || path.join(process.cwd(), 'uploads');

export async function ensureUploadsDir() {
  await fs.mkdir(UPLOAD_DIR, { recursive: true });
  return UPLOAD_DIR;
}

export async function persistBrowserFile(file: File, prefix = 'asset'): Promise<{ filePath: string; sizeBytes: number; mimeType: string }> {
  const dir = await ensureUploadsDir();
  const ext = file.name.includes('.') ? file.name.split('.').pop() : undefined;
  const safeExt = ext ? `.${ext.toLowerCase()}` : '';
  const filename = `${prefix}_${Date.now()}_${crypto.randomBytes(6).toString('hex')}${safeExt}`;
  const filePath = path.join(dir, filename);
  const bytes = await file.arrayBuffer();
  const buffer = Buffer.from(bytes);
  await fs.writeFile(filePath, buffer);

  return {
    filePath,
    sizeBytes: buffer.length,
    mimeType: file.type || 'application/octet-stream',
  };
}
