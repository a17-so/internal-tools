import { NextResponse } from 'next/server';
import { Provider } from '@prisma/client';
import { withAuth } from '@/lib/api-auth';
import { db } from '@/lib/db';

export async function GET(request: Request) {
  return withAuth(async (user) => {
    const { searchParams } = new URL(request.url);
    const providerParam = searchParams.get('provider') as Provider | null;

    const accounts = await db.connectedAccount.findMany({
      where: {
        userId: user.id,
        ...(providerParam ? { provider: providerParam } : {}),
      },
      orderBy: { createdAt: 'desc' },
      include: {
        capabilities: {
          orderBy: { fetchedAt: 'desc' },
          take: 1,
        },
      },
    });

    return NextResponse.json({ accounts });
  });
}
