/** @type {import('tailwindcss').Config} */

/**
 * EASY CHANGE #4: Accent color switched from Indigo (#6366f1) to
 * Sky Blue / Cyan (#0ea5e9) for a fresher, more distinctive look.
 * To pick a different color yourself, just edit the 3 hex values
 * in `colors.accent` below — everything else updates automatically.
 */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['DM Sans', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        navy: {
          950: '#080d1a',
          900: '#0d1424',
          800: '#111c30',
          700: '#172240',
          600: '#1e2d52',
        },
        accent: {
          DEFAULT: '#0ea5e9',   // ← was #6366f1 (indigo) → now sky blue
          hover:   '#0284c7',   // ← was #4f46e5
          muted:   'rgba(14,165,233,0.15)',  // ← was rgba(99,102,241,0.15)
        },
        success: '#22c55e',
        warning: '#f59e0b',
        danger:  '#ef4444',
      },
      animation: {
        'fade-up':     'fadeUp 0.5s ease forwards',
        'fade-in':     'fadeIn 0.4s ease forwards',
        'slide-right': 'slideRight 0.3s ease forwards',
        'pulse-slow':  'pulse 3s cubic-bezier(0.4,0,0.6,1) infinite',
        'spin-slow':   'spin 3s linear infinite',
      },
      keyframes: {
        fadeUp:     { from: { opacity: 0, transform: 'translateY(16px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        fadeIn:     { from: { opacity: 0 }, to: { opacity: 1 } },
        slideRight: { from: { opacity: 0, transform: 'translateX(-12px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
      },
    },
  },
  plugins: [],
}
