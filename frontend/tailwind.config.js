/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        canvas: {
          bg: "#1a1a2e",
          grid: "#16213e",
          node: "#0f3460",
          accent: "#e94560",
          border: "#ffffff1a",
        },
      },
    },
  },
  plugins: [],
};
