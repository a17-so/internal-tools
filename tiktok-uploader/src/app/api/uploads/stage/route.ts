import { NextResponse } from 'next/server';
import { withAuth } from '@/lib/api-auth';
import { persistBrowserFile } from '@/lib/upload-storage';

export async function POST(request: Request) {
  return withAuth(async () => {
    const formData = await request.formData();
    const files = formData.getAll('files').filter((f): f is File => f instanceof File);

    if (files.length === 0) {
      return NextResponse.json({ error: 'No files provided' }, { status: 400 });
    }

    const staged = await Promise.all(
      files.map(async (file, index) => {
        const saved = await persistBrowserFile(file, `stage_${index}`);
        return {
          filePath: saved.filePath,
          fileName: file.name,
          mimeType: saved.mimeType,
          size: file.size,
        };
      })
    );

    return NextResponse.json({ staged });
  });
}
