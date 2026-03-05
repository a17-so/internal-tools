import Link from 'next/link';

export default function PrivacyPage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-6 px-6 py-14 text-zinc-900 dark:text-zinc-100">
      <h1 className="text-3xl font-semibold">Privacy Policy</h1>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">Last updated: March 4, 2026</p>

      <section className="space-y-2 text-sm leading-6">
        <p>We collect only data required to authenticate TikTok and upload media drafts.</p>
        <p>OAuth tokens are used solely to perform requested upload actions for connected accounts.</p>
        <p>We do not sell personal data. Access is limited to internal operators.</p>
        <p>You can request account disconnection and data removal at any time.</p>
      </section>

      <p className="text-sm">
        Privacy requests: <a className="underline underline-offset-4" href="mailto:privacy@a17.so">privacy@a17.so</a>
      </p>

      <Link href="/" className="text-sm underline underline-offset-4">
        Back to home
      </Link>
    </main>
  );
}
