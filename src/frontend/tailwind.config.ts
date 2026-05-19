import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'neuropit-black': '#0a0a0a',
        'neuropit-dark': '#1a1a1a',
        'neuropit-red': '#E4002B',
      },
    },
  },
  plugins: [],
}
export default config
