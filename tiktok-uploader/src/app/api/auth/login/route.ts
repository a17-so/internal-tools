import { NextResponse } from 'next/server';
import { z } from 'zod';
import { loginWithPassword } from '@/lib/auth';

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

export async function POST(request: Request) {
  try {
    const body = schema.parse(await request.json());
    const user = await loginWithPassword(body.email, body.password);

    if (!user) {
      return NextResponse.json({ error: 'Invalid credentials' }, { status: 401 });
    }

    return NextResponse.json({ user });
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json({ error: error.issues[0]?.message || 'Invalid payload' }, { status: 400 });
    }

    console.error(error);
    return NextResponse.json({ error: 'Login failed' }, { status: 500 });
  }
}
