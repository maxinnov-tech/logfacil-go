/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'brand-dark': '#1a1a2e',
        'brand-light': '#f5f7fa',
        'accent-blue': '#3498db',
        'accent-green': '#2ecc71',
      },
      backdropBlur: {
        xs: '2px',
      }
    },
  },
  plugins: [],
}
