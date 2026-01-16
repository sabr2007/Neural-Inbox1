/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Telegram theme colors
        tg: {
          bg: 'var(--tg-theme-bg-color, #ffffff)',
          text: 'var(--tg-theme-text-color, #000000)',
          hint: 'var(--tg-theme-hint-color, #999999)',
          link: 'var(--tg-theme-link-color, #2481cc)',
          button: 'var(--tg-theme-button-color, #2481cc)',
          'button-text': 'var(--tg-theme-button-text-color, #ffffff)',
          'secondary-bg': 'var(--tg-theme-secondary-bg-color, #f0f0f0)',
        },
        // App accent colors
        primary: {
          DEFAULT: '#8B5CF6',
          50: '#F5F3FF',
          100: '#EDE9FE',
          500: '#8B5CF6',
          600: '#7C3AED',
          700: '#6D28D9',
        },
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      animation: {
        'slide-up': 'slide-up 0.3s ease-out',
        'fade-in': 'fade-in 0.2s ease-out',
      },
      keyframes: {
        'slide-up': {
          '0%': { transform: 'translateY(100%)' },
          '100%': { transform: 'translateY(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
