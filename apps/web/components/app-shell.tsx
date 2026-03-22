import Link from "next/link";
import type { ReactNode } from "react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/jobs", label: "Jobs" },
  { href: "/accounts", label: "Accounts" },
  { href: "/content", label: "Content" },
  { href: "/outreach", label: "Outreach" },
  { href: "/affiliate", label: "Affiliate" },
  { href: "/settings", label: "Settings" },
];

type AppShellProps = {
  current: string;
  eyebrow: string;
  title: string;
  summary: string;
  children: ReactNode;
};

export function AppShell({ current, eyebrow, title, summary, children }: AppShellProps) {
  const currentItem = NAV_ITEMS.find((item) => item.href === current);

  return (
    <div className="shell">
      <aside className="shell__rail">
        <div className="shell__rail-header">
          <p className="shell__eyebrow">Creator Growth Control</p>
          <h1 className="shell__brand">Creator Growth Control Plane</h1>
          <p className="shell__subtitle">Compact command center for jobs, content, outreach, and profit visibility.</p>
        </div>
        <nav className="shell__nav" aria-label="Primary navigation">
          {NAV_ITEMS.map((item) => (
            <Link key={item.href} className={current === item.href ? "shell__nav-link shell__nav-link--active" : "shell__nav-link"} href={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="shell__note">
          <span className="shell__note-label">Now viewing</span>
          <p>
            <strong>{currentItem?.label ?? "Dashboard"}</strong>
            {" "}
            panel. Follow live jobs, inspect outcomes, and intervene without switching tools.
          </p>
        </div>
      </aside>
      <main className="shell__main">
        <section className="hero">
          <p className="hero__eyebrow">{eyebrow}</p>
          <h2 className="hero__title">{title}</h2>
          <p className="hero__summary">{summary}</p>
        </section>
        <section className="shell__content">{children}</section>
      </main>
    </div>
  );
}
