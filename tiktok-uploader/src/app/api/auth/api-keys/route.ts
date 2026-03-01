import { NextResponse } from 'next/server';
import { z } from 'zod';
import { createApiKey } from '@/lib/auth';
import { db } from '@/lib/db';
import { withAuth } from '@/lib/api-auth';

const createSchema = z.object({
  name: z.string().min(1).max(64).default('CLI Key'),
});

export async function POST(request: Request) {
  return withAuth(async (user) => {
    const payload = createSchema.parse(await request.json().catch(() => ({})));
    const key = await createApiKey(user.id, payload.name);

    return NextResponse.json({
      apiKey: {
        id: key.id,
        name: key.name,
        keyPrefix: key.keyPrefix,
        createdAt: key.createdAt,
        token: key.token,
      },
    });
  });
}

const revokeSchema = z.object({
  id: z.string().min(1),
});

export async function DELETE(request: Request) {
  return withAuth(async (user) => {
    const payload = revokeSchema.parse(await request.json());
    await db.apiKey.updateMany({
      where: {
        id: payload.id,
        userId: user.id,
      },
      data: {
        revokedAt: new Date(),
      },
    });

    return NextResponse.json({ success: true });
  });
}
