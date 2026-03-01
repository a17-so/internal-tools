import { NextResponse } from 'next/server';
import { getOptionalAuth } from '@/lib/auth';

export async function GET() {
  const user = await getOptionalAuth();
  if (!user) {
    return NextResponse.json({ user: null }, { status: 401 });
  }

  return NextResponse.json({ user });
}
