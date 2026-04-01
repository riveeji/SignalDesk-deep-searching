import Link from "next/link";
import { useId } from "react";

import { APP_BLURB, APP_LINE, APP_NAME, APP_NAME_CN } from "@/lib/brand";

type BrandMarkProps = {
  href?: string;
  compact?: boolean;
  showSubtitle?: boolean;
  className?: string;
};

export function BrandMark({ href, compact = false, showSubtitle = false, className = "" }: BrandMarkProps) {
  const content = (
    <div className={`inline-flex items-center ${compact ? "gap-3" : "gap-4"} ${className}`.trim()}>
      <span
        className={`relative flex shrink-0 items-center justify-center overflow-hidden border border-white/12 bg-[linear-gradient(180deg,rgba(18,21,33,0.94),rgba(9,11,18,0.98))] shadow-[0_18px_48px_rgba(8,7,22,0.32)] ${
          compact ? "h-11 w-11 rounded-2xl" : "h-14 w-14 rounded-[22px]"
        }`}
      >
        <span className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,213,143,0.24),transparent_38%),radial-gradient(circle_at_bottom_right,rgba(127,212,255,0.2),transparent_42%)]" />
        <BrandGlyph className={compact ? "h-8 w-8" : "h-10 w-10"} />
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="font-mono text-[11px] uppercase tracking-[0.28em] text-[var(--accent-soft)]">{APP_NAME_CN}</span>
        <span className={`${compact ? "text-lg" : "text-2xl"} mt-1 leading-none font-semibold tracking-tight text-white`}>
          {APP_NAME}
        </span>
        <span className="mt-1 text-sm text-[var(--muted)]">{APP_LINE}</span>
        {showSubtitle ? <span className="mt-1 max-w-xl text-sm leading-6 text-[var(--muted)]">{APP_BLURB}</span> : null}
      </span>
    </div>
  );

  if (!href) {
    return content;
  }

  return (
    <Link href={href} className="inline-flex">
      {content}
    </Link>
  );
}

type BrandGlyphProps = {
  className?: string;
};

export function BrandGlyph({ className = "h-10 w-10" }: BrandGlyphProps) {
  const gradientId = useId();
  const glowId = useId();

  return (
    <svg viewBox="0 0 64 64" fill="none" aria-hidden="true" className={className}>
      <defs>
        <linearGradient id={gradientId} x1="16" y1="16" x2="48" y2="48" gradientUnits="userSpaceOnUse">
          <stop stopColor="#FFD58F" />
          <stop offset="0.5" stopColor="#F7EFE1" />
          <stop offset="1" stopColor="#7FD4FF" />
        </linearGradient>
        <radialGradient id={glowId} cx="0" cy="0" r="1" gradientTransform="translate(32 28) rotate(90) scale(22)">
          <stop stopColor="#162033" />
          <stop offset="1" stopColor="#0B0F1B" />
        </radialGradient>
      </defs>
      <path d="M32 13L47.5 28.5L32 44L16.5 28.5L32 13Z" fill={`url(#${glowId})`} stroke={`url(#${gradientId})`} strokeWidth="2.2" />
      <path d="M22 22L32 28L42 22" stroke={`url(#${gradientId})`} strokeWidth="2" strokeLinecap="round" />
      <path d="M22 36L32 28L42 36" stroke={`url(#${gradientId})`} strokeWidth="2" strokeLinecap="round" />
      <path d="M18 18L32 28L46 18" stroke="rgba(255,255,255,0.26)" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M32 28V48" stroke="rgba(255,255,255,0.24)" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="18" cy="18" r="3.2" fill="#FFD58F" />
      <circle cx="46" cy="18" r="3.2" fill="#7FD4FF" />
      <circle cx="32" cy="48" r="3.5" fill="#F7EFE1" />
      <circle cx="32" cy="28" r="4.2" fill="#0B0F1B" stroke={`url(#${gradientId})`} strokeWidth="1.8" />
    </svg>
  );
}
