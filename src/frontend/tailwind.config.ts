import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "neuropit-black": "#050505",
        "neuropit-dark": "#0f1115",
        "neuropit-panel": "#13161c",
        "neuropit-red": "#E4002B",
        "neuropit-amber": "#f59e0b",
        "neuropit-emerald": "#10b981",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
