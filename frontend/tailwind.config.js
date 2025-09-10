/* * @type {import('tailwindcss').Config} */
// Tailwind setup for the AI commerce frontend
// Pretty standard config - just scanning our React components for CSS classes
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: { extend: {} },
  plugins: [],
};
