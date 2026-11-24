import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#201a35",
        plum: "#2a2342",
        paper: "#fbf9ff",
        violet: "#5a47a8",
        lav: {
          50: "#f6f2fd",
          100: "#ede6fb",
          200: "#ddd1f6",
          300: "#cfc1ef",
          400: "#b3a2e3",
          500: "#8e79cf",
        },
      },
      fontFamily: {
        sans: ["Manrope", "ui-sans-serif", "system-ui", "sans-serif"],
        serif: ["Instrument Serif", "Georgia", "serif"],
      },
      borderRadius: {
        "4xl": "28px",
      },
    },
  },
  plugins: [],
};

export default config;
