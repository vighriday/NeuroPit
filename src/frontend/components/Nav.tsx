"use client";

import Image from "next/image";
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
    <nav className="flex items-center gap-4 mb-6 border-b border-gray-800 pb-3 text-sm tracking-widest uppercase">
      <Link href="/" className="flex items-center gap-2 mr-2 shrink-0">
        <Image
          src="/neuropit-logo.png"
          alt="NeuroPit"
          width={36}
          height={36}
          priority
          className="rounded"
        />
        <span className="hidden md:inline text-gray-200 font-semibold">NeuroPit</span>
      </Link>
      <div className="flex gap-2 flex-wrap">
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
      </div>
    </nav>
  );
}
