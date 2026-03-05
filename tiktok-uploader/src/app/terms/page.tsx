import Link from 'next/link';

export default function TermsPage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-6 px-6 py-14 text-zinc-900 dark:text-zinc-100">
      <h1 className="text-3xl font-semibold">Terms of Service</h1>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">Last updated: March 4, 2026</p>

      <section className="space-y-2 text-sm leading-6">
        <p>This tool is for authorized internal publishing operations.</p>
        <p>You must only connect accounts and upload content that you own or are authorized to manage.</p>
        <p>You are responsible for complying with TikTok policies and all applicable laws.</p>
        <p>We may suspend access for misuse, abuse, or policy violations.</p>
      </section>

      <p className="text-sm">
        Questions: <a className="underline underline-offset-4" href="mailto:support@a17.so">support@a17.so</a>
      </p>

      <Link href="/" className="text-sm underline underline-offset-4">
        Back to home
      </Link>
    </main>
  );
}
