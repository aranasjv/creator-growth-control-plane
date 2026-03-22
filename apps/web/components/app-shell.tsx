import Link from "next/link";
import type { ReactNode } from "react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/jobs", label: "Jobs" },
  { href: "/accounts", label: "Accounts" },
  { href: "/content", label: "Content" },
  { href: "/outreach", label: "Outreach" },
  { href: "/affiliate", label: "Affiliate" },
];

type AppShellProps = {
  current: string;
  eyebrow: string;
  title: string;
  summary: string;
  children: ReactNode;
};

export function AppShell({ current, eyebrow, title, summary, children }: AppShellProps) {
  return (
    <div className="shell">
      <aside className="shell__rail">
        <p className="shell__eyebrow">Creator Growth Control</p>
        <h1 className="shell__brand">Watch the bots. Guard the margin.</h1>
        <nav className="shell__nav" aria-label="Primary navigation">
          {NAV_ITEMS.map((item) => (
            <Link key={item.href} className={current === item.href ? "shell__nav-link shell__nav-link--active" : "shell__nav-link"} href={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="shell__note">
          <span className="shell__note-label">Control Plane</span>
          <p>Next.js dashboard, ASP.NET Core orchestrator, Python workers, Postgres, Redis, and your existing automation flows behind one command center.</p>
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
