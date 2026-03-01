import { NextResponse } from 'next/server';
import { logoutCurrentSession } from '@/lib/auth';

export async function POST() {
  await logoutCurrentSession();
  return NextResponse.json({ success: true });
}
