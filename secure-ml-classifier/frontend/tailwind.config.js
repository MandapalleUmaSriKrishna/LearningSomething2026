/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: '#0f172a',
        panel: '#111c33',
        edge: '#1e2a45',
        accent: '#38bdf8',
      },
    },
  },
  plugins: [],
}
