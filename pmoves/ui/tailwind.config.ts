import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './runtime/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        void: {
          DEFAULT: 'var(--void)',
          elevated: 'var(--void-elevated)',
          soft: 'var(--void-soft)',
        },
        cata: {
          cyan: 'var(--cata-cyan)',
          'cyan-dim': 'var(--cata-cyan-dim)',
          ember: 'var(--cata-ember)',
          'ember-dim': 'var(--cata-ember-dim)',
          forest: 'var(--cata-forest)',
          'forest-dim': 'var(--cata-forest-dim)',
          gold: 'var(--cata-gold)',
          'gold-dim': 'var(--cata-gold-dim)',
          violet: 'var(--cata-violet)',
          'violet-dim': 'var(--cata-violet-dim)',
        },
        ink: {
          DEFAULT: 'var(--ink-primary)',
          primary: 'var(--ink-primary)',
          secondary: 'var(--ink-secondary)',
          muted: 'var(--ink-muted)',
          inverse: 'var(--ink-inverse)',
        },
        surface: {
          glass: 'var(--surface-glass)',
          'glass-hover': 'var(--surface-glass-hover)',
          card: 'var(--surface-card)',
        },
        border: {
          subtle: 'var(--border-subtle)',
          strong: 'var(--border-strong)',
        },
        // Legacy compat
        brand: {
          sky: 'var(--cata-cyan)',
          crimson: 'var(--cata-ember)',
          forest: 'var(--cata-forest)',
          gold: 'var(--cata-gold)',
          slate: 'var(--ink-muted)',
          surface: 'var(--void)',
          ink: 'var(--ink-primary)',
        },
      },
      fontFamily: {
        display: ['var(--font-display)'],
        pixel: ['var(--font-pixel)'],
        mono: ['var(--font-mono)'],
        body: ['var(--font-body)'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '1' }],
        '10xl': ['10rem', { lineHeight: '0.85' }],
        '11xl': ['12rem', { lineHeight: '0.85' }],
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
        '128': '32rem',
      },
      animation: {
        'fade-in-up': 'fadeInUp 0.8s var(--ease-out-expo) forwards',
        'fade-in-left': 'fadeInLeft 0.8s var(--ease-out-expo) forwards',
        'scale-in': 'scaleIn 0.6s var(--ease-out-expo) forwards',
        'pulse-glow': 'pulse-glow 4s ease-in-out infinite',
        'float': 'float 6s ease-in-out infinite',
        'drift': 'drift 60s linear infinite',
      },
      keyframes: {
        fadeInUp: {
          from: { opacity: '0', transform: 'translateY(30px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        fadeInLeft: {
          from: { opacity: '0', transform: 'translateX(-30px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        scaleIn: {
          from: { opacity: '0', transform: 'scale(0.95)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        'pulse-glow': {
          '0%, 100%': { opacity: '0.5', filter: 'blur(40px)' },
          '50%': { opacity: '0.8', filter: 'blur(60px)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0) rotate(0deg)' },
          '50%': { transform: 'translateY(-20px) rotate(2deg)' },
        },
        drift: {
          from: { transform: 'rotate(0deg)' },
          to: { transform: 'rotate(360deg)' },
        },
      },
      transitionTimingFunction: {
        'out-expo': 'cubic-bezier(0.16, 1, 0.3, 1)',
        'out-back': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        'glow-cyan': 'radial-gradient(ellipse at center, var(--cata-cyan) 0%, transparent 70%)',
        'glow-ember': 'radial-gradient(ellipse at center, var(--cata-ember) 0%, transparent 70%)',
        'glow-violet': 'radial-gradient(ellipse at center, var(--cata-violet) 0%, transparent 70%)',
      },
      boxShadow: {
        'glow-cyan': '0 0 40px -10px var(--cata-cyan)',
        'glow-ember': '0 0 40px -10px var(--cata-ember)',
        'glow-gold': '0 0 40px -10px var(--cata-gold)',
        'glow-forest': '0 0 40px -10px var(--cata-forest)',
        'glow-violet': '0 0 40px -10px var(--cata-violet)',
        brutal: '0 20px 40px -20px rgba(0, 0, 0, 0.5)',
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
};

export default config;
