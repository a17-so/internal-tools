import { NextResponse } from 'next/server';
import { requireAuth } from '@/lib/auth';

export async function withAuth<T>(fn: (user: Awaited<ReturnType<typeof requireAuth>>) => Promise<T>) {
  try {
    const user = await requireAuth();
    return await fn(user);
  } catch (error) {
    if (error instanceof Error && error.message === 'UNAUTHORIZED') {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 }) as T;
    }

    console.error(error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 }) as T;
  }
}
