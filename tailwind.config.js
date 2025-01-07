/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        'off-white': '#F7F7F7',
        'coral': '#FF6E40',
        'coral-dark': '#FF5722',
        'electric-blue': '#007BFF',
        'electric-blue-dark': '#0056b3',
        'spotify-green': '#1DB954',
        'spotify-green-dark': '#1AA34A',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
      }
    },
  },
  plugins: [],
  safelist: [
    'opacity-25',
    'opacity-20',
    'opacity-15',
    // ... add other opacity values you need
  ],
}

