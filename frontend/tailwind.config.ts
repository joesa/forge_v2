import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        void: '#04040a',
        surface: '#080812',
        panel: '#0d0d1f',
        card: '#111125',
        forge: '#63d9ff',
        ember: '#ff6b35',
        gold: '#f5c842',
        jade: '#3dffa0',
        violet: '#b06bff',
      },
      fontFamily: {
        syne: ['Syne', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
} satisfies Config
