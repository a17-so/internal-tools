import { NextResponse } from 'next/server';
import { withAuth } from '@/lib/api-auth';
import { db } from '@/lib/db';

export async function DELETE(_request: Request, context: { params: Promise<{ id: string }> }) {
  return withAuth(async (user) => {
    const { id } = await context.params;

    await db.connectedAccount.deleteMany({
      where: {
        id,
        userId: user.id,
      },
    });

    return NextResponse.json({ success: true });
  });
}
