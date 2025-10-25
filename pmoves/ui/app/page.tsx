import Link from 'next/link';

export default function HomePage() {
  return (
    <main
      style={{
        display: 'flex',
        minHeight: '100vh',
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: '1.5rem',
        textAlign: 'center'
      }}
    >
      <h1>PMOVES Operator Console</h1>
      <p>Authentication is required to access internal tooling.</p>
      <Link
        href="/login"
        style={{
          padding: '0.75rem 1.5rem',
          borderRadius: '9999px',
          background: 'rgba(255,255,255,0.1)',
          border: '1px solid rgba(148, 163, 184, 0.4)',
          color: '#f8fafc'
        }}
      >
        Continue to login
      </Link>
    </main>
  );
}
