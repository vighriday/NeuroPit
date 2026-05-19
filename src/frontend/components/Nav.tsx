"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "Mission Control" },
  { href: "/ghost-lap", label: "Ghost Lap" },
  { href: "/counterfactual", label: "Counterfactual" },
  { href: "/explainability", label: "Explainability" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-2 mb-6 border-b border-gray-800 pb-3 text-sm tracking-widest uppercase">
      {TABS.map((tab) => {
        const active = pathname === tab.href;
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={`px-3 py-1 rounded border transition-colors ${
              active
                ? "border-red-700/60 bg-red-900/20 text-red-300"
                : "border-gray-800 text-gray-400 hover:text-gray-200 hover:border-gray-600"
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
