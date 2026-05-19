/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Motiva Sans"', '"Noto Sans"', 'Inter', 'sans-serif'],
      },
      colors: {
        steam: {
          bg:      '#1b2838',
          darker:  '#16202d',
          card:    '#171a21',
          panel:   '#1f2a3a',
          border:  '#2a3f5a',
          blue:    '#66c0f4',
          link:    '#67c1f5',
          light:   '#c7d5e0',
          text:    '#c7d5e0',
          muted:   '#8f98a0',
          dim:     '#67707b',
          green:   '#a4d007',
          greenHi: '#b9e02e',
          orange:  '#dba84e',
        },
        brand: {
          50:  '#e8f4fb',
          100: '#cfeafa',
          200: '#a5d8f5',
          300: '#67c1f5',
          400: '#66c0f4',
          500: '#3a98d6',
          600: '#2f7eb3',
          700: '#256590',
          800: '#1c4d6d',
          900: '#16202d',
          950: '#0e1620',
        },
      },
      borderRadius: {
        steam: '2px',
        'steam-lg': '4px',
      },
      animation: {
        'fade-in': 'fadeIn 0.15s linear',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
