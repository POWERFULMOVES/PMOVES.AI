import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          sky: 'var(--color-brand-sky)',
          crimson: 'var(--color-brand-crimson)',
          forest: 'var(--color-brand-forest)',
          slate: 'var(--color-brand-slate)',
          gold: 'var(--color-brand-gold)',
          rust: 'var(--color-brand-rust)',
          surface: 'var(--color-brand-surface)',
          'surface-muted': 'var(--color-brand-surface-muted)',
          ink: 'var(--color-brand-ink)',
          'ink-strong': 'var(--color-brand-ink-strong)',
          muted: 'var(--color-brand-muted)',
          subtle: 'var(--color-brand-subtle)',
          border: 'var(--color-brand-border)',
          inverse: 'var(--color-brand-inverse)',
        },
      },
    },
  },
  plugins: [],
};

export default config;
