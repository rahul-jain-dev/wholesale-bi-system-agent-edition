import { useState } from "react";
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, ScatterChart, Scatter, ZAxis,
} from "recharts";

// ── Tokens ───────────────────────────────────────────────────────────────────
const T = {
  appBg: "#0B0E14",
  sidebarBg: "#10141B",
  card: "#151A23",
  cardElevated: "#1A202B",
  border: "#232A36",
  borderStrong: "#2E3644",
  textPrimary: "#E8ECF3",
  textSecondary: "#9AA4B2",
  textMuted: "#6B7482",
  accent: "#6D5BF0",
  link: "#8B7CF7",
  success: "#34D399",
  warning: "#F5B84C",
  danger: "#F0616D",
  critical: "#E5484D",
  info: "#4C9AFF",
  gold: "#E7B93C",
  segAtRisk: "#F58A4C",
};

// ── Indian number format ──────────────────────────────────────────────────────
function inr(v: number): string {
  if (v >= 10_000_000) return `₹${(v / 10_000_000).toFixed(2)}Cr`;
  if (v >= 100_000)    return `₹${(v / 100_000).toFixed(1)}L`;
  if (v >= 1_000)      return `₹${(v / 1_000).toFixed(1)}K`;
  return `₹${v}`;
}

// ── Raw rupee string (like ₹2,72,414) ────────────────────────────────────────
function inrExact(v: number): string {
  return "₹" + v.toLocaleString("en-IN");
}

// ── Chart data ────────────────────────────────────────────────────────────────
const revenueData = [
  { m: "Oct'22", rev: 18.4 }, { m: "Nov'22", rev: 21.2 }, { m: "Dec'22", rev: 24.8 },
  { m: "Jan'23", rev: 22.6 }, { m: "Feb'23", rev: 19.9 }, { m: "Mar'23", rev: 28.1 },
  { m: "Apr'23", rev: 23.4 }, { m: "May'23", rev: 25.6 }, { m: "Jun'23", rev: 22.1 },
  { m: "Jul'23", rev: 26.8 }, { m: "Aug'23", rev: 29.3 }, { m: "Sep'23", rev: 27.0 },
  { m: "Oct'23", rev: 24.2 }, { m: "Nov'23", rev: 26.7 }, { m: "Dec'23", rev: 31.4 },
  { m: "Jan'24", rev: 27.5 }, { m: "Feb'24", rev: 23.8 }, { m: "Mar'24", rev: 34.2 },
  { m: "Apr'24", rev: 28.6 }, { m: "May'24", rev: 30.1 }, { m: "Jun'24", rev: 25.9 },
  { m: "Jul'24", rev: 32.4 }, { m: "Aug'24", rev: 35.6 }, { m: "Sep'24", rev: 27.0 },
];
const receivablesData = [
  { m: "Oct'23", val: 28.4 }, { m: "Nov'23", val: 31.2 }, { m: "Dec'23", val: 26.8 },
  { m: "Jan'24", val: 33.4 }, { m: "Feb'24", val: 29.6 }, { m: "Mar'24", val: 38.1 },
  { m: "Apr'24", val: 34.7 }, { m: "May'24", val: 36.2 }, { m: "Jun'24", val: 31.9 },
  { m: "Jul'24", val: 39.4 }, { m: "Aug'24", val: 42.1 }, { m: "Sep'24", val: 45.9 },
];
const townData = [
  { town: "Tonk", sales: 2207 }, { town: "Uniara", sales: 1124 },
  { town: "Sawai M.", sales: 876 }, { town: "Malpura", sales: 743 },
  { town: "Niwai", sales: 612 }, { town: "Deoli", sales: 498 },
  { town: "Todaraisingh", sales: 421 }, { town: "Khanpur", sales: 318 },
];

// ── Shared primitives ─────────────────────────────────────────────────────────
type BadgeTone = "success" | "warning" | "danger" | "info" | "neutral" | "orange";
const badgeToneMap: Record<BadgeTone, { bg: string; color: string }> = {
  success: { bg: `${T.success}18`, color: T.success },
  warning: { bg: `${T.warning}18`, color: T.warning },
  danger:  { bg: `${T.danger}18`,  color: T.danger },
  info:    { bg: `${T.info}18`,    color: T.info },
  neutral: { bg: T.cardElevated,   color: T.textSecondary },
  orange:  { bg: `${T.segAtRisk}18`, color: T.segAtRisk },
};

function Badge({ label, tone = "neutral" }: { label: string; tone?: BadgeTone }) {
  const { bg, color } = badgeToneMap[tone];
  return (
    <span style={{
      fontSize: 10, fontWeight: 600, textTransform: "uppercase" as const,
      letterSpacing: "0.07em", background: bg, color, padding: "3px 8px",
      borderRadius: 999, display: "inline-block", whiteSpace: "nowrap" as const,
    }}>
      {label}
    </span>
  );
}

function Chip({
  label, active = false, color, onClick,
}: {
  label: string; active?: boolean; color?: string; onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        fontSize: 11, fontWeight: 500, padding: "3px 10px", borderRadius: 999,
        border: `1px solid ${active ? (color ?? T.accent) : T.border}`,
        background: active ? `${color ?? T.accent}18` : "transparent",
        color: active ? (color ?? T.link) : T.textSecondary,
        cursor: onClick ? "pointer" : "default",
        whiteSpace: "nowrap" as const, transition: "all 0.1s",
      }}
    >
      {label}
    </button>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 style={{
      fontSize: 16, lineHeight: "24px", fontWeight: 600, color: T.textPrimary,
      margin: "0 0 14px", display: "flex", alignItems: "center", gap: 8,
    }}>
      {children}
    </h2>
  );
}

function Divider() {
  return <div style={{ height: 1, background: T.border, margin: "28px 0" }} />;
}

// ── ChartTooltip ──────────────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: T.cardElevated, border: `1px solid ${T.borderStrong}`,
      borderRadius: 8, padding: "8px 12px", fontSize: 12, color: T.textPrimary,
    }}>
      <div style={{ color: T.textMuted, marginBottom: 2 }}>{label}</div>
      <div style={{ fontWeight: 600 }}>₹{payload[0].value.toFixed(1)}L</div>
    </div>
  );
}
function TownTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: T.cardElevated, border: `1px solid ${T.borderStrong}`,
      borderRadius: 8, padding: "8px 12px", fontSize: 12, color: T.textPrimary,
    }}>
      <div style={{ color: T.textMuted, marginBottom: 2 }}>{label}</div>
      <div style={{ fontWeight: 600 }}>₹{payload[0].value.toFixed(0)}K</div>
    </div>
  );
}

// ── Segmented Control ─────────────────────────────────────────────────────────
function SegControl({
  options, value, onChange, small,
}: {
  options: string[]; value: string; onChange: (v: string) => void; small?: boolean;
}) {
  return (
    <div style={{
      display: "inline-flex", background: T.appBg,
      border: `1px solid ${T.border}`, borderRadius: 8, padding: 3, gap: 2,
    }}>
      {options.map(opt => (
        <button
          key={opt}
          onClick={() => onChange(opt)}
          style={{
            fontSize: small ? 11 : 12, fontWeight: 500,
            padding: small ? "4px 10px" : "5px 14px", borderRadius: 6,
            border: "none", cursor: "pointer", transition: "all 0.1s",
            background: value === opt ? T.accent : "transparent",
            color: value === opt ? "#fff" : T.textSecondary,
            whiteSpace: "nowrap" as const,
          }}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}

// ── Sidebar ───────────────────────────────────────────────────────────────────
const navItems = [
  { id: "command",   icon: "⚡", label: "Command Center" },
  { id: "recovery",  icon: "💳", label: "Revenue Recovery & Risk" },
  { id: "inventory", icon: "📦", label: "Inventory & Operations" },
  { id: "customers", icon: "👥", label: "Customer Intelligence" },
  { id: "ai",        icon: "🤖", label: "AI Business Analyst" },
];

function Sidebar({ active, onNav }: { active: string; onNav: (id: string) => void }) {
  return (
    <div style={{
      width: 260, flexShrink: 0, background: T.sidebarBg,
      borderRight: `1px solid ${T.border}`, display: "flex",
      flexDirection: "column", height: "100vh", position: "sticky", top: 0,
    }}>
      <div style={{ padding: "20px 18px 16px", borderBottom: `1px solid ${T.border}` }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8, background: T.accent,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 18, flexShrink: 0, marginTop: 1,
          }}>⚡</div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: T.textPrimary, lineHeight: "18px", letterSpacing: "-0.01em" }}>
              Wholesale BI System
            </div>
            <div style={{ fontSize: 10, color: T.textMuted, lineHeight: "15px", marginTop: 1 }}>
              AI Decision Support for Indian Distributors
            </div>
          </div>
        </div>
      </div>
      <nav style={{ flex: 1, padding: "10px 8px", overflowY: "auto" }}>
        {navItems.map(item => {
          const isActive = item.id === active;
          return (
            <button
              key={item.id}
              onClick={() => onNav(item.id)}
              style={{
                display: "flex", alignItems: "center", gap: 10, width: "100%",
                padding: "9px 12px", borderRadius: 8, border: "none", cursor: "pointer",
                marginBottom: 1, background: isActive ? `${T.accent}18` : "transparent",
                color: isActive ? T.textPrimary : T.textSecondary, textAlign: "left",
                transition: "all 0.1s", position: "relative",
              }}
            >
              <span style={{ fontSize: 16, flexShrink: 0, lineHeight: 1 }}>{item.icon}</span>
              <span style={{ fontSize: 13, fontWeight: isActive ? 600 : 400, lineHeight: "18px" }}>{item.label}</span>
              {isActive && (
                <div style={{
                  position: "absolute", right: 0, top: "50%", transform: "translateY(-50%)",
                  width: 3, height: 18, background: T.accent, borderRadius: "2px 0 0 2px",
                }} />
              )}
            </button>
          );
        })}
      </nav>
      <div style={{ margin: "0 8px 8px", padding: "12px 14px", background: T.card, border: `1px solid ${T.border}`, borderRadius: 10 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 6, fontSize: 11, color: T.textSecondary, lineHeight: "17px" }}>
          <span style={{ color: T.success, fontSize: 10, marginTop: 3, flexShrink: 0 }}>●</span>
          <span>
            <span style={{ color: T.success, fontWeight: 600 }}>Demo Data Loaded</span><br />
            24,806 Sales Transactions<br />380 Customers
          </span>
        </div>
      </div>
      <div style={{ padding: "12px 18px 18px", borderTop: `1px solid ${T.border}` }}>
        <div style={{ fontSize: 10, color: T.textMuted, fontWeight: 500, marginBottom: 5 }}>API Credits</div>
        <div style={{ height: 3, background: T.border, borderRadius: 2, overflow: "hidden", marginBottom: 5 }}>
          <div style={{ height: "100%", width: "62%", background: T.accent, borderRadius: 2 }} />
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: T.textMuted }}>
          <span>620 / 1,000 used</span>
          <a href="#" style={{ color: T.link, textDecoration: "none" }}>Upgrade</a>
        </div>
      </div>
    </div>
  );
}

// ── Page header shared ────────────────────────────────────────────────────────
function PageHeader({ emoji, title, subtitle }: { emoji: string; title: string; subtitle: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
      <div>
        <h1 style={{ fontSize: 24, lineHeight: "32px", fontWeight: 600, color: T.textPrimary, margin: "0 0 4px", letterSpacing: "-0.015em" }}>
          {emoji} {title}
        </h1>
        <p style={{ fontSize: 13, color: T.textSecondary, margin: 0, lineHeight: "20px" }}>{subtitle}</p>
      </div>
      <div style={{ textAlign: "right", fontSize: 12, lineHeight: "20px", color: T.textMuted, flexShrink: 0 }}>
        <div style={{ fontWeight: 500, color: T.textSecondary }}>Business: Tonk, Rajasthan</div>
        <div>ERP: Kuber / Tally / Marg</div>
        <div style={{ marginTop: 3 }}>FY 2024–25</div>
      </div>
    </div>
  );
}

// ── KPI Tile ──────────────────────────────────────────────────────────────────
function KpiTile({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: T.appBg, border: `1px solid ${T.border}`, borderRadius: 8, padding: "12px 16px" }}>
      <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.08em", color: T.textMuted, marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 22, lineHeight: "28px", fontWeight: 600, color: T.textPrimary, fontVariantNumeric: "tabular-nums" }}>
        {value}
      </div>
    </div>
  );
}

// ── Exec KPI card ─────────────────────────────────────────────────────────────
function ExecKpi({ label, value, context, tone }: { label: string; value: string; context: string; tone: BadgeTone }) {
  const { color } = badgeToneMap[tone];
  const isNeutral = tone === "neutral";
  return (
    <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "18px 20px", flex: 1 }}>
      <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ fontSize: 26, lineHeight: "32px", fontWeight: 600, color: T.textPrimary, fontVariantNumeric: "tabular-nums", marginBottom: 6 }}>
        {value}
      </div>
      <div style={{ fontSize: 12, color: isNeutral ? T.textSecondary : color, fontWeight: isNeutral ? 400 : 500 }}>
        {context}
      </div>
    </div>
  );
}

// ── Insight Card ──────────────────────────────────────────────────────────────
function InsightCard({ icon, topic, tone, headline, evidence, action }: {
  icon: string; topic: string; tone: BadgeTone;
  headline: string; evidence: string; action: string;
}) {
  const { color } = badgeToneMap[tone];
  return (
    <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "18px 20px", display: "flex", gap: 14 }}>
      <div style={{ width: 8, height: 8, borderRadius: "50%", background: color, boxShadow: `0 0 6px ${color}80`, flexShrink: 0, marginTop: 5 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ marginBottom: 7 }}>
          <span style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.1em", color, background: `${color}15`, padding: "2px 7px", borderRadius: 999 }}>
            {icon} {topic}
          </span>
        </div>
        <div style={{ fontSize: 14, fontWeight: 600, color: T.textPrimary, marginBottom: 5, lineHeight: "20px" }}>{headline}</div>
        <div style={{ fontSize: 12, color: T.textSecondary, lineHeight: "18px", marginBottom: 10 }}>{evidence}</div>
        <a href="#" style={{ fontSize: 12, color: T.link, textDecoration: "none", fontWeight: 500 }}>{action}</a>
      </div>
    </div>
  );
}

// ── Priority Row ──────────────────────────────────────────────────────────────
type Urgency = "HIGH" | "MEDIUM" | "LOW";
const urgencyMap: Record<Urgency, { bg: string; color: string }> = {
  HIGH:   { bg: `${T.danger}20`,  color: T.danger },
  MEDIUM: { bg: `${T.warning}20`, color: T.warning },
  LOW:    { bg: `${T.success}20`, color: T.success },
};
function PriorityRow({ urgency, title, reason, impact, action }: {
  urgency: Urgency; title: string; reason: string; impact?: number; action: string;
}) {
  const { bg, color } = urgencyMap[urgency];
  const [hov, setHov] = useState(false);
  return (
    <div
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{
        display: "flex", alignItems: "center", gap: 16, padding: "13px 18px",
        borderRadius: 10, border: `1px solid ${hov ? T.borderStrong : T.border}`,
        background: hov ? T.cardElevated : T.card, transition: "all 0.12s",
      }}
    >
      <span style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.07em", background: bg, color, padding: "3px 9px", borderRadius: 999, whiteSpace: "nowrap" as const, flexShrink: 0 }}>
        {urgency}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary, marginBottom: 2 }}>{title}</div>
        <div style={{ fontSize: 12, color: T.textSecondary }}>{reason}</div>
      </div>
      {impact !== undefined && (
        <div style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary, fontVariantNumeric: "tabular-nums", minWidth: 70, textAlign: "right", flexShrink: 0 }}>
          {inr(impact)}
        </div>
      )}
      <button
        style={{ fontSize: 12, fontWeight: 500, color: T.accent, border: `1px solid ${T.accent}50`, background: "transparent", padding: "5px 14px", borderRadius: 8, cursor: "pointer", whiteSpace: "nowrap", flexShrink: 0 }}
        onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = `${T.accent}15`; (e.currentTarget as HTMLButtonElement).style.borderColor = T.accent; }}
        onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = "transparent"; (e.currentTarget as HTMLButtonElement).style.borderColor = `${T.accent}50`; }}
      >
        {action}
      </button>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// REVENUE RECOVERY & RISK SCREEN
// ══════════════════════════════════════════════════════════════════════════════
interface LedgerRow {
  id: string;
  town: string;
  customer: string;
  invoice: string;
  invoiceDate: string;
  dueDate: string;
  outstanding: number;
  daysOverdue: number | null;
  dueSoon?: string;
  riskTier: "WRITE-OFF" | "HIGH" | "MEDIUM" | "LOW";
  riskTone: BadgeTone;
  collProb: number;
  expectedRecovery: number;
  payStatus: "UNPAID" | "PARTIAL" | "PAID";
  payTone: BadgeTone;
  state: string;
  stateTone: BadgeTone;
  lastAction: string;
}

const ledgerData: LedgerRow[] = [
  { id: "1", town: "Tonk",    customer: "Patel Stores",        invoice: "INV-2043", invoiceDate: "12-Apr-24", dueDate: "12-May-24", outstanding: 272414, daysOverdue: 149,  riskTier: "WRITE-OFF", riskTone: "danger",  collProb: 30, expectedRecovery: 81700,  payStatus: "UNPAID",  payTone: "danger",  state: "ESCALATED",       stateTone: "danger",  lastAction: "Escalation call 02-Sep"  },
  { id: "2", town: "Tonk",    customer: "Yadav Traders",       invoice: "INV-1987", invoiceDate: "14-Sep-22", dueDate: "14-Oct-22", outstanding: 93500,  daysOverdue: 669,  riskTier: "WRITE-OFF", riskTone: "danger",  collProb: 10, expectedRecovery: 9400,   payStatus: "UNPAID",  payTone: "danger",  state: "ESCALATED",       stateTone: "danger",  lastAction: "Legal notice 15-Aug"     },
  { id: "3", town: "Uniara",  customer: "Sharma Kirana",       invoice: "INV-2210", invoiceDate: "28-Aug-24", dueDate: "27-Sep-24", outstanding: 41200,  daysOverdue: 12,   riskTier: "MEDIUM",    riskTone: "warning", collProb: 68, expectedRecovery: 28000,  payStatus: "PARTIAL", payTone: "warning", state: "FIRST REMINDER",  stateTone: "warning", lastAction: "WA sent 03-Sep"          },
  { id: "4", town: "Malpura", customer: "Gupta General Store", invoice: "INV-2288", invoiceDate: "03-Sep-24", dueDate: "03-Oct-24", outstanding: 18750,  daysOverdue: null, riskTier: "LOW",       riskTone: "success", collProb: 87, expectedRecovery: 16300,  payStatus: "UNPAID",  payTone: "danger",  state: "IDENTIFIED",      stateTone: "info",    lastAction: "Auto-identified 04-Sep", dueSoon: "due in 6d" },
  { id: "5", town: "Niwai",   customer: "Ram Provision Store", invoice: "INV-2156", invoiceDate: "10-Jul-24", dueDate: "09-Aug-24", outstanding: 34600,  daysOverdue: 52,   riskTier: "HIGH",      riskTone: "orange",  collProb: 52, expectedRecovery: 18000,  payStatus: "UNPAID",  payTone: "danger",  state: "SECOND REMINDER", stateTone: "orange",  lastAction: "2nd reminder 01-Sep"     },
  { id: "6", town: "Deoli",   customer: "Mehta Traders",       invoice: "INV-2198", invoiceDate: "22-Aug-24", dueDate: "21-Sep-24", outstanding: 27300,  daysOverdue: 18,   riskTier: "MEDIUM",    riskTone: "warning", collProb: 71, expectedRecovery: 19400,  payStatus: "PARTIAL", payTone: "warning", state: "WAITING",         stateTone: "neutral", lastAction: "Partial rcvd 02-Sep"     },
  { id: "7", town: "Tonk",    customer: "Jain Brothers",       invoice: "INV-2047", invoiceDate: "15-Apr-24", dueDate: "15-May-24", outstanding: 58900,  daysOverdue: 138,  riskTier: "WRITE-OFF", riskTone: "danger",  collProb: 25, expectedRecovery: 14700,  payStatus: "UNPAID",  payTone: "danger",  state: "ESCALATED",       stateTone: "danger",  lastAction: "Escalation call 28-Aug"  },
  { id: "8", town: "Khanpur", customer: "Singh Kirana",        invoice: "INV-2271", invoiceDate: "29-Aug-24", dueDate: "28-Sep-24", outstanding: 12400,  daysOverdue: null, riskTier: "LOW",       riskTone: "success", collProb: 91, expectedRecovery: 11300,  payStatus: "UNPAID",  payTone: "danger",  state: "IDENTIFIED",      stateTone: "info",    lastAction: "Auto-identified 04-Sep", dueSoon: "due in 2d" },
];

const stateStep = (s: string) => ["IDENTIFIED","FIRST REMINDER","WAITING","SECOND REMINDER","ESCALATED","RECOVERED"].indexOf(s);

const recoverySteps = [
  { label: "Identified",       count: 96 },
  { label: "1st Reminder",     count: 74 },
  { label: "Waiting",          count: 41 },
  { label: "2nd Reminder",     count: 28 },
  { label: "Escalated",        count: 23 },
  { label: "Recovered",        count: 40 },
];

const mockLinks: Record<string, string> = {
  "1": "rzp.io/i/pT4xQ2",
  "2": "rzp.io/i/aB9mR7",
  "3": "rzp.io/i/cX2kP5",
};

const waTone: Record<string, { label: string; tone: BadgeTone }> = {
  "1": { label: "FIRM (HIGH RISK)", tone: "danger" },
  "2": { label: "FINAL (ESCALATED)", tone: "danger" },
  "3": { label: "FRIENDLY (MEDIUM)", tone: "warning" },
};

function waMessage(row: LedgerRow) {
  const link = mockLinks[row.id] ?? "rzp.io/i/xxxxxx";
  if (row.riskTier === "WRITE-OFF")
    return `Dear ${row.customer.split(" ")[0]} ji, your invoice ${row.invoice} for ${inrExact(row.outstanding)} is ${row.daysOverdue} days overdue. Please complete payment immediately using ${link} to avoid legal action. — Raj Distributors`;
  return `Dear ${row.customer.split(" ")[0]} ji, your invoice ${row.invoice} for ${inrExact(row.outstanding)} is due. Please clear using ${link} at your earliest convenience. — Raj Distributors`;
}

function riskBadgeTone(tier: string): BadgeTone {
  if (tier === "WRITE-OFF") return "danger";
  if (tier === "HIGH") return "orange";
  if (tier === "MEDIUM") return "warning";
  return "success";
}

function payBadgeTone(s: string): BadgeTone {
  if (s === "UNPAID") return "danger";
  if (s === "PARTIAL") return "warning";
  return "success";
}

function stateBadgeTone(s: string): BadgeTone {
  if (["ESCALATED", "STOPPED"].includes(s)) return "danger";
  if (["SECOND REMINDER", "FIRST REMINDER"].includes(s)) return "warning";
  if (s === "RECOVERED") return "success";
  if (s === "IDENTIFIED") return "info";
  return "neutral";
}

// ── Mono chip (payment link) ──────────────────────────────────────────────────
function MonoChip({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      <span style={{ fontFamily: "monospace", fontSize: 12, color: T.link, background: T.appBg, border: `1px solid ${T.border}`, padding: "3px 10px", borderRadius: 6 }}>
        {value}
      </span>
      <button
        onClick={() => { navigator.clipboard?.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
        style={{ fontSize: 11, color: copied ? T.success : T.textMuted, background: "none", border: "none", cursor: "pointer", padding: 0, fontWeight: 500 }}
      >
        {copied ? "Copied!" : "Copy"}
      </button>
      <button style={{ fontSize: 11, color: T.textMuted, background: "none", border: "none", cursor: "pointer", padding: 0 }}>↻</button>
    </span>
  );
}

// ── WA bubble ─────────────────────────────────────────────────────────────────
function WaBubble({ row, compact }: { row: LedgerRow; compact?: boolean }) {
  const msg = waMessage(row);
  const link = mockLinks[row.id] ?? "rzp.io/i/xxxxxx";
  const wt = waTone[row.id] ?? { label: "STANDARD", tone: "neutral" as BadgeTone };
  return (
    <div style={{ background: "#1F2C34", border: `1px solid ${T.border}`, borderRadius: 12, padding: compact ? "12px 14px" : "14px 16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: T.success }}>{row.customer}</span>
        <Badge label={wt.label} tone={wt.tone} />
      </div>
      <div style={{ fontSize: 12, color: "#D1D7DB", lineHeight: "18px", marginBottom: 8 }}>
        {msg}
      </div>
      <div style={{ fontFamily: "monospace", fontSize: 11, color: T.link, background: "#0D1418", padding: "4px 8px", borderRadius: 5, marginBottom: 8, wordBreak: "break-all" as const }}>
        {link}
      </div>
      {!compact && (
        <div style={{ display: "flex", gap: 8 }}>
          <button style={{ fontSize: 11, color: T.textMuted, background: "none", border: "none", cursor: "pointer", padding: 0 }}>Copy</button>
          <button style={{ fontSize: 11, color: T.textMuted, background: "none", border: "none", cursor: "pointer", padding: 0 }}>↻ Regenerate</button>
        </div>
      )}
    </div>
  );
}

// ── Stepper ───────────────────────────────────────────────────────────────────
function StateStepper({ currentStep }: { currentStep: number }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start" }}>
      {recoverySteps.map((step, i) => {
        const isDone = i < currentStep;
        const isActive = i === currentStep;
        return (
          <div key={step.label} style={{ display: "flex", alignItems: "flex-start", flex: 1 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", width: "100%" }}>
                {i > 0 && <div style={{ flex: 1, height: 1, background: isDone || isActive ? T.accent : T.border }} />}
                <div style={{
                  width: 32, height: 32, borderRadius: "50%", display: "flex", alignItems: "center",
                  justifyContent: "center", flexShrink: 0,
                  background: isActive ? T.accent : isDone ? `${T.accent}30` : T.card,
                  border: `2px solid ${isActive || isDone ? T.accent : T.border}`,
                  fontSize: 12, fontWeight: 700,
                  color: isActive ? "#fff" : isDone ? T.link : T.textMuted,
                }}>
                  {isDone ? "✓" : step.count}
                </div>
                {i < recoverySteps.length - 1 && <div style={{ flex: 1, height: 1, background: isDone ? T.accent : T.border }} />}
              </div>
              <div style={{ fontSize: 11, fontWeight: 500, color: isActive ? T.textPrimary : isDone ? T.textSecondary : T.textMuted, marginTop: 8, textAlign: "center", whiteSpace: "nowrap" }}>
                {step.label}
              </div>
              <div style={{ fontSize: 10, color: T.textMuted, marginTop: 2, fontVariantNumeric: "tabular-nums" }}>
                {step.count}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Immutable ledger data ─────────────────────────────────────────────────────
const auditRows = [
  { ts: "2024-09-04 09:14:22 IST", customer: "Patel Stores",   invoice: "INV-2043", action: "Collection action",       prevState: "SECOND REMINDER", newState: "ESCALATED",     amount: 272414, outcome: "SIMULATED" },
  { ts: "2024-09-04 09:14:18 IST", customer: "Yadav Traders",  invoice: "INV-1987", action: "Payment outcome",          prevState: "ESCALATED",       newState: "ESCALATED",     amount: 0,      outcome: "FAILED"    },
  { ts: "2024-09-04 09:02:05 IST", customer: "Sharma Kirana",  invoice: "INV-2210", action: "Collection run started",   prevState: "IDENTIFIED",      newState: "FIRST REMINDER",amount: 41200,  outcome: "SIMULATED" },
  { ts: "2024-09-04 08:55:41 IST", customer: "Mehta Traders",  invoice: "INV-2198", action: "Payment outcome",          prevState: "FIRST REMINDER",  newState: "WAITING",       amount: 15000,  outcome: "SUCCESS"   },
  { ts: "2024-09-04 08:44:10 IST", customer: "Jain Brothers",  invoice: "INV-2047", action: "Collection action",        prevState: "WAITING",         newState: "SECOND REMINDER",amount: 58900, outcome: "SIMULATED" },
  { ts: "2024-09-04 08:30:03 IST", customer: "(system)",       invoice: "—",        action: "AI query logged",          prevState: "—",               newState: "—",             amount: 0,      outcome: "SUCCESS"   },
];

const outcomeTone: Record<string, BadgeTone> = {
  SUCCESS: "success", FAILED: "danger", SIMULATED: "info",
};

// ── Revenue Recovery Screen ───────────────────────────────────────────────────
function RevenueRecovery() {
  const [townFilter, setTownFilter] = useState("ALL");
  const [viewPill, setViewPill] = useState("LEDGER");
  const [ageingFilter, setAgeingFilter] = useState("All");
  const [searchVal, setSearchVal] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set(["1", "2", "3"]));
  const [showLinks, setShowLinks] = useState(true);
  const [showWA, setShowWA] = useState(true);
  const [detailCustomer, setDetailCustomer] = useState<LedgerRow>(ledgerData[0]);

  const towns = ["ALL", "Tonk", "Uniara", "Deoli", "Niwai", "Malpura", "Todaraisingh", "Khanpur", "Sawai Madhopur"];
  const viewPills = ["LEDGER", "BY TOWN", "BY BEAT"];

  function toggleRow(id: string) {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  const selectedRows = ledgerData.filter(r => selected.has(r.id));
  const selOutstanding = selectedRows.reduce((s, r) => s + r.outstanding, 0);
  const selExpected = selectedRows.reduce((s, r) => s + r.expectedRecovery, 0);
  const selectedWithLink = selectedRows.filter(r => mockLinks[r.id]);

  const thStyle: React.CSSProperties = {
    fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em",
    color: T.textMuted, padding: "9px 10px", textAlign: "left", whiteSpace: "nowrap",
    background: T.appBg, borderBottom: `1px solid ${T.border}`,
  };

  return (
    <div style={{ padding: "0 0 40px" }}>
      {/* Demo-only warning strip */}
      <div style={{
        background: `${T.gold}12`, borderBottom: `1px solid ${T.gold}30`,
        padding: "8px 32px", display: "flex", alignItems: "center", gap: 8,
      }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: T.gold, letterSpacing: "0.1em" }}>DEMO ONLY</span>
        <span style={{ fontSize: 11, color: T.textSecondary }}>
          Mock payment links &amp; simulated outcomes; no real payment processing.
        </span>
      </div>

      <div style={{ padding: "24px 32px 0" }}>
        <PageHeader
          emoji="💳"
          title="Revenue Recovery & Risk"
          subtitle="See every outstanding receivable, prioritize collection, and take controlled recovery actions."
        />

        {/* ── Portfolio KPIs ── */}
        <SectionTitle>📊 Portfolio KPIs</SectionTitle>
        <div style={{ display: "flex", gap: 14, marginBottom: 0 }}>
          <ExecKpi label="Total Receivables" value={inr(4592000)} context="312 open invoices" tone="neutral" />
          <ExecKpi label="Overdue"            value={inr(3870000)} context="214 invoices past due" tone="danger" />
          <ExecKpi label="Due Soon"           value={inr(720000)}  context="Next 14 days" tone="warning" />
          <ExecKpi label="Expected Recovery"  value={inr(1420000)} context="31% of outstanding" tone="neutral" />
          <ExecKpi label="With Outstanding"   value="253"          context="Active customers" tone="neutral" />
        </div>

        <Divider />

        {/* ── Payments on Hold ── */}
        <SectionTitle>💳 Payments on Hold</SectionTitle>
        <div style={{
          background: T.card, border: `1px solid ${T.border}`, borderRadius: 12,
          overflow: "hidden",
        }}>
          {/* Row 1: Town segmented + view pills */}
          <div style={{
            padding: "14px 18px", borderBottom: `1px solid ${T.border}`,
            display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap",
          }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {towns.map(t => (
                <button
                  key={t}
                  onClick={() => setTownFilter(t)}
                  style={{
                    fontSize: 11, fontWeight: 500, padding: "4px 10px", borderRadius: 6,
                    border: `1px solid ${townFilter === t ? T.accent : T.border}`,
                    background: townFilter === t ? `${T.accent}18` : "transparent",
                    color: townFilter === t ? T.link : T.textSecondary, cursor: "pointer", transition: "all 0.1s",
                  }}
                >
                  {t}
                </button>
              ))}
            </div>
            <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
              {viewPills.map(vp => (
                <button
                  key={vp}
                  onClick={() => setViewPill(vp)}
                  style={{
                    fontSize: 11, fontWeight: 600, padding: "4px 12px", borderRadius: 6,
                    border: `1px solid ${viewPill === vp ? T.borderStrong : T.border}`,
                    background: viewPill === vp ? T.cardElevated : "transparent",
                    color: viewPill === vp ? T.textPrimary : T.textMuted, cursor: "pointer",
                    letterSpacing: "0.04em",
                  }}
                >
                  {vp}
                </button>
              ))}
            </div>
          </div>

          {/* Row 2: Filter bar */}
          <div style={{
            padding: "12px 18px", borderBottom: `1px solid ${T.border}`,
            display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
          }}>
            {/* Search */}
            <input
              value={searchVal}
              onChange={e => setSearchVal(e.target.value)}
              placeholder="Search customer / invoice…"
              style={{
                fontSize: 12, padding: "6px 12px", borderRadius: 8, border: `1px solid ${T.border}`,
                background: T.appBg, color: T.textPrimary, outline: "none", width: 200,
              }}
            />
            {/* Beat dropdown */}
            <select style={{ fontSize: 12, padding: "6px 10px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.appBg, color: T.textSecondary, cursor: "pointer" }}>
              <option>Beat: All</option>
              <option>T-04</option><option>T-07</option><option>U-02</option>
            </select>
            {/* Risk chips */}
            <div style={{ display: "flex", gap: 5 }}>
              {["All Risk", "WRITE-OFF", "HIGH", "MEDIUM", "LOW"].map(r => (
                <Chip key={r} label={r} active={r === "All Risk"} />
              ))}
            </div>
            {/* Ageing segmented */}
            <SegControl
              small
              options={["Current", "1–30", "31–60", "61–90", "90+"]}
              value={ageingFilter}
              onChange={setAgeingFilter}
            />
            {/* Payment status chips */}
            <div style={{ display: "flex", gap: 5 }}>
              {["UNPAID", "PARTIAL", "PAID"].map(p => (
                <Chip key={p} label={p} />
              ))}
            </div>
            <a href="#" style={{ fontSize: 11, color: T.link, textDecoration: "none", whiteSpace: "nowrap" }}>More filters</a>
            <button
              onClick={() => { setSearchVal(""); setAgeingFilter("All"); setTownFilter("ALL"); }}
              style={{ fontSize: 11, color: T.textMuted, background: "none", border: "none", cursor: "pointer", padding: 0, whiteSpace: "nowrap" }}
            >
              Clear
            </button>
          </div>

          {/* Row 3: Collection Ledger table */}
          <div style={{ padding: "14px 18px 0", borderBottom: `1px solid ${T.border}` }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: T.textSecondary, marginBottom: 10 }}>🧾 Collection Ledger</div>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 1100 }}>
                <thead>
                  <tr>
                    <th style={{ ...thStyle, width: 36 }}>
                      <input type="checkbox" style={{ accentColor: T.accent }} />
                    </th>
                    <th style={thStyle}>Town</th>
                    <th style={thStyle}>Customer</th>
                    <th style={thStyle}>Invoice</th>
                    <th style={thStyle}>Inv. Date</th>
                    <th style={thStyle}>Due Date</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>Outstanding</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>Days Overdue</th>
                    <th style={thStyle}>Risk</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>Coll. Prob</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>Exp. Recovery</th>
                    <th style={thStyle}>Payment</th>
                    <th style={thStyle}>State</th>
                    <th style={thStyle}>Last Action</th>
                  </tr>
                </thead>
                <tbody>
                  {ledgerData.map((row) => {
                    const isSel = selected.has(row.id);
                    return (
                      <tr
                        key={row.id}
                        onClick={() => { toggleRow(row.id); setDetailCustomer(row); }}
                        style={{
                          background: isSel ? `${T.accent}0A` : "transparent",
                          borderBottom: `1px solid ${T.border}`,
                          cursor: "pointer", transition: "background 0.1s",
                        }}
                        onMouseEnter={e => { if (!isSel) (e.currentTarget as HTMLTableRowElement).style.background = T.cardElevated; }}
                        onMouseLeave={e => { if (!isSel) (e.currentTarget as HTMLTableRowElement).style.background = "transparent"; }}
                      >
                        <td style={{ padding: "10px 10px", textAlign: "center" }}>
                          <input type="checkbox" checked={isSel} onChange={() => toggleRow(row.id)} style={{ accentColor: T.accent }} onClick={e => e.stopPropagation()} />
                        </td>
                        <td style={{ padding: "10px 10px", fontSize: 12, color: T.textSecondary, whiteSpace: "nowrap" }}>{row.town}</td>
                        <td style={{ padding: "10px 10px", fontSize: 13, fontWeight: 500, color: T.textPrimary, whiteSpace: "nowrap" }}>{row.customer}</td>
                        <td style={{ padding: "10px 10px", fontSize: 12, color: T.link, fontFamily: "monospace", whiteSpace: "nowrap" }}>{row.invoice}</td>
                        <td style={{ padding: "10px 10px", fontSize: 12, color: T.textMuted, whiteSpace: "nowrap" }}>{row.invoiceDate}</td>
                        <td style={{ padding: "10px 10px", fontSize: 12, color: T.textMuted, whiteSpace: "nowrap" }}>{row.dueDate}</td>
                        <td style={{ padding: "10px 10px", fontSize: 13, fontWeight: 600, color: T.textPrimary, textAlign: "right", fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>
                          {inrExact(row.outstanding)}
                        </td>
                        <td style={{ padding: "10px 10px", textAlign: "right", whiteSpace: "nowrap" }}>
                          {row.daysOverdue !== null ? (
                            <span style={{ fontSize: 12, fontWeight: 600, color: row.daysOverdue > 90 ? T.critical : row.daysOverdue > 30 ? T.danger : T.warning, fontVariantNumeric: "tabular-nums" }}>
                              {row.daysOverdue}d
                            </span>
                          ) : (
                            <span style={{ fontSize: 11, color: T.success }}>{row.dueSoon}</span>
                          )}
                        </td>
                        <td style={{ padding: "10px 10px" }}><Badge label={row.riskTier} tone={row.riskTone} /></td>
                        <td style={{ padding: "10px 10px", textAlign: "right", whiteSpace: "nowrap" }}>
                          <span style={{ fontSize: 12, fontVariantNumeric: "tabular-nums", color: row.collProb >= 70 ? T.success : row.collProb >= 40 ? T.warning : T.danger, fontWeight: 600 }}>
                            {row.collProb}%
                          </span>
                        </td>
                        <td style={{ padding: "10px 10px", textAlign: "right", fontVariantNumeric: "tabular-nums", fontSize: 12, color: T.textSecondary, whiteSpace: "nowrap" }}>
                          {inr(row.expectedRecovery)}
                        </td>
                        <td style={{ padding: "10px 10px" }}><Badge label={row.payStatus} tone={payBadgeTone(row.payStatus)} /></td>
                        <td style={{ padding: "10px 10px" }}><Badge label={row.state} tone={stateBadgeTone(row.state)} /></td>
                        <td style={{ padding: "10px 10px", fontSize: 11, color: T.textMuted, whiteSpace: "nowrap" }}>{row.lastAction}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {/* Pagination footer */}
            <div style={{ padding: "10px 0 14px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 11, color: T.textMuted }}>312 receivables · page 1 of 13</span>
              <div style={{ display: "flex", gap: 6 }}>
                {["‹", "1", "2", "3", "…", "13", "›"].map((p, i) => (
                  <button key={i} style={{ fontSize: 11, padding: "3px 8px", borderRadius: 5, border: `1px solid ${p === "1" ? T.accent : T.border}`, background: p === "1" ? `${T.accent}18` : "transparent", color: p === "1" ? T.link : T.textMuted, cursor: "pointer" }}>
                    {p}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Row 4: Selection Bar */}
          {selected.size > 0 && (
            <div style={{ padding: "12px 18px", borderBottom: `1px solid ${T.border}`, background: T.cardElevated, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <div style={{ fontSize: 13 }}>
                <span style={{ fontWeight: 600, color: T.textPrimary }}>{selected.size} customer{selected.size > 1 ? "s" : ""} selected</span>
                <span style={{ color: T.textSecondary, fontVariantNumeric: "tabular-nums", marginLeft: 12 }}>{inr(selOutstanding)} outstanding</span>
                <span style={{ color: T.textSecondary, fontVariantNumeric: "tabular-nums", marginLeft: 10 }}>· {inr(selExpected)} expected recovery</span>
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <button
                  onClick={() => setShowLinks(v => !v)}
                  style={{ fontSize: 12, fontWeight: 500, padding: "6px 14px", borderRadius: 8, border: "none", background: T.accent, color: "#fff", cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}>
                  ⚡ Generate Mock Payment Links
                  <span style={{ fontSize: 9, fontWeight: 700, background: T.gold, color: "#000", padding: "1px 5px", borderRadius: 3 }}>DEMO ONLY</span>
                </button>
                <button
                  onClick={() => setShowWA(v => !v)}
                  style={{ fontSize: 12, fontWeight: 500, padding: "6px 14px", borderRadius: 8, border: `1px solid ${T.border}`, background: "transparent", color: T.textSecondary, cursor: "pointer" }}>
                  📱 Generate WhatsApp Messages
                </button>
                <button onClick={() => setSelected(new Set())} style={{ fontSize: 12, color: T.textMuted, background: "none", border: "none", cursor: "pointer" }}>
                  Clear
                </button>
              </div>
            </div>
          )}

          {/* Row 5: Payment Links */}
          {showLinks && selectedWithLink.length > 0 && (
            <div style={{ padding: "14px 18px", borderBottom: `1px solid ${T.border}` }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: T.textSecondary, marginBottom: 10 }}>⚡ Payment Links (Mock)</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {selectedWithLink.map(row => (
                  <div key={row.id} style={{ display: "flex", alignItems: "center", gap: 14, padding: "9px 12px", borderRadius: 8, background: T.appBg, border: `1px solid ${T.border}` }}>
                    <span style={{ fontSize: 13, fontWeight: 500, color: T.textPrimary, minWidth: 160 }}>{row.customer}</span>
                    <span style={{ fontFamily: "monospace", fontSize: 11, color: T.textMuted }}>{row.invoice}</span>
                    <span style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary, fontVariantNumeric: "tabular-nums", minWidth: 90 }}>{inrExact(row.outstanding)}</span>
                    <MonoChip value={mockLinks[row.id]} />
                  </div>
                ))}
              </div>
              <div style={{ fontSize: 10, color: T.textMuted, marginTop: 10, letterSpacing: "0.05em" }}>
                MOCK PAYMENT LINK — DEMO ONLY — NO REAL PAYMENT PROCESSED
              </div>
            </div>
          )}

          {/* Row 6: WhatsApp Messages */}
          {showWA && selectedWithLink.length > 0 && (
            <div style={{ padding: "14px 18px" }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: T.textSecondary, marginBottom: 10 }}>📱 WhatsApp Messages</div>
              <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
                {selectedWithLink.map(row => (
                  <div key={row.id} style={{ flex: "1 1 300px", maxWidth: 380 }}>
                    <WaBubble row={row} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <Divider />

        {/* ── Customer Collection Detail (60/40) ── */}
        <SectionTitle>👤 Customer Collection Detail</SectionTitle>
        <div style={{ display: "grid", gridTemplateColumns: "3fr 2fr", gap: 16, marginBottom: 0 }}>

          {/* Left: customer fact card */}
          <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "20px 24px" }}>
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 18, fontWeight: 700, color: T.textPrimary, letterSpacing: "-0.01em", marginBottom: 4 }}>
                  {detailCustomer.customer}
                </div>
                <div style={{ fontSize: 12, color: T.textMuted }}>
                  {detailCustomer.town} · Beat T-04
                </div>
              </div>
              <Badge label="Loyal" tone="success" />
            </div>

            {/* Facts 2-col grid */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px 24px", marginBottom: 18 }}>
              {[
                { label: "Invoice", value: detailCustomer.invoice, mono: true },
                { label: "Due Date", value: detailCustomer.dueDate },
                { label: "Outstanding", value: inrExact(detailCustomer.outstanding), tabular: true },
                { label: "Days Overdue", value: detailCustomer.daysOverdue !== null ? `${detailCustomer.daysOverdue}d` : detailCustomer.dueSoon ?? "—" },
                { label: "Credit Days", value: "30" },
                { label: "Risk Tier", badge: detailCustomer.riskTier, tone: detailCustomer.riskTone },
                { label: "Payment", badge: detailCustomer.payStatus, tone: detailCustomer.payTone },
                { label: "Last Action", value: "Escalation call 02-Sep" },
              ].map(({ label, value, mono, tabular, badge, tone }) => (
                <div key={label}>
                  <div style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 3 }}>{label}</div>
                  {badge ? (
                    <Badge label={badge} tone={tone as BadgeTone} />
                  ) : (
                    <div style={{ fontSize: 13, fontWeight: 500, color: T.textPrimary, fontFamily: mono ? "monospace" : undefined, fontVariantNumeric: tabular ? "tabular-nums" : undefined }}>
                      {value}
                    </div>
                  )}
                </div>
              ))}

              {/* Collection probability with mini bar */}
              <div>
                <div style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 3 }}>Collection Probability</div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: detailCustomer.collProb >= 70 ? T.success : detailCustomer.collProb >= 40 ? T.warning : T.danger, fontVariantNumeric: "tabular-nums" }}>
                    {detailCustomer.collProb}%
                  </span>
                  <div style={{ flex: 1, height: 4, background: T.border, borderRadius: 2 }}>
                    <div style={{ height: "100%", width: `${detailCustomer.collProb}%`, background: detailCustomer.collProb >= 70 ? T.success : detailCustomer.collProb >= 40 ? T.warning : T.danger, borderRadius: 2 }} />
                  </div>
                </div>
              </div>

              <div>
                <div style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 3 }}>Expected Recovery</div>
                <div style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary, fontVariantNumeric: "tabular-nums" }}>{inr(detailCustomer.expectedRecovery)}</div>
              </div>
            </div>

            {/* State stepper */}
            <div style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 12 }}>Recovery State</div>
            <StateStepper currentStep={stateStep(detailCustomer.state)} />
          </div>

          {/* Right: stacked recovery action cards */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {/* Recovery Intelligence */}
            <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "16px 18px" }}>
              <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 10 }}>🧠 Recovery Intelligence</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: T.textPrimary, marginBottom: 5 }}>Payment Link + WhatsApp Reminder</div>
              <div style={{ fontSize: 12, color: T.textSecondary, lineHeight: "18px", marginBottom: 12 }}>
                Large outstanding + significant ageing + modeled recoverability at {detailCustomer.collProb}%
              </div>
              <div style={{ display: "flex", gap: 16 }}>
                <div>
                  <div style={{ fontSize: 10, color: T.textMuted, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 2 }}>Probability</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: detailCustomer.collProb >= 50 ? T.success : T.danger, fontVariantNumeric: "tabular-nums" }}>{detailCustomer.collProb}%</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: T.textMuted, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 2 }}>Expected</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary, fontVariantNumeric: "tabular-nums" }}>{inr(detailCustomer.expectedRecovery)}</div>
                </div>
              </div>
            </div>

            {/* Payment Link */}
            <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "16px 18px" }}>
              <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 10 }}>⚡ Payment Link</div>
              <MonoChip value={mockLinks[detailCustomer.id] ?? "rzp.io/i/xxxxxx"} />
              <div style={{ fontSize: 9, color: T.textMuted, marginTop: 8, letterSpacing: "0.05em" }}>
                MOCK PAYMENT LINK — DEMO ONLY — NO REAL PAYMENT PROCESSED
              </div>
            </div>

            {/* WhatsApp Message */}
            <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "16px 18px" }}>
              <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 10 }}>📱 WhatsApp Message</div>
              <WaBubble row={detailCustomer} compact />
              <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                <button style={{ fontSize: 11, color: T.textMuted, background: "none", border: "none", cursor: "pointer", padding: 0 }}>Copy</button>
                <button style={{ fontSize: 11, color: T.textMuted, background: "none", border: "none", cursor: "pointer", padding: 0 }}>↻ Regenerate</button>
              </div>
            </div>
          </div>
        </div>

        <Divider />

        {/* ── Recovery State Flow ── */}
        <SectionTitle>🔄 Recovery State Flow</SectionTitle>
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "24px 28px 20px" }}>
          <StateStepper currentStep={4} />
          {/* STOPPED annotation */}
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 6, gap: 16 }}>
            <span style={{ fontSize: 10, color: T.textMuted }}>
              <Badge label="STOPPED 10" tone="neutral" /> accounts removed from active recovery
            </span>
          </div>
          <div style={{ fontSize: 11, color: T.textMuted, marginTop: 12, borderTop: `1px solid ${T.border}`, paddingTop: 10 }}>
            Transitions enforced by the deterministic recovery policy engine. Each state change is append-only and immutable.
          </div>
        </div>

        <Divider />

        {/* ── Immutable Ledger ── */}
        <SectionTitle>🔐 Immutable Ledger</SectionTitle>
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden" }}>
          <div style={{ padding: "14px 18px", borderBottom: `1px solid ${T.border}` }}>
            <div style={{ fontSize: 12, color: T.textSecondary }}>
              Append-only record of agent decisions, collection actions, payment outcomes and state transitions.
            </div>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Timestamp (IST)", "Customer", "Invoice", "Action", "Previous State", "New State", "Amount", "Outcome"].map(h => (
                  <th key={h} style={{ ...thStyle, padding: "9px 14px" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {auditRows.map((row, i) => (
                <tr
                  key={i}
                  style={{ borderBottom: `1px solid ${T.border}`, background: i % 2 === 0 ? "transparent" : `${T.border}20` }}
                  onMouseEnter={e => (e.currentTarget.style.background = T.cardElevated)}
                  onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 0 ? "transparent" : `${T.border}20`)}
                >
                  <td style={{ padding: "10px 14px", fontSize: 11, fontFamily: "monospace", color: T.textMuted, whiteSpace: "nowrap" }}>{row.ts}</td>
                  <td style={{ padding: "10px 14px", fontSize: 12, fontWeight: 500, color: T.textPrimary, whiteSpace: "nowrap" }}>{row.customer}</td>
                  <td style={{ padding: "10px 14px", fontSize: 11, fontFamily: "monospace", color: T.link }}>{row.invoice}</td>
                  <td style={{ padding: "10px 14px", fontSize: 12, color: T.textSecondary }}>{row.action}</td>
                  <td style={{ padding: "10px 14px" }}>{row.prevState !== "—" ? <Badge label={row.prevState} tone={stateBadgeTone(row.prevState)} /> : <span style={{ color: T.textMuted, fontSize: 11 }}>—</span>}</td>
                  <td style={{ padding: "10px 14px" }}>{row.newState !== "—" ? <Badge label={row.newState} tone={stateBadgeTone(row.newState)} /> : <span style={{ color: T.textMuted, fontSize: 11 }}>—</span>}</td>
                  <td style={{ padding: "10px 14px", fontSize: 12, fontVariantNumeric: "tabular-nums", color: row.amount > 0 ? T.textPrimary : T.textMuted, textAlign: "right" }}>
                    {row.amount > 0 ? inrExact(row.amount) : "—"}
                  </td>
                  <td style={{ padding: "10px 14px" }}><Badge label={row.outcome} tone={outcomeTone[row.outcome]} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// COMMAND CENTER SCREEN
// ══════════════════════════════════════════════════════════════════════════════
function CommandCenter() {
  const [dataExpanded, setDataExpanded] = useState(false);
  return (
    <div style={{ padding: "28px 32px", maxWidth: 1140, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
        <div>
          <h1 style={{ fontSize: 24, lineHeight: "32px", fontWeight: 600, color: T.textPrimary, margin: "0 0 4px", letterSpacing: "-0.015em" }}>
            ⚡ Command Center
          </h1>
          <p style={{ fontSize: 13, color: T.textSecondary, margin: 0, lineHeight: "20px" }}>
            What needs your attention right now.
          </p>
        </div>
        <div style={{ textAlign: "right", fontSize: 12, lineHeight: "20px", color: T.textMuted, flexShrink: 0 }}>
          <div style={{ fontWeight: 500, color: T.textSecondary }}>Business: Tonk, Rajasthan</div>
          <div>ERP: Kuber / Tally / Marg</div>
          <div style={{ marginTop: 3 }}>FY 2024–25</div>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 28, flexWrap: "wrap" }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 500, color: T.success, background: `${T.success}12`, border: `1px solid ${T.success}30`, padding: "4px 12px", borderRadius: 999 }}>
          <span style={{ fontSize: 8 }}>●</span>
          Demo Data Loaded · 380 Customers · 135 SKUs · 24M Sales History
        </span>
        <button onClick={() => setDataExpanded(p => !p)} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 500, color: T.textMuted, background: "transparent", border: `1px solid ${T.border}`, padding: "4px 12px", borderRadius: 8, cursor: "pointer" }}>
          🗄 DATA SOURCE — Load Demo Data or Upload CSV
          <span style={{ fontSize: 10, transform: dataExpanded ? "rotate(180deg)" : "rotate(0deg)", display: "inline-block", transition: "transform 0.15s" }}>▾</span>
        </button>
        {dataExpanded && (
          <div style={{ width: "100%", background: T.card, border: `1px solid ${T.border}`, borderRadius: 10, padding: "14px 18px", display: "flex", gap: 12, alignItems: "center" }}>
            <button style={{ fontSize: 12, fontWeight: 500, padding: "6px 16px", borderRadius: 8, background: T.accent, color: "#fff", border: "none", cursor: "pointer" }}>✓ Demo Data Loaded</button>
            <button style={{ fontSize: 12, fontWeight: 500, padding: "6px 16px", borderRadius: 8, background: "transparent", color: T.textSecondary, border: `1px solid ${T.border}`, cursor: "pointer" }}>Upload CSV / Excel</button>
            <span style={{ fontSize: 12, color: T.textMuted }}>Connect ERP: Kuber · Tally · Marg</span>
          </div>
        )}
      </div>

      <SectionTitle>🏢 Business Snapshot</SectionTitle>
      <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "24px 28px", display: "grid", gridTemplateColumns: "240px 1fr 1fr", gap: 28, marginBottom: 0, position: "relative", overflow: "hidden" }}>
        <div style={{ position: "absolute", top: 0, left: "15%", right: "15%", height: 1, background: `linear-gradient(90deg, transparent, ${T.accent}50, transparent)` }} />
        <div style={{ borderRight: `1px solid ${T.border}`, paddingRight: 24, display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: T.textPrimary, letterSpacing: "-0.02em", marginBottom: 4 }}>Raj Distributors</div>
          <div style={{ fontSize: 13, fontWeight: 500, color: T.textSecondary }}>Rajesh Kumar Sharma</div>
          <div style={{ fontSize: 12, color: T.textMuted }}>FMCG Wholesale Distributor</div>
          <div style={{ fontSize: 12, color: T.textMuted }}>Tonk, Rajasthan</div>
          <div style={{ marginTop: 8 }}><Badge label="FY 2024–25" tone="info" /></div>
        </div>
        <div style={{ borderRight: `1px solid ${T.border}`, paddingRight: 24 }}>
          <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 12 }}>Financial Scale</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <KpiTile label="24M Revenue" value={inr(64800000)} />
            <KpiTile label="Monthly Revenue" value={inr(2700000)} />
            <KpiTile label="Total Receivables" value={inr(4592000)} />
            <KpiTile label="Inventory Value" value={inr(3860000)} />
          </div>
        </div>
        <div>
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 10 }}>Territories Served</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {["Tonk", "Uniara", "Malpura", "Niwai", "Deoli", "Todaraisingh", "Sawai Madhopur", "Khanpur"].map(t => <Chip key={t} label={t} />)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 10 }}>Strongest Categories</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              <Chip label="Packaged Foods 18.4%" color={T.accent} />
              <Chip label="Personal Care 16.5%" color={T.info} />
              <Chip label="Household 14.1%" color={T.success} />
            </div>
          </div>
        </div>
      </div>

      <Divider />
      <SectionTitle>📊 Executive KPIs</SectionTitle>
      <div style={{ display: "flex", gap: 14 }}>
        <ExecKpi label="Total Outstanding" value={inr(64800000)} context="vs ₹58.2Cr last month" tone="danger" />
        <ExecKpi label="Active Parties" value="148" context="+6 this week" tone="success" />
        <ExecKpi label="Overdue > 30d" value={inr(23400000)} context="36.1% of total book" tone="warning" />
        <ExecKpi label="High-Risk Customers" value="247" context="Write-off tier" tone="danger" />
        <ExecKpi label="Stockout Risks" value="6" context="Coverage < 7 days" tone="warning" />
      </div>

      <Divider />
      <SectionTitle>☀️ CEO Morning Briefing</SectionTitle>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <InsightCard icon="💸" topic="Cash Recovery" tone="danger" headline="₹38.7L overdue across 214 invoices" evidence="23 accounts >90 days; ₹8.2L concentrated in Tonk" action="Review collection ledger →" />
        <InsightCard icon="📦" topic="Inventory" tone="warning" headline="6 SKUs below reorder level" evidence="Beverages coverage 13 days vs 22-day seasonal peak" action="Open stockout list →" />
        <InsightCard icon="💰" topic="Working Capital" tone="success" headline="₹0 blocked in dead stock" evidence="All 135 SKUs sold within 30 days — clean inventory" action="View inventory health →" />
        <InsightCard icon="📍" topic="Territory" tone="info" headline="Tonk contributes 34% of sales" evidence="Top 3 towns = 61% of revenue; 5 towns under-penetrated" action="Territory intelligence →" />
      </div>

      <Divider />
      <SectionTitle>🔥 Today's Priority Actions</SectionTitle>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <PriorityRow urgency="HIGH" title="Contact top 10 overdue accounts today" reason="₹12.4L at write-off risk — accounts >90 days with no payment" impact={12400000} action="Open Revenue Recovery →" />
        <PriorityRow urgency="HIGH" title="Buy Beverages before peak season" reason="+28% seasonal uplift expected in 22 days — current stock critically low" impact={310000} action="Open Inventory →" />
        <PriorityRow urgency="MEDIUM" title="Win back 4 churned retailers" reason="₹97.1K monthly revenue lost — last purchase >60 days ago" action="Open Customers →" />
        <PriorityRow urgency="LOW" title="Review low-margin Personal Care SKUs" reason="8 SKUs below 12% margin threshold — pricing review needed" action="Open Inventory →" />
      </div>

      <Divider />
      <SectionTitle>📈 Business Trends</SectionTitle>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "18px 20px 14px" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary, marginBottom: 2 }}>Monthly Revenue</div>
          <div style={{ fontSize: 11, color: T.textMuted, marginBottom: 14 }}>24-month trend · ₹L</div>
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={revenueData} margin={{ top: 4, right: 4, bottom: 0, left: -28 }}>
              <defs>
                <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={T.accent} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={T.accent} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={T.border} vertical={false} />
              <XAxis dataKey="m" tick={{ fontSize: 9, fill: T.textMuted }} tickLine={false} axisLine={false} interval={5} />
              <YAxis tick={{ fontSize: 9, fill: T.textMuted }} tickLine={false} axisLine={false} tickFormatter={v => `${v}L`} />
              <Tooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="rev" stroke={T.accent} strokeWidth={1.5} fill="url(#revGrad)" dot={false} activeDot={{ r: 3, fill: T.accent, strokeWidth: 0 }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "18px 20px 14px" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary, marginBottom: 2 }}>Month-End Receivables</div>
          <div style={{ fontSize: 11, color: T.textMuted, marginBottom: 14 }}>12-month trend · ₹L outstanding</div>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={receivablesData} margin={{ top: 4, right: 4, bottom: 0, left: -28 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={T.border} vertical={false} />
              <XAxis dataKey="m" tick={{ fontSize: 9, fill: T.textMuted }} tickLine={false} axisLine={false} interval={2} />
              <YAxis tick={{ fontSize: 9, fill: T.textMuted }} tickLine={false} axisLine={false} tickFormatter={v => `${v}L`} />
              <Tooltip content={<ChartTooltip />} />
              <Line type="monotone" dataKey="val" stroke={T.danger} strokeWidth={1.5} dot={false} activeDot={{ r: 3, fill: T.danger, strokeWidth: 0 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "18px 20px 14px" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary, marginBottom: 2 }}>Sales by Town</div>
          <div style={{ fontSize: 11, color: T.textMuted, marginBottom: 14 }}>8 territories · ₹K</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={townData} layout="vertical" margin={{ top: 0, right: 4, bottom: 0, left: 2 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={T.border} horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 9, fill: T.textMuted }} tickLine={false} axisLine={false} tickFormatter={v => `${(v / 1000).toFixed(0)}K`} />
              <YAxis type="category" dataKey="town" tick={{ fontSize: 9, fill: T.textMuted }} tickLine={false} axisLine={false} width={62} />
              <Tooltip content={<TownTooltip />} />
              <Bar dataKey="sales" fill={T.accent} radius={[0, 3, 3, 0]} fillOpacity={0.85} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// ROOT APP
// ══════════════════════════════════════════════════════════════════════════════
function PlaceholderScreen({ icon, label }: { icon: string; label: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: 12, color: T.textMuted }}>
      <div style={{ fontSize: 40 }}>{icon}</div>
      <div style={{ fontSize: 16, fontWeight: 600, color: T.textSecondary }}>{label}</div>
      <div style={{ fontSize: 13 }}>Select from the sidebar to navigate</div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// INVENTORY & OPERATIONS SCREEN
// ══════════════════════════════════════════════════════════════════════════════

// ── Band header ───────────────────────────────────────────────────────────────
function BandHeader({ label }: { label: string }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 14, margin: "32px 0 18px",
    }}>
      <span style={{
        fontSize: 10, fontWeight: 800, letterSpacing: "0.16em",
        textTransform: "uppercase", color: T.accent,
        background: `${T.accent}14`, border: `1px solid ${T.accent}30`,
        padding: "3px 10px", borderRadius: 999,
      }}>{label}</span>
      <div style={{ flex: 1, height: 1, background: T.border }} />
    </div>
  );
}

// ── Stockout data ──────────────────────────────────────────────────────────────
const stockoutUrgent = [
  { name: "Parle-G Biscuit 1kg", cat: "Snacks",    coverage: 4,  demand: 18, reorder: 120, recommended: 360 },
  { name: "Amul Butter 500g",    cat: "Dairy",     coverage: 5,  demand: 12, reorder: 80,  recommended: 240 },
  { name: "Maaza 600ml (24pk)",  cat: "Beverages", coverage: 6,  demand: 22, reorder: 160, recommended: 480 },
];
const stockoutTable = [
  { product: "Parle-G Biscuit 1kg",     cat: "Snacks",    stock: 72,  coverage: 4,  demand: 18, reorder: 120, recommended: 360 },
  { product: "Amul Butter 500g",         cat: "Dairy",     stock: 60,  coverage: 5,  demand: 12, reorder: 80,  recommended: 240 },
  { product: "Maaza 600ml (24pk)",       cat: "Beverages", stock: 132, coverage: 6,  demand: 22, reorder: 160, recommended: 480 },
  { product: "Britannia Good Day 400g",  cat: "Snacks",    stock: 48,  coverage: 6,  demand: 8,  reorder: 60,  recommended: 160 },
  { product: "Surf Excel 1kg",           cat: "Household", stock: 35,  coverage: 6,  demand: 6,  reorder: 50,  recommended: 120 },
  { product: "Rin Detergent 500g",       cat: "Household", stock: 56,  coverage: 7,  demand: 8,  reorder: 70,  recommended: 150 },
];

// ── Dead stock bar chart data (all ≤19 days, all active) ─────────────────────
const deadStockData = [
  { name: "Dhara Mustard Oil 1L",    days: 19 },
  { name: "Tata Salt 1kg",           days: 16 },
  { name: "Fortune Soya Oil 1L",     days: 15 },
  { name: "Aashirvaad Atta 5kg",     days: 14 },
  { name: "Surf Excel 2kg",          days: 13 },
  { name: "Ariel Powder 1kg",        days: 12 },
  { name: "Amul Ghee 500ml",         days: 11 },
  { name: "Maggi Noodles 12pk",      days: 10 },
  { name: "Nestle KitKat 12pk",      days: 9  },
  { name: "Colgate 200g",            days: 8  },
  { name: "Dettol Handwash 500ml",   days: 7  },
  { name: "Lifebuoy Soap 4pk",       days: 6  },
  { name: "Head & Shoulders 180ml",  days: 5  },
  { name: "Clinic Plus 100ml",       days: 4  },
  { name: "Vaseline Lotion 200ml",   days: 3  },
];

// ── Seasonal buying data ─────────────────────────────────────────────────────
const seasonalHighlight = [
  { name: "Beverages",  uplift: 28, coverage: 13, peakIn: 22, qty: 480, window: "THIS WEEK"   },
  { name: "Snacks",     uplift: 19, coverage: 16, peakIn: 26, qty: 350, window: "THIS WEEK"   },
  { name: "Dairy",      uplift: 12, coverage: 9,  peakIn: 18, qty: 260, window: "THIS WEEK"   },
];
const seasonalTable = [
  { product: "Maaza 600ml (24pk)",      cat: "Beverages",    uplift: "+28%", coverage: "13d", peak: "26-Sep", qty: 480, window: "This week"    },
  { product: "Slice 600ml (24pk)",      cat: "Beverages",    uplift: "+24%", coverage: "18d", peak: "28-Sep", qty: 320, window: "This week"    },
  { product: "Parle-G Biscuit 1kg",     cat: "Snacks",       uplift: "+19%", coverage: "16d", peak: "30-Sep", qty: 350, window: "This week"    },
  { product: "Kurkure 80g (24pk)",      cat: "Snacks",       uplift: "+17%", coverage: "21d", peak: "02-Oct", qty: 280, window: "Next 2 weeks" },
  { product: "Amul Butter 500g",        cat: "Dairy",        uplift: "+12%", coverage: "9d",  peak: "22-Sep", qty: 260, window: "This week"    },
  { product: "Britannia Good Day 400g", cat: "Snacks",       uplift: "+11%", coverage: "24d", peak: "04-Oct", qty: 200, window: "Next 2 weeks" },
  { product: "Rasna Powder (24pk)",     cat: "Beverages",    uplift: "+9%",  coverage: "28d", peak: "06-Oct", qty: 160, window: "Next 2 weeks" },
  { product: "Cadbury Dairy Milk 40g",  cat: "Packaged Fd.", uplift: "+8%",  coverage: "31d", peak: "08-Oct", qty: 140, window: "Next 2 weeks" },
];

// ── Procurement recommendations ───────────────────────────────────────────────
const procurementRows = [
  { product: "Parle-G Biscuit 1kg",    cat: "Snacks",    qty: 360,  window: "THIS WEEK",    reason: "4-day coverage — below 7-day stockout threshold; reorder 3× to cover Navratri surge." },
  { product: "Maaza 600ml (24pk)",     cat: "Beverages", qty: 480,  window: "THIS WEEK",    reason: "+28% seasonal uplift in 22 days; current stock critically low at 6 days." },
  { product: "Amul Butter 500g",       cat: "Dairy",     qty: 240,  window: "THIS WEEK",    reason: "5-day coverage + 12% festive uplift; cold-chain items lead time 3 days." },
  { product: "Slice 600ml (24pk)",     cat: "Beverages", qty: 320,  window: "THIS WEEK",    reason: "+24% uplift; historically stock-out in Niwai & Deoli during Oct peak." },
  { product: "Kurkure 80g (24pk)",     cat: "Snacks",    qty: 280,  window: "NEXT 2 WEEKS", reason: "+17% festive uplift; current 21-day coverage adequate for 2 more weeks." },
  { product: "Britannia Good Day 400g",cat: "Snacks",    qty: 200,  window: "NEXT 2 WEEKS", reason: "Moderate uplift; 24-day coverage gives buying flexibility." },
  { product: "Surf Excel 1kg",         cat: "Household", qty: 120,  window: "THIS WEEK",    reason: "6-day coverage — marginal stockout risk; price stable, buy now." },
];

// ── Price intelligence ────────────────────────────────────────────────────────
const priceRows = [
  { product: "Parle-G Biscuit 1kg",    avgPrice: 48.20,  recentPrice: 51.00,  trend: "up",   delta: 5.8,  note: "Purchase prices historically rose ~6% before the Oct–Nov peak." },
  { product: "Maaza 600ml (24pk)",     avgPrice: 520.00, recentPrice: 498.00, trend: "down", delta: -4.2, note: "Prices soften in Sep; buy now before festive markup." },
  { product: "Amul Butter 500g",       avgPrice: 243.00, recentPrice: 243.00, trend: "flat", delta: 0,    note: "Stable; dairy prices typically spike post-Diwali." },
  { product: "Surf Excel 1kg",         avgPrice: 118.50, recentPrice: 124.00, trend: "up",   delta: 4.6,  note: "Steady upward trend since Mar; no seasonal inflection expected." },
  { product: "Britannia Good Day 400g",avgPrice: 36.80,  recentPrice: 35.50,  trend: "down", delta: -3.5, note: "Trade discount active — good time to load up before Q3." },
  { product: "Dhara Mustard Oil 1L",   avgPrice: 142.00, recentPrice: 149.00, trend: "up",   delta: 4.9,  note: "Edible oil prices tracking up; consider buying 3–4 weeks forward." },
];

// ── Revenue chart (same data as Command Center) ───────────────────────────────
const revChartData = [
  { m: "Oct'22", rev: 18.4 }, { m: "Nov'22", rev: 21.2 }, { m: "Dec'22", rev: 24.8 },
  { m: "Jan'23", rev: 22.6 }, { m: "Feb'23", rev: 19.9 }, { m: "Mar'23", rev: 28.1 },
  { m: "Apr'23", rev: 23.4 }, { m: "May'23", rev: 25.6 }, { m: "Jun'23", rev: 22.1 },
  { m: "Jul'23", rev: 26.8 }, { m: "Aug'23", rev: 29.3 }, { m: "Sep'23", rev: 27.0 },
  { m: "Oct'23", rev: 24.2 }, { m: "Nov'23", rev: 26.7 }, { m: "Dec'23", rev: 31.4 },
  { m: "Jan'24", rev: 27.5 }, { m: "Feb'24", rev: 23.8 }, { m: "Mar'24", rev: 34.2 },
  { m: "Apr'24", rev: 28.6 }, { m: "May'24", rev: 30.1 }, { m: "Jun'24", rev: 25.9 },
  { m: "Jul'24", rev: 32.4 }, { m: "Aug'24", rev: 35.6 }, { m: "Sep'24", rev: 27.0 },
];

// ── Category mix donut ────────────────────────────────────────────────────────
const categoryMix = [
  { name: "Packaged Foods", value: 18.4, color: "#6D5BF0" },
  { name: "Personal Care",  value: 16.5, color: "#4C9AFF" },
  { name: "Household",      value: 14.1, color: "#34D399" },
  { name: "Beverages",      value: 13.8, color: "#F5B84C" },
  { name: "Home Care",      value: 11.2, color: "#F58A4C" },
  { name: "Dairy",          value: 9.6,  color: "#E7B93C" },
  { name: "FMCG",           value: 8.9,  color: "#8B7CF7" },
  { name: "Agricultural",   value: 7.5,  color: "#F0616D" },
];

// ── Heatmap data (Category × Month) ──────────────────────────────────────────
const heatmapMonths = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"];
const heatmapCategories = ["Packaged Foods", "Personal Care", "Household", "Beverages", "Home Care", "Dairy", "FMCG", "Agricultural"];
const heatmapRaw: number[][] = [
  [4.8, 5.2, 6.1, 4.9, 4.2, 5.8, 4.7, 5.0, 4.4, 5.6, 6.2, 5.1],
  [4.2, 4.6, 4.8, 4.3, 3.9, 4.5, 4.1, 4.4, 3.8, 4.7, 5.1, 4.6],
  [3.6, 3.9, 4.2, 3.7, 3.4, 3.9, 3.5, 3.8, 3.3, 4.0, 4.4, 3.9],
  [4.0, 3.8, 3.2, 2.9, 2.7, 3.1, 3.8, 4.6, 4.9, 5.2, 4.4, 3.8],
  [2.9, 3.1, 3.4, 2.8, 2.6, 3.0, 2.9, 3.1, 2.7, 3.2, 3.5, 3.1],
  [2.4, 2.7, 3.0, 2.5, 2.3, 2.7, 2.4, 2.6, 2.2, 2.8, 3.1, 2.7],
  [2.2, 2.5, 2.8, 2.3, 2.1, 2.5, 2.2, 2.4, 2.1, 2.6, 2.9, 2.5],
  [1.8, 2.0, 2.1, 1.9, 1.7, 2.0, 1.8, 1.9, 1.7, 2.0, 2.2, 2.0],
];

function heatColor(val: number, max: number): string {
  const t = val / max;
  if (t > 0.85) return "#34D399";
  if (t > 0.65) return "#4DB892";
  if (t > 0.45) return "#2E8B6A";
  if (t > 0.28) return "#1A5C48";
  return "#0F3A2E";
}

// ── Shared table header style ─────────────────────────────────────────────────
const TH: React.CSSProperties = {
  fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em",
  color: T.textMuted, padding: "9px 12px", textAlign: "left", whiteSpace: "nowrap",
  background: T.appBg, borderBottom: `1px solid ${T.border}`,
};

const TD: React.CSSProperties = {
  padding: "10px 12px", fontSize: 12, color: T.textSecondary,
  borderBottom: `1px solid ${T.border}`, verticalAlign: "middle",
};

// ── Window badge ──────────────────────────────────────────────────────────────
function WindowBadge({ label }: { label: string }) {
  const isNow = label.toUpperCase().includes("THIS WEEK") || label.toUpperCase().includes("THIS WEEK");
  return (
    <span style={{
      fontSize: 10, fontWeight: 600, letterSpacing: "0.06em",
      textTransform: "uppercase", padding: "3px 8px", borderRadius: 999,
      background: isNow ? `${T.gold}18` : `${T.info}15`,
      color: isNow ? T.gold : T.info,
      whiteSpace: "nowrap",
    }}>{label}</span>
  );
}

// ── Inventory & Operations ────────────────────────────────────────────────────
function InventoryOperations() {
  const [diagExpanded, setDiagExpanded] = useState(false);

  return (
    <div style={{ padding: "28px 32px 48px", maxWidth: 1140, margin: "0 auto" }}>

      {/* Page header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 24, lineHeight: "32px", fontWeight: 600, color: T.textPrimary, margin: "0 0 4px", letterSpacing: "-0.015em" }}>
            📦 Inventory & Operations
          </h1>
          <p style={{ fontSize: 13, color: T.textSecondary, margin: 0, lineHeight: "20px" }}>
            Current stock, future demand, and what to buy next.
          </p>
        </div>
        <div style={{ textAlign: "right", fontSize: 12, lineHeight: "20px", color: T.textMuted, flexShrink: 0 }}>
          <div style={{ fontWeight: 500, color: T.textSecondary }}>Business: Tonk, Rajasthan</div>
          <div>ERP: Kuber / Tally / Marg</div>
          <div style={{ marginTop: 3 }}>FY 2024–25</div>
        </div>
      </div>

      {/* ════════════════════ BAND: NOW ════════════════════ */}
      <BandHeader label="NOW" />

      {/* Inventory Health KPIs */}
      <div style={{ fontSize: 13, fontWeight: 600, color: T.textSecondary, marginBottom: 12 }}>📦 Inventory Health</div>
      <div style={{ display: "flex", gap: 14, marginBottom: 28 }}>
        <ExecKpi label="Active SKUs"         value="135"         context="405 stock rows · 3 godowns"     tone="neutral" />
        <ExecKpi label="Inventory Value"     value={inr(3860000)} context="Across all godowns"             tone="neutral" />
        <ExecKpi label="Dead Stock Value"    value="₹0"          context="No dead stock"                  tone="success" />
        <ExecKpi label="Stockout Risks"      value="6"           context="Coverage < 7 days"              tone="danger"  />
        <ExecKpi label="Average Coverage"    value="21 days"     context="Across 135 SKUs"                tone="neutral" />
      </div>

      {/* ── Stockout Risk ── */}
      <div style={{ fontSize: 13, fontWeight: 600, color: T.textSecondary, marginBottom: 12 }}>⚠️ Stockout Risk</div>

      {/* Urgent cards */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginBottom: 16 }}>
        {stockoutUrgent.map(item => (
          <div key={item.name} style={{
            background: T.card, border: `1px solid ${T.critical}40`,
            borderRadius: 12, padding: "16px 18px",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary, lineHeight: "19px", flex: 1, marginRight: 8 }}>{item.name}</div>
              <Badge label={item.cat} tone="neutral" />
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginBottom: 12 }}>
              <span style={{ fontSize: 34, fontWeight: 700, color: T.critical, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>{item.coverage}</span>
              <span style={{ fontSize: 14, color: T.critical, fontWeight: 500 }}>days left</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 12px" }}>
              {[
                { l: "Demand rate",      v: `${item.demand} units/day` },
                { l: "Reorder level",    v: `${item.reorder} units`    },
                { l: "Recommended buy",  v: `${item.recommended} units` },
              ].map(({ l, v }) => (
                <div key={l}>
                  <div style={{ fontSize: 9, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 2 }}>{l}</div>
                  <div style={{ fontSize: 12, fontWeight: 500, color: T.textPrimary, fontVariantNumeric: "tabular-nums" }}>{v}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Stockout table */}
      <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden", marginBottom: 28 }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["Product", "Category", "Current Stock", "Coverage Days", "Demand Rate", "Reorder Level", "Recommended Reorder"].map(h => (
                <th key={h} style={{ ...TH, textAlign: h === "Product" || h === "Category" ? "left" : "right" as const }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {stockoutTable.map((row, i) => (
              <tr key={row.product}
                style={{ background: i % 2 === 0 ? "transparent" : `${T.border}20` }}
                onMouseEnter={e => (e.currentTarget.style.background = T.cardElevated)}
                onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 0 ? "transparent" : `${T.border}20`)}
              >
                <td style={{ ...TD, color: T.textPrimary, fontWeight: 500 }}>{row.product}</td>
                <td style={TD}><Badge label={row.cat} tone="neutral" /></td>
                <td style={{ ...TD, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{row.stock.toLocaleString()}</td>
                <td style={{ ...TD, textAlign: "right" }}>
                  <span style={{ fontWeight: 700, color: row.coverage <= 5 ? T.critical : row.coverage <= 7 ? T.danger : T.warning, fontVariantNumeric: "tabular-nums" }}>
                    {row.coverage}d
                  </span>
                </td>
                <td style={{ ...TD, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{row.demand} u/d</td>
                <td style={{ ...TD, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{row.reorder.toLocaleString()}</td>
                <td style={{ ...TD, textAlign: "right", fontWeight: 600, color: T.textPrimary, fontVariantNumeric: "tabular-nums" }}>
                  {row.recommended.toLocaleString()} units
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Dead Stock ── */}
      <div style={{ fontSize: 13, fontWeight: 600, color: T.textSecondary, marginBottom: 12 }}>🧊 Dead Stock</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 14, marginBottom: 0 }}>

        {/* Empty state */}
        <div style={{ background: T.card, border: `1px solid ${T.success}30`, borderRadius: 12, padding: "24px 22px", display: "flex", flexDirection: "column", alignItems: "flex-start", justifyContent: "center" }}>
          <div style={{ fontSize: 28, marginBottom: 10 }}>✅</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: T.textPrimary, marginBottom: 6 }}>No dead or slow SKUs</div>
          <div style={{ fontSize: 12, color: T.textSecondary, lineHeight: "18px" }}>
            All 135 SKUs sold within the last 30 days.<br />
            Longest unsold: <span style={{ fontWeight: 600, color: T.textPrimary }}>19 days</span> — Dhara Mustard Oil 1L
          </div>
          <div style={{ marginTop: 14 }}>
            <Badge label="● All ACTIVE" tone="success" />
          </div>
        </div>

        {/* Horizontal bar chart */}
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "18px 20px 14px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 14 }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary, marginBottom: 2 }}>Top 15 Products by Days Unsold</div>
              <div style={{ fontSize: 11, color: T.textMuted }}>Max 19 days — well within 30-day threshold</div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <div style={{ width: 8, height: 8, borderRadius: 2, background: T.success }} />
              <span style={{ fontSize: 10, color: T.textMuted, fontWeight: 500 }}>ACTIVE</span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={deadStockData} layout="vertical" margin={{ top: 0, right: 24, bottom: 0, left: 6 }}>
              <CartesianGrid strokeDasharray="2 2" stroke={T.border} horizontal={false} />
              <XAxis type="number" domain={[0, 30]} tick={{ fontSize: 9, fill: T.textMuted }} tickLine={false} axisLine={false} tickFormatter={v => `${v}d`} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 9, fill: T.textMuted }} tickLine={false} axisLine={false} width={148} />
              <Tooltip
                content={({ active, payload, label }: any) => {
                  if (!active || !payload?.length) return null;
                  return (
                    <div style={{ background: T.cardElevated, border: `1px solid ${T.borderStrong}`, borderRadius: 8, padding: "7px 12px", fontSize: 12, color: T.textPrimary }}>
                      <div style={{ color: T.textMuted, marginBottom: 2 }}>{label}</div>
                      <div style={{ fontWeight: 600 }}>{payload[0].value} days unsold</div>
                    </div>
                  );
                }}
              />
              <Bar dataKey="days" fill={T.success} radius={[0, 3, 3, 0]} fillOpacity={0.75} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ════════════════════ BAND: NEXT ════════════════════ */}
      <BandHeader label="NEXT" />

      {/* Demand Forecasting — unavailable */}
      <div style={{ fontSize: 13, fontWeight: 600, color: T.textSecondary, marginBottom: 12 }}>📈 Demand Forecasting</div>
      <div style={{ background: T.card, border: `1px solid ${T.warning}35`, borderRadius: 12, padding: "18px 22px", marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 14, alignItems: "flex-start", marginBottom: 12 }}>
          <span style={{ fontSize: 18, flexShrink: 0, marginTop: 1 }}>⚠️</span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary, marginBottom: 4 }}>
              Demand forecasting unavailable
            </div>
            <div style={{ fontSize: 12, color: T.textSecondary, lineHeight: "18px" }}>
              Prophet / CmdStan backend not installed in this environment. Statistical time-series forecasting requires a Python runtime with Prophet dependencies.
            </div>
          </div>
        </div>
        <button
          onClick={() => setDiagExpanded(p => !p)}
          style={{ fontSize: 11, color: T.link, background: "none", border: "none", cursor: "pointer", padding: 0, display: "flex", alignItems: "center", gap: 4, marginBottom: diagExpanded ? 10 : 0 }}
        >
          View diagnostic details
          <span style={{ fontSize: 9, transform: diagExpanded ? "rotate(180deg)" : "rotate(0deg)", display: "inline-block", transition: "transform 0.15s" }}>▾</span>
        </button>
        {diagExpanded && (
          <div style={{ background: T.appBg, borderRadius: 8, padding: "10px 14px", fontFamily: "monospace", fontSize: 11, color: T.textMuted, lineHeight: "18px" }}>
            ModuleNotFoundError: No module named 'prophet'<br />
            → Run: pip install prophet<br />
            → Requires: CmdStan ≥ 2.31 + PyStan or CmdStanPy
          </div>
        )}
        <div style={{ fontSize: 12, color: T.textSecondary, borderTop: `1px solid ${T.border}`, marginTop: 14, paddingTop: 12, display: "flex", gap: 8, alignItems: "flex-start" }}>
          <span style={{ color: T.info, fontSize: 13 }}>→</span>
          Seasonality-based buying intelligence below uses 24-month historical patterns instead.
        </div>
      </div>

      {/* Seasonal Buying Intelligence */}
      <div style={{ fontSize: 13, fontWeight: 600, color: T.textSecondary, marginBottom: 12 }}>🌤 Seasonal Buying Intelligence</div>

      {/* Highlight cards */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginBottom: 16 }}>
        {seasonalHighlight.map(item => (
          <div key={item.name} style={{
            background: T.card, border: `1px solid ${T.gold}30`,
            borderRadius: 12, padding: "16px 18px",
            position: "relative" as const, overflow: "hidden",
          }}>
            <div style={{ position: "absolute", top: 0, left: "20%", right: "20%", height: 1, background: `linear-gradient(90deg, transparent, ${T.gold}50, transparent)` }} />
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: T.textPrimary }}>{item.name}</div>
              <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase" as const, background: `${T.gold}22`, color: T.gold, padding: "3px 8px", borderRadius: 999, whiteSpace: "nowrap" as const }}>
                BUY BEFORE PEAK
              </span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 12px" }}>
              {[
                { l: "Expected uplift",   v: `+${item.uplift}%`, col: T.gold },
                { l: "Current coverage",  v: `${item.coverage} days`, col: item.coverage < 14 ? T.danger : T.textPrimary },
                { l: "Peak season in",    v: `${item.peakIn} days`, col: T.textPrimary },
                { l: "Recommended buy",   v: `${item.qty} units`, col: T.accent },
              ].map(({ l, v, col }) => (
                <div key={l}>
                  <div style={{ fontSize: 9, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.08em", color: T.textMuted, marginBottom: 2 }}>{l}</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: col, fontVariantNumeric: "tabular-nums" }}>{v}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Seasonal table */}
      <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden", marginBottom: 0 }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["Product", "Category", "Expected Uplift", "Current Coverage", "Proj. Peak", "Recommended Qty", "Buying Window"].map(h => (
                <th key={h} style={{ ...TH, textAlign: ["Expected Uplift", "Current Coverage", "Recommended Qty"].includes(h) ? "right" as const : "left" as const }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {seasonalTable.map((row, i) => (
              <tr key={row.product}
                style={{ background: i % 2 === 0 ? "transparent" : `${T.border}20` }}
                onMouseEnter={e => (e.currentTarget.style.background = T.cardElevated)}
                onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 0 ? "transparent" : `${T.border}20`)}
              >
                <td style={{ ...TD, color: T.textPrimary, fontWeight: 500 }}>{row.product}</td>
                <td style={TD}><Badge label={row.cat} tone="neutral" /></td>
                <td style={{ ...TD, textAlign: "right", fontWeight: 700, color: T.gold, fontVariantNumeric: "tabular-nums" }}>{row.uplift}</td>
                <td style={{ ...TD, textAlign: "right", fontVariantNumeric: "tabular-nums", color: parseInt(row.coverage) < 14 ? T.danger : T.textSecondary }}>{row.coverage}</td>
                <td style={{ ...TD, fontFamily: "monospace", fontSize: 11, color: T.textMuted }}>{row.peak}</td>
                <td style={{ ...TD, textAlign: "right", fontWeight: 600, color: T.textPrimary, fontVariantNumeric: "tabular-nums" }}>{row.qty.toLocaleString()}</td>
                <td style={{ ...TD }}><WindowBadge label={row.window} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ════════════════════ BAND: BUY ════════════════════ */}
      <BandHeader label="BUY" />

      {/* Procurement Recommendations */}
      <div style={{ fontSize: 13, fontWeight: 600, color: T.textSecondary, marginBottom: 12 }}>🛒 Procurement Recommendations</div>
      <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden", marginBottom: 28 }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["Product", "Category", "Recommended Qty", "Buying Window", "Reason"].map(h => (
                <th key={h} style={{ ...TH, textAlign: h === "Recommended Qty" ? "right" as const : "left" as const }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {procurementRows.map((row, i) => (
              <tr key={row.product}
                style={{ background: i % 2 === 0 ? "transparent" : `${T.border}20` }}
                onMouseEnter={e => (e.currentTarget.style.background = T.cardElevated)}
                onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 0 ? "transparent" : `${T.border}20`)}
              >
                <td style={{ ...TD, color: T.textPrimary, fontWeight: 500, whiteSpace: "nowrap" }}>{row.product}</td>
                <td style={TD}><Badge label={row.cat} tone="neutral" /></td>
                <td style={{ ...TD, textAlign: "right", fontWeight: 600, color: T.textPrimary, fontVariantNumeric: "tabular-nums" }}>{row.qty.toLocaleString()} units</td>
                <td style={TD}><WindowBadge label={row.window} /></td>
                <td style={{ ...TD, fontSize: 11, color: T.textSecondary, lineHeight: "16px", maxWidth: 380 }}>{row.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Price Intelligence */}
      <div style={{ fontSize: 13, fontWeight: 600, color: T.textSecondary, marginBottom: 12 }}>🏷 Price Intelligence</div>
      <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden", marginBottom: 28 }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["Product", "Avg. Purchase Price", "Recent Price", "Trend", "Procurement Opportunity"].map(h => (
                <th key={h} style={{ ...TH, textAlign: ["Avg. Purchase Price", "Recent Price"].includes(h) ? "right" as const : "left" as const }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {priceRows.map((row, i) => {
              const trendColor = row.trend === "up" ? T.danger : row.trend === "down" ? T.success : T.textMuted;
              const trendArrow = row.trend === "up" ? "↑" : row.trend === "down" ? "↓" : "→";
              return (
                <tr key={row.product}
                  style={{ background: i % 2 === 0 ? "transparent" : `${T.border}20` }}
                  onMouseEnter={e => (e.currentTarget.style.background = T.cardElevated)}
                  onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 0 ? "transparent" : `${T.border}20`)}
                >
                  <td style={{ ...TD, color: T.textPrimary, fontWeight: 500, whiteSpace: "nowrap" }}>{row.product}</td>
                  <td style={{ ...TD, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>₹{row.avgPrice.toFixed(2)}</td>
                  <td style={{ ...TD, textAlign: "right", fontWeight: 600, color: T.textPrimary, fontVariantNumeric: "tabular-nums" }}>₹{row.recentPrice.toFixed(2)}</td>
                  <td style={{ ...TD }}>
                    <span style={{ fontWeight: 700, color: trendColor, fontSize: 13, fontVariantNumeric: "tabular-nums" }}>
                      {trendArrow} {row.delta !== 0 ? `${Math.abs(row.delta)}%` : "flat"}
                    </span>
                  </td>
                  <td style={{ ...TD, fontSize: 11, color: T.textSecondary, lineHeight: "16px", maxWidth: 380 }}>{row.note}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Sales & Profitability */}
      <div style={{ fontSize: 13, fontWeight: 600, color: T.textSecondary, marginBottom: 12 }}>💹 Sales & Profitability</div>
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14, marginBottom: 14 }}>

        {/* Revenue line chart */}
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "18px 20px 14px" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary, marginBottom: 2 }}>Monthly Revenue</div>
          <div style={{ fontSize: 11, color: T.textMuted, marginBottom: 14 }}>24-month trend · ₹L</div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={revChartData} margin={{ top: 4, right: 4, bottom: 0, left: -28 }}>
              <defs>
                <linearGradient id="invRevGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={T.accent} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={T.accent} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={T.border} vertical={false} />
              <XAxis dataKey="m" tick={{ fontSize: 9, fill: T.textMuted }} tickLine={false} axisLine={false} interval={5} />
              <YAxis tick={{ fontSize: 9, fill: T.textMuted }} tickLine={false} axisLine={false} tickFormatter={v => `${v}L`} />
              <Tooltip content={({ active, payload, label }: any) => {
                if (!active || !payload?.length) return null;
                return <div style={{ background: T.cardElevated, border: `1px solid ${T.borderStrong}`, borderRadius: 8, padding: "7px 12px", fontSize: 12, color: T.textPrimary }}>
                  <div style={{ color: T.textMuted, marginBottom: 2 }}>{label}</div>
                  <div style={{ fontWeight: 600 }}>₹{payload[0].value.toFixed(1)}L</div>
                </div>;
              }} />
              <Area type="monotone" dataKey="rev" stroke={T.accent} strokeWidth={1.5} fill="url(#invRevGrad)" dot={false} activeDot={{ r: 3, fill: T.accent, strokeWidth: 0 }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Gross margin + donut */}
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "18px 20px 14px" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary, marginBottom: 2 }}>Gross Margin & Category Mix</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginBottom: 14 }}>
            <span style={{ fontSize: 28, fontWeight: 700, color: T.success, fontVariantNumeric: "tabular-nums" }}>14.2%</span>
            <span style={{ fontSize: 11, color: T.textMuted }}>avg gross margin</span>
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            <ResponsiveContainer width={110} height={110}>
              <PieChart>
                <Pie data={categoryMix} cx={50} cy={50} innerRadius={28} outerRadius={50} dataKey="value" paddingAngle={2}>
                  {categoryMix.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4, justifyContent: "center" }}>
              {categoryMix.map(cat => (
                <div key={cat.name} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <div style={{ width: 8, height: 8, borderRadius: 2, background: cat.color, flexShrink: 0 }} />
                  <span style={{ fontSize: 10, color: T.textSecondary, flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{cat.name}</span>
                  <span style={{ fontSize: 10, color: T.textMuted, fontVariantNumeric: "tabular-nums", flexShrink: 0 }}>{cat.value}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Heatmap: Category × Month */}
      <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "18px 20px 20px" }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary, marginBottom: 2 }}>Category × Month Revenue Heatmap</div>
        <div style={{ fontSize: 11, color: T.textMuted, marginBottom: 16 }}>Monthly revenue (₹L) by category · FY 2023–24 → 2024–25 · Green intensity = higher revenue</div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ borderCollapse: "separate", borderSpacing: 3, minWidth: 700 }}>
            <thead>
              <tr>
                <th style={{ fontSize: 10, fontWeight: 600, color: T.textMuted, textAlign: "left", padding: "0 10px 8px 0", whiteSpace: "nowrap", letterSpacing: "0.06em", textTransform: "uppercase" }}>Category</th>
                {heatmapMonths.map(m => (
                  <th key={m} style={{ fontSize: 10, fontWeight: 600, color: T.textMuted, textAlign: "center", padding: "0 0 8px", width: 52, letterSpacing: "0.06em", textTransform: "uppercase" }}>{m}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {heatmapCategories.map((cat, ci) => {
                const row = heatmapRaw[ci];
                const rowMax = Math.max(...row);
                return (
                  <tr key={cat}>
                    <td style={{ fontSize: 11, color: T.textSecondary, padding: "0 12px 3px 0", whiteSpace: "nowrap", fontWeight: 500 }}>{cat}</td>
                    {row.map((val, mi) => {
                      const bg = heatColor(val, 6.5);
                      const isHigh = val === rowMax;
                      return (
                        <td key={mi} title={`${cat} · ${heatmapMonths[mi]}: ₹${val.toFixed(1)}L`}
                          style={{
                            background: bg, borderRadius: 4, padding: "6px 0",
                            textAlign: "center", fontSize: 10, fontWeight: isHigh ? 700 : 400,
                            color: val > 3.5 ? "#E8F8F2" : "#5A8A76",
                            cursor: "default", fontVariantNumeric: "tabular-nums",
                            transition: "opacity 0.1s",
                          }}
                          onMouseEnter={e => (e.currentTarget.style.opacity = "0.8")}
                          onMouseLeave={e => (e.currentTarget.style.opacity = "1")}
                        >
                          {val.toFixed(1)}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {/* Legend */}
        <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 12 }}>
          <span style={{ fontSize: 10, color: T.textMuted, marginRight: 4 }}>Low</span>
          {["#0F3A2E", "#1A5C48", "#2E8B6A", "#4DB892", "#34D399"].map(c => (
            <div key={c} style={{ width: 18, height: 10, background: c, borderRadius: 2 }} />
          ))}
          <span style={{ fontSize: 10, color: T.textMuted, marginLeft: 4 }}>High</span>
        </div>
      </div>

    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// CUSTOMER INTELLIGENCE SCREEN
// ══════════════════════════════════════════════════════════════════════════════

// ── Segment colours ───────────────────────────────────────────────────────────
const SEG = {
  Champions: { color: T.gold,     bg: `${T.gold}18`,     border: `${T.gold}35`     },
  Loyal:     { color: T.success,  bg: `${T.success}18`,  border: `${T.success}35`  },
  "At Risk": { color: T.segAtRisk,bg: `${T.segAtRisk}18`,border: `${T.segAtRisk}35`},
  Lost:      { color: T.danger,   bg: `${T.danger}18`,   border: `${T.danger}35`   },
};

// ── Customer Portfolio KPI data ───────────────────────────────────────────────
const portfolioKpis = [
  { label: "Total Customers",  value: "380",  context: "12 new in last 90 days", tone: "neutral"  as BadgeTone },
  { label: "Active",           value: "320",  context: "Ordered in 90 days",     tone: "success"  as BadgeTone },
  { label: "Champions",        value: "87",   context: "23% of base",            tone: "neutral"  as BadgeTone, accent: T.gold    },
  { label: "Loyal",            value: "202",  context: "53% of base",            tone: "success"  as BadgeTone, accent: T.success  },
  { label: "At Risk",          value: "31",   context: "8% of base",             tone: "orange"   as BadgeTone, accent: T.segAtRisk},
  { label: "Lost",             value: "60",   context: "16% of base",            tone: "danger"   as BadgeTone, accent: T.danger   },
];

// ── Segment cards data ────────────────────────────────────────────────────────
const segmentCards = [
  { name: "Champions", count: 87,  pct: 23, revenue: "₹48.2K/mo", daysSince: "12d",  orders: "6.1 orders/mo" },
  { name: "Loyal",     count: 202, pct: 53, revenue: "₹21.4K/mo", daysSince: "21d",  orders: "3.4 orders/mo" },
  { name: "At Risk",   count: 31,  pct: 8,  revenue: "₹18.9K/mo", daysSince: "58d",  orders: "2.1 orders/mo" },
  { name: "Lost",      count: 60,  pct: 16, revenue: "₹9.8K/mo",  daysSince: "141d", orders: "0.3 orders/mo" },
];

const segmentDonut = [
  { name: "Champions", value: 87,  color: T.gold      },
  { name: "Loyal",     value: 202, color: T.success    },
  { name: "At Risk",   value: 31,  color: T.segAtRisk  },
  { name: "Lost",      value: 60,  color: T.danger     },
];

// ── Geographic data ───────────────────────────────────────────────────────────
const townGeo = [
  { town: "Tonk",          customers: 142, sales: 22.07, outstanding: 15.4, overdue: 11.2, z: 22 },
  { town: "Uniara",        customers: 68,  sales: 11.24, outstanding: 8.1,  overdue: 5.8,  z: 11 },
  { town: "Malpura",       customers: 52,  sales: 7.43,  outstanding: 5.6,  overdue: 3.2,  z: 7  },
  { town: "Niwai",         customers: 44,  sales: 6.12,  outstanding: 4.8,  overdue: 2.9,  z: 6  },
  { town: "Deoli",         customers: 33,  sales: 4.98,  outstanding: 3.9,  overdue: 2.1,  z: 5  },
  { town: "Todaraisingh",  customers: 18,  sales: 4.21,  outstanding: 3.1,  overdue: 2.6,  z: 4  },
  { town: "Sawai Madhopur",customers: 14,  sales: 3.76,  outstanding: 2.8,  overdue: 1.9,  z: 4  },
  { town: "Khanpur",       customers: 9,   sales: 3.18,  outstanding: 2.2,  overdue: 1.7,  z: 3  },
];

// ── Territory bar chart data ───────────────────────────────────────────────────
const territoryBarData = townGeo.map(t => ({
  name: t.town.replace("Sawai Madhopur", "Sawai M.").replace("Todaraisingh", "Todara."),
  sales: t.sales,
  overdue: t.overdue,
  dueSoon: t.outstanding - t.overdue,
}));

// ── Beat intelligence data ────────────────────────────────────────────────────
const beatRows = [
  { beat: "T-01", town: "Tonk",    customers: 24, sales: 4.12, outstanding: 3.1,  rep: "Mukesh S.",  day: "Mon" },
  { beat: "T-02", town: "Tonk",    customers: 19, sales: 3.84, outstanding: 2.7,  rep: "Mukesh S.",  day: "Tue" },
  { beat: "T-03", town: "Tonk",    customers: 22, sales: 4.01, outstanding: 2.9,  rep: "Ramji K.",   day: "Wed" },
  { beat: "T-04", town: "Tonk",    customers: 31, sales: 5.22, outstanding: 3.8,  rep: "Ramji K.",   day: "Thu" },
  { beat: "T-05", town: "Tonk",    customers: 18, sales: 2.94, outstanding: 2.1,  rep: "Suresh P.",  day: "Fri" },
  { beat: "T-06", town: "Tonk",    customers: 14, sales: 1.94, outstanding: 0.8,  rep: "Suresh P.",  day: "Sat" },
  { beat: "U-01", town: "Uniara",  customers: 38, sales: 6.18, outstanding: 4.4,  rep: "Anand M.",   day: "Mon" },
  { beat: "U-02", town: "Uniara",  customers: 30, sales: 5.06, outstanding: 3.7,  rep: "Anand M.",   day: "Wed" },
  { beat: "M-01", town: "Malpura", customers: 52, sales: 7.43, outstanding: 5.6,  rep: "Vinod J.",   day: "Tue" },
  { beat: "N-01", town: "Niwai",   customers: 44, sales: 6.12, outstanding: 4.8,  rep: "Pradeep R.", day: "Thu" },
  { beat: "D-01", town: "Deoli",   customers: 33, sales: 4.98, outstanding: 3.9,  rep: "Hemant B.",  day: "Fri" },
  { beat: "TO-1", town: "Todaraisingh", customers: 18, sales: 4.21, outstanding: 3.1, rep: "Rakesh V.", day: "Wed" },
  { beat: "SM-1", town: "Sawai M.", customers: 14, sales: 3.76, outstanding: 2.8,  rep: "Gopal D.",   day: "Mon" },
  { beat: "K-01", town: "Khanpur", customers: 9,  sales: 3.18, outstanding: 2.2,  rep: "Gopal D.",   day: "Sat" },
];

// ── RFM histograms ────────────────────────────────────────────────────────────
const recencyBuckets = [
  { label: "0–7d",   count: 84 }, { label: "8–14d",  count: 72 },
  { label: "15–30d", count: 68 }, { label: "31–60d", count: 44 },
  { label: "61–90d", count: 32 }, { label: "90d+",   count: 80 },
];
const frequencyBuckets = [
  { label: "1–2/mo",  count: 112 }, { label: "3–4/mo",  count: 98 },
  { label: "5–6/mo",  count: 74  }, { label: "7–8/mo",  count: 54 },
  { label: "9–10/mo", count: 28  }, { label: "10+/mo",  count: 14 },
];
const monetaryBuckets = [
  { label: "<₹5K",   count: 48 }, { label: "₹5–10K",  count: 84 },
  { label: "₹10–20K",count: 96 }, { label: "₹20–40K", count: 72 },
  { label: "₹40–80K",count: 48 }, { label: "₹80K+",   count: 32 },
];

// ── Growing / declining tables ────────────────────────────────────────────────
const topGrowing = [
  { customer: "Sharma Medical Store", town: "Tonk",   delta: 38400  },
  { customer: "Yadav Kirana Depot",   town: "Uniara", delta: 29100  },
  { customer: "Modi General Store",   town: "Malpura",delta: 24800  },
  { customer: "Patel Provision",      town: "Niwai",  delta: 21600  },
  { customer: "Agarwal Brothers",     town: "Tonk",   delta: 18900  },
];
const topDeclining = [
  { customer: "Bairwa Supermart",      town: "Tonk",    delta: -23600 },
  { customer: "Lodha Enterprises",     town: "Tonk",    delta: -25600 },
  { customer: "Bansal Cold Store",     town: "Deoli",   delta: -20900 },
  { customer: "Khandelwal Traders",    town: "Khanpur", delta: -26900 },
  { customer: "Rathore Provisions",    town: "Niwai",   delta: -14200 },
];

// ── Churned customers ─────────────────────────────────────────────────────────
const churnedRows = [
  { customer: "Bairwa Supermart",   town: "Tonk",    lastOrder: "26-Jun-26", daysSince: 71, monthlyRev: 23600, recent: 0 },
  { customer: "Lodha Enterprises",  town: "Tonk",    lastOrder: "30-Jun-26", daysSince: 67, monthlyRev: 25600, recent: 0 },
  { customer: "Bansal Cold Store",  town: "Deoli",   lastOrder: "07-Jul-26", daysSince: 59, monthlyRev: 20900, recent: 0 },
  { customer: "Khandelwal Traders", town: "Khanpur", lastOrder: "19-Jul-26", daysSince: 47, monthlyRev: 26900, recent: 0 },
];

// ── Custom chart tooltip ──────────────────────────────────────────────────────
function CusTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: T.cardElevated, border: `1px solid ${T.borderStrong}`, borderRadius: 8, padding: "7px 12px", fontSize: 12, color: T.textPrimary }}>
      <div style={{ color: T.textMuted, marginBottom: 2 }}>{label}</div>
      <div style={{ fontWeight: 600 }}>{payload[0].value}</div>
    </div>
  );
}
function RevTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: T.cardElevated, border: `1px solid ${T.borderStrong}`, borderRadius: 8, padding: "7px 12px", fontSize: 12, color: T.textPrimary }}>
      <div style={{ color: T.textMuted, marginBottom: 2 }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.name} style={{ color: p.color, fontWeight: 600 }}>
          {p.name}: ₹{p.value.toFixed(1)}L
        </div>
      ))}
    </div>
  );
}
function ScatterTip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  return (
    <div style={{ background: T.cardElevated, border: `1px solid ${T.borderStrong}`, borderRadius: 8, padding: "8px 12px", fontSize: 12, color: T.textPrimary }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{d.town}</div>
      <div style={{ color: T.textMuted }}>Customers: {d.customers}</div>
      <div style={{ color: T.textMuted }}>Sales: ₹{d.sales.toFixed(2)}L</div>
      <div style={{ color: T.textMuted }}>Outstanding: ₹{d.outstanding.toFixed(1)}L</div>
    </div>
  );
}

function CustomerIntelligence() {
  const [beatTown, setBeatTown] = useState("All");
  const [showOptCols, setShowOptCols] = useState(false);
  const beatTowns = ["All", "Tonk", "Uniara", "Malpura", "Niwai", "Deoli", "Todaraisingh", "Sawai M.", "Khanpur"];
  const filteredBeats = beatTown === "All" ? beatRows : beatRows.filter(r => r.town.startsWith(beatTown.replace("Sawai M.", "Sawai")));

  const beatTotals = {
    customers: filteredBeats.reduce((s, r) => s + r.customers, 0),
    sales: filteredBeats.reduce((s, r) => s + r.sales, 0),
    outstanding: filteredBeats.reduce((s, r) => s + r.outstanding, 0),
  };

  const TH2: React.CSSProperties = {
    fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em",
    color: T.textMuted, padding: "9px 12px", textAlign: "left", whiteSpace: "nowrap",
    background: T.appBg, borderBottom: `1px solid ${T.border}`,
  };
  const TD2: React.CSSProperties = {
    padding: "10px 12px", fontSize: 12, color: T.textSecondary,
    borderBottom: `1px solid ${T.border}`, verticalAlign: "middle",
  };

  return (
    <div style={{ padding: "28px 32px 56px", maxWidth: 1140, margin: "0 auto" }}>

      {/* Page header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, lineHeight: "32px", fontWeight: 600, color: T.textPrimary, margin: "0 0 4px", letterSpacing: "-0.015em" }}>
            👥 Customer Intelligence
          </h1>
          <p style={{ fontSize: 13, color: T.textSecondary, margin: 0 }}>
            Understand customer segments, geography, and retention.
          </p>
        </div>
        <div style={{ textAlign: "right", fontSize: 12, lineHeight: "20px", color: T.textMuted, flexShrink: 0 }}>
          <div style={{ fontWeight: 500, color: T.textSecondary }}>Business: Tonk, Rajasthan</div>
          <div>ERP: Kuber / Tally / Marg</div>
          <div style={{ marginTop: 3 }}>FY 2024–25</div>
        </div>
      </div>

      {/* ── Customer Portfolio ── */}
      <div style={{ fontSize: 13, fontWeight: 600, color: T.textSecondary, marginBottom: 12 }}>👥 Customer Portfolio</div>
      <div style={{ display: "flex", gap: 14, marginBottom: 28 }}>
        {portfolioKpis.map(k => (
          <div key={k.label} style={{
            background: T.card, border: `1px solid ${k.accent ? `${k.accent}35` : T.border}`,
            borderRadius: 12, padding: "18px 20px", flex: 1,
          }}>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>
              {k.label}
            </div>
            <div style={{ fontSize: 26, lineHeight: "32px", fontWeight: 700, color: k.accent ?? T.textPrimary, fontVariantNumeric: "tabular-nums", marginBottom: 5 }}>
              {k.value}
            </div>
            <div style={{ fontSize: 12, color: badgeToneMap[k.tone]?.color ?? T.textSecondary }}>
              {k.context}
            </div>
          </div>
        ))}
      </div>

      {/* ── Customer Segmentation ── */}
      <div style={{ fontSize: 13, fontWeight: 600, color: T.textSecondary, marginBottom: 12 }}>🎯 Customer Segmentation</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr auto", gap: 14, alignItems: "stretch", marginBottom: 28 }}>
        {segmentCards.map(seg => {
          const s = SEG[seg.name as keyof typeof SEG];
          return (
            <div key={seg.name} style={{ background: T.card, border: `1px solid ${s.border}`, borderRadius: 12, padding: "18px 18px 14px" }}>
              <div style={{ marginBottom: 10 }}>
                <span style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.08em", background: s.bg, color: s.color, padding: "3px 9px", borderRadius: 999 }}>
                  {seg.name}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginBottom: 4 }}>
                <span style={{ fontSize: 28, fontWeight: 700, color: s.color, fontVariantNumeric: "tabular-nums", lineHeight: 1 }}>{seg.count}</span>
                <span style={{ fontSize: 13, color: T.textMuted }}>customers</span>
              </div>
              <div style={{ fontSize: 12, color: T.textMuted, marginBottom: 12 }}>{seg.pct}% of base</div>
              <div style={{ display: "flex", flexDirection: "column" as const, gap: 6, borderTop: `1px solid ${T.border}`, paddingTop: 10 }}>
                {[
                  { l: "Avg monthly rev",    v: seg.revenue   },
                  { l: "Days since order",   v: seg.daysSince },
                  { l: "Orders / month",     v: seg.orders    },
                ].map(({ l, v }) => (
                  <div key={l} style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                    <span style={{ fontSize: 11, color: T.textMuted }}>{l}</span>
                    <span style={{ fontSize: 12, fontWeight: 600, color: T.textPrimary, fontVariantNumeric: "tabular-nums" }}>{v}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}

        {/* Donut + caption */}
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "18px 20px", display: "flex", flexDirection: "column" as const, alignItems: "center", justifyContent: "center", minWidth: 200 }}>
          <ResponsiveContainer width={150} height={150}>
            <PieChart>
              <Pie data={segmentDonut} cx={70} cy={70} innerRadius={36} outerRadius={64} dataKey="value" paddingAngle={2}>
                {segmentDonut.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
              <Tooltip content={({ active, payload }: any) => {
                if (!active || !payload?.length) return null;
                return (
                  <div style={{ background: T.cardElevated, border: `1px solid ${T.borderStrong}`, borderRadius: 8, padding: "6px 10px", fontSize: 11, color: T.textPrimary }}>
                    <div style={{ fontWeight: 600 }}>{payload[0].name}: {payload[0].value}</div>
                  </div>
                );
              }} />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ display: "flex", flexDirection: "column" as const, gap: 4, marginTop: 4 }}>
            {segmentDonut.map(s => (
              <div key={s.name} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <div style={{ width: 8, height: 8, borderRadius: 2, background: s.color, flexShrink: 0 }} />
                <span style={{ fontSize: 10, color: T.textSecondary }}>{s.name}</span>
                <span style={{ fontSize: 10, color: T.textMuted, marginLeft: "auto", paddingLeft: 8 }}>{s.value}</span>
              </div>
            ))}
          </div>
          <div style={{ fontSize: 9, color: T.textMuted, marginTop: 10, textAlign: "center" as const, lineHeight: "14px", maxWidth: 160 }}>
            RFM features + K-Means, recomputed on each load
          </div>
        </div>
      </div>

      {/* ── Geographic Intelligence ── */}
      <div style={{ fontSize: 13, fontWeight: 600, color: T.textSecondary, marginBottom: 12 }}>🗺 Geographic Intelligence</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 28 }}>

        {/* Bubble chart */}
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "18px 20px 14px" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary, marginBottom: 2 }}>Customer Distribution by Town</div>
          <div style={{ fontSize: 11, color: T.textMuted, marginBottom: 14 }}>
            x = customers · y = sales (₹L) · bubble = sales · shade = outstanding
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={T.border} />
              <XAxis
                type="number" dataKey="customers" name="Customers"
                tick={{ fontSize: 9, fill: T.textMuted }} tickLine={false} axisLine={false}
                label={{ value: "Customers", position: "insideBottom", offset: -10, fontSize: 10, fill: T.textMuted }}
              />
              <YAxis
                type="number" dataKey="sales" name="Sales"
                tick={{ fontSize: 9, fill: T.textMuted }} tickLine={false} axisLine={false}
                tickFormatter={v => `${v}L`}
                label={{ value: "Sales (₹L)", angle: -90, position: "insideLeft", offset: 14, fontSize: 10, fill: T.textMuted }}
              />
              <ZAxis type="number" dataKey="z" range={[300, 2000]} />
              <Tooltip content={<ScatterTip />} />
              <Scatter data={townGeo} fill={T.accent} fillOpacity={0.65} />
            </ScatterChart>
          </ResponsiveContainer>
          <div style={{ fontSize: 10, color: T.textMuted, marginTop: 6, borderTop: `1px solid ${T.border}`, paddingTop: 8 }}>
            No GPS data — town-level aggregation only
          </div>
        </div>

        {/* Town table */}
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden" }}>
          <div style={{ padding: "14px 16px", borderBottom: `1px solid ${T.border}` }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary }}>Town-Level Summary</div>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Town", "Customers", "Sales", "Outstanding", "Overdue", ""].map((h, i) => (
                  <th key={i} style={{
                    fontSize: 10, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.08em",
                    color: T.textMuted, padding: "9px 12px",
                    textAlign: (i >= 1 && i <= 4) ? "right" as const : "left" as const,
                    background: T.appBg, borderBottom: `1px solid ${T.border}`,
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {townGeo.map((row, i) => (
                <tr key={row.town}
                  style={{ background: i % 2 === 0 ? "transparent" : `${T.border}20` }}
                  onMouseEnter={e => (e.currentTarget.style.background = T.cardElevated)}
                  onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 0 ? "transparent" : `${T.border}20`)}
                >
                  <td style={{ padding: "10px 12px", fontSize: 13, fontWeight: 500, color: T.textPrimary, borderBottom: `1px solid ${T.border}` }}>{row.town}</td>
                  <td style={{ padding: "10px 12px", fontSize: 12, color: T.textSecondary, textAlign: "right", fontVariantNumeric: "tabular-nums", borderBottom: `1px solid ${T.border}` }}>{row.customers}</td>
                  <td style={{ padding: "10px 12px", fontSize: 12, fontWeight: 600, color: T.textPrimary, textAlign: "right", fontVariantNumeric: "tabular-nums", borderBottom: `1px solid ${T.border}` }}>₹{row.sales.toFixed(2)}L</td>
                  <td style={{ padding: "10px 12px", fontSize: 12, fontWeight: 600, color: T.textPrimary, textAlign: "right", fontVariantNumeric: "tabular-nums", borderBottom: `1px solid ${T.border}` }}>₹{row.outstanding.toFixed(1)}L</td>
                  <td style={{ padding: "10px 12px", fontSize: 12, color: T.danger, fontWeight: 600, textAlign: "right", fontVariantNumeric: "tabular-nums", borderBottom: `1px solid ${T.border}` }}>₹{row.overdue.toFixed(1)}L</td>
                  <td style={{ padding: "10px 12px", borderBottom: `1px solid ${T.border}` }}>
                    <a href="#" style={{ fontSize: 11, color: T.link, textDecoration: "none", fontWeight: 500 }}>Focus →</a>
                  </td>
                </tr>
              ))}
              {/* Total row */}
              <tr style={{ background: T.cardElevated }}>
                <td style={{ padding: "10px 12px", fontSize: 12, fontWeight: 700, color: T.textPrimary }}>TOTAL</td>
                <td style={{ padding: "10px 12px", fontSize: 12, fontWeight: 700, color: T.textPrimary, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>380</td>
                <td style={{ padding: "10px 12px", fontSize: 12, fontWeight: 700, color: T.textPrimary, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>₹45.92L</td>
                <td style={{ padding: "10px 12px", fontSize: 12, fontWeight: 700, color: T.textPrimary, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>₹45.92L</td>
                <td style={{ padding: "10px 12px", fontSize: 12, fontWeight: 700, color: T.danger, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>₹31.4L</td>
                <td />
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Territory Performance ── */}
      <div style={{ fontSize: 13, fontWeight: 600, color: T.textSecondary, marginBottom: 12 }}>📍 Territory Performance</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 14 }}>
        {/* Sales by town */}
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "18px 20px 14px" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary, marginBottom: 2 }}>Sales by Town</div>
          <div style={{ fontSize: 11, color: T.textMuted, marginBottom: 12 }}>₹L · sorted descending</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={territoryBarData} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 4 }}>
              <CartesianGrid strokeDasharray="2 2" stroke={T.border} horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 9, fill: T.textMuted }} tickLine={false} axisLine={false} tickFormatter={v => `${v}L`} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 9, fill: T.textMuted }} tickLine={false} axisLine={false} width={60} />
              <Tooltip content={({ active, payload, label }: any) => {
                if (!active || !payload?.length) return null;
                return <div style={{ background: T.cardElevated, border: `1px solid ${T.borderStrong}`, borderRadius: 8, padding: "7px 12px", fontSize: 12, color: T.textPrimary }}>
                  <div style={{ color: T.textMuted, marginBottom: 2 }}>{label}</div>
                  <div style={{ fontWeight: 600 }}>₹{payload[0].value.toFixed(2)}L</div>
                </div>;
              }} />
              <Bar dataKey="sales" fill={T.accent} radius={[0, 3, 3, 0]} fillOpacity={0.8} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Outstanding stacked */}
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "18px 20px 14px" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary, marginBottom: 2 }}>Outstanding by Town</div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 12 }}>
            <span style={{ fontSize: 11, color: T.textMuted }}>₹L</span>
            <div style={{ display: "flex", gap: 10 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10 }}>
                <div style={{ width: 10, height: 10, borderRadius: 2, background: T.danger }} />
                <span style={{ color: T.textMuted }}>Overdue</span>
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10 }}>
                <div style={{ width: 10, height: 10, borderRadius: 2, background: T.warning }} />
                <span style={{ color: T.textMuted }}>Due soon</span>
              </span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={territoryBarData} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 4 }}>
              <CartesianGrid strokeDasharray="2 2" stroke={T.border} horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 9, fill: T.textMuted }} tickLine={false} axisLine={false} tickFormatter={v => `${v}L`} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 9, fill: T.textMuted }} tickLine={false} axisLine={false} width={60} />
              <Tooltip content={<RevTip />} />
              <Bar dataKey="overdue" name="Overdue" stackId="a" fill={T.danger} fillOpacity={0.8} />
              <Bar dataKey="dueSoon" name="Due soon" stackId="a" fill={T.warning} fillOpacity={0.65} radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Territory table */}
      <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden", marginBottom: 28 }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["Town", "Customers", "Sales", "Outstanding", "Overdue", "Overdue %"].map(h => (
                <th key={h} style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.08em", color: T.textMuted, padding: "9px 14px", textAlign: h === "Town" ? "left" as const : "right" as const, background: T.appBg, borderBottom: `1px solid ${T.border}` }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {townGeo.map((row, i) => (
              <tr key={row.town}
                style={{ background: i % 2 === 0 ? "transparent" : `${T.border}20` }}
                onMouseEnter={e => (e.currentTarget.style.background = T.cardElevated)}
                onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 0 ? "transparent" : `${T.border}20`)}
              >
                <td style={{ padding: "10px 14px", fontSize: 13, fontWeight: 500, color: T.textPrimary, borderBottom: `1px solid ${T.border}` }}>{row.town}</td>
                <td style={{ padding: "10px 14px", fontSize: 12, color: T.textSecondary, textAlign: "right", fontVariantNumeric: "tabular-nums", borderBottom: `1px solid ${T.border}` }}>{row.customers}</td>
                <td style={{ padding: "10px 14px", fontSize: 12, fontWeight: 600, color: T.textPrimary, textAlign: "right", fontVariantNumeric: "tabular-nums", borderBottom: `1px solid ${T.border}` }}>₹{row.sales.toFixed(2)}L</td>
                <td style={{ padding: "10px 14px", fontSize: 12, fontWeight: 600, color: T.textPrimary, textAlign: "right", fontVariantNumeric: "tabular-nums", borderBottom: `1px solid ${T.border}` }}>₹{row.outstanding.toFixed(1)}L</td>
                <td style={{ padding: "10px 14px", fontSize: 12, color: T.danger, fontWeight: 600, textAlign: "right", fontVariantNumeric: "tabular-nums", borderBottom: `1px solid ${T.border}` }}>₹{row.overdue.toFixed(1)}L</td>
                <td style={{ padding: "10px 14px", fontSize: 12, textAlign: "right", fontVariantNumeric: "tabular-nums", borderBottom: `1px solid ${T.border}`, color: row.overdue / row.outstanding > 0.7 ? T.danger : T.textSecondary }}>
                  {((row.overdue / row.outstanding) * 100).toFixed(0)}%
                </td>
              </tr>
            ))}
            <tr style={{ background: T.cardElevated }}>
              <td style={{ padding: "10px 14px", fontSize: 12, fontWeight: 700, color: T.textPrimary }}>TOTAL</td>
              <td style={{ padding: "10px 14px", fontSize: 12, fontWeight: 700, color: T.textPrimary, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>380</td>
              <td style={{ padding: "10px 14px", fontSize: 12, fontWeight: 700, color: T.textPrimary, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>₹45.92L</td>
              <td style={{ padding: "10px 14px", fontSize: 12, fontWeight: 700, color: T.textPrimary, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>₹45.92L</td>
              <td style={{ padding: "10px 14px", fontSize: 12, fontWeight: 700, color: T.danger, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>₹31.4L</td>
              <td style={{ padding: "10px 14px", fontSize: 12, fontWeight: 700, color: T.danger, textAlign: "right" }}>68%</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* ── Beat Intelligence ── */}
      <div style={{ fontSize: 13, fontWeight: 600, color: T.textSecondary, marginBottom: 12 }}>🛵 Beat Intelligence</div>
      <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden", marginBottom: 28 }}>
        {/* Filter row */}
        <div style={{ padding: "12px 16px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {beatTowns.map(t => (
              <button key={t} onClick={() => setBeatTown(t)} style={{
                fontSize: 11, fontWeight: 500, padding: "3px 10px", borderRadius: 999,
                border: `1px solid ${beatTown === t ? T.accent : T.border}`,
                background: beatTown === t ? `${T.accent}18` : "transparent",
                color: beatTown === t ? T.link : T.textSecondary, cursor: "pointer",
              }}>{t}</button>
            ))}
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: T.textSecondary, cursor: "pointer" }}>
            <input type="checkbox" checked={showOptCols} onChange={e => setShowOptCols(e.target.checked)} style={{ accentColor: T.accent }} />
            Show Sales Rep &amp; Route Day
          </label>
        </div>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["Beat", "Town", "Customers", "Sales", "Outstanding", ...(showOptCols ? ["Sales Rep", "Route Day"] : [])].map(h => (
                <th key={h} style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.08em", color: T.textMuted, padding: "9px 12px", textAlign: ["Customers", "Sales", "Outstanding"].includes(h) ? "right" as const : "left" as const, background: T.appBg, borderBottom: `1px solid ${T.border}`, whiteSpace: "nowrap" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredBeats.map((row, i) => (
              <tr key={row.beat}
                style={{ background: i % 2 === 0 ? "transparent" : `${T.border}20` }}
                onMouseEnter={e => (e.currentTarget.style.background = T.cardElevated)}
                onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 0 ? "transparent" : `${T.border}20`)}
              >
                <td style={{ padding: "9px 12px", fontSize: 12, fontFamily: "monospace", color: T.link, borderBottom: `1px solid ${T.border}` }}>{row.beat}</td>
                <td style={{ padding: "9px 12px", fontSize: 12, color: T.textSecondary, borderBottom: `1px solid ${T.border}` }}>{row.town}</td>
                <td style={{ padding: "9px 12px", fontSize: 12, color: T.textSecondary, textAlign: "right", fontVariantNumeric: "tabular-nums", borderBottom: `1px solid ${T.border}` }}>{row.customers}</td>
                <td style={{ padding: "9px 12px", fontSize: 12, fontWeight: 600, color: T.textPrimary, textAlign: "right", fontVariantNumeric: "tabular-nums", borderBottom: `1px solid ${T.border}` }}>₹{row.sales.toFixed(2)}L</td>
                <td style={{ padding: "9px 12px", fontSize: 12, fontWeight: 500, color: T.textPrimary, textAlign: "right", fontVariantNumeric: "tabular-nums", borderBottom: `1px solid ${T.border}` }}>₹{row.outstanding.toFixed(1)}L</td>
                {showOptCols && <>
                  <td style={{ padding: "9px 12px", fontSize: 12, color: T.textSecondary, borderBottom: `1px solid ${T.border}` }}>{row.rep}</td>
                  <td style={{ padding: "9px 12px", borderBottom: `1px solid ${T.border}` }}>
                    <span style={{ fontSize: 10, fontWeight: 600, background: T.cardElevated, color: T.textSecondary, padding: "2px 7px", borderRadius: 999, border: `1px solid ${T.border}` }}>{row.day}</span>
                  </td>
                </>}
              </tr>
            ))}
            {/* Totals row */}
            <tr style={{ background: T.cardElevated }}>
              <td colSpan={2} style={{ padding: "9px 12px", fontSize: 11, fontWeight: 700, color: T.textPrimary }}>TOTAL · {filteredBeats.length} beats</td>
              <td style={{ padding: "9px 12px", fontSize: 12, fontWeight: 700, color: T.textPrimary, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{beatTotals.customers}</td>
              <td style={{ padding: "9px 12px", fontSize: 12, fontWeight: 700, color: T.textPrimary, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>₹{beatTotals.sales.toFixed(2)}L</td>
              <td style={{ padding: "9px 12px", fontSize: 12, fontWeight: 700, color: T.textPrimary, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>₹{beatTotals.outstanding.toFixed(1)}L</td>
              {showOptCols && <><td /><td /></>}
            </tr>
          </tbody>
        </table>
      </div>

      {/* ── Customer Behaviour ── */}
      <div style={{ fontSize: 13, fontWeight: 600, color: T.textSecondary, marginBottom: 12 }}>📊 Customer Behaviour</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginBottom: 14 }}>
        {[
          { title: "Recency",  subtitle: "Days since last order", data: recencyBuckets, color: T.accent  },
          { title: "Frequency",subtitle: "Orders per month",      data: frequencyBuckets, color: T.info   },
          { title: "Monetary", subtitle: "Avg monthly revenue",   data: monetaryBuckets, color: T.success },
        ].map(({ title, subtitle, data, color }) => (
          <div key={title} style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "16px 18px 14px" }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: T.textPrimary, marginBottom: 2 }}>{title}</div>
            <div style={{ fontSize: 11, color: T.textMuted, marginBottom: 12 }}>{subtitle}</div>
            <ResponsiveContainer width="100%" height={130}>
              <BarChart data={data} margin={{ top: 0, right: 0, bottom: 0, left: -28 }}>
                <CartesianGrid strokeDasharray="2 2" stroke={T.border} vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 8, fill: T.textMuted }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 8, fill: T.textMuted }} tickLine={false} axisLine={false} />
                <Tooltip content={<CusTip />} />
                <Bar dataKey="count" fill={color} radius={[3, 3, 0, 0]} fillOpacity={0.8} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ))}
      </div>

      {/* Growing / declining chips + mini tables */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: T.success, background: `${T.success}14`, border: `1px solid ${T.success}30`, padding: "3px 12px", borderRadius: 999 }}>
          ↑ 186 growing
        </span>
        <span style={{ fontSize: 12, fontWeight: 600, color: T.danger, background: `${T.danger}14`, border: `1px solid ${T.danger}30`, padding: "3px 12px", borderRadius: 999 }}>
          ↓ 94 declining
        </span>
        <span style={{ fontSize: 11, color: T.textMuted }}>vs previous period</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 28 }}>
        {[
          { title: "Top 5 Growing", rows: topGrowing, positive: true },
          { title: "Top 5 Declining", rows: topDeclining, positive: false },
        ].map(({ title, rows, positive }) => (
          <div key={title} style={{ background: T.card, border: `1px solid ${positive ? T.success : T.danger}30`, borderRadius: 12, overflow: "hidden" }}>
            <div style={{ padding: "11px 14px", borderBottom: `1px solid ${T.border}`, fontSize: 12, fontWeight: 600, color: positive ? T.success : T.danger }}>
              {positive ? "↑" : "↓"} {title}
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Customer", "Town", "Δ Revenue"].map(h => (
                    <th key={h} style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.07em", color: T.textMuted, padding: "8px 12px", textAlign: h === "Δ Revenue" ? "right" as const : "left" as const, background: T.appBg, borderBottom: `1px solid ${T.border}` }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={row.customer}
                    style={{ borderBottom: i < rows.length - 1 ? `1px solid ${T.border}` : "none" }}
                    onMouseEnter={e => (e.currentTarget.style.background = T.cardElevated)}
                    onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                  >
                    <td style={{ padding: "9px 12px", fontSize: 12, fontWeight: 500, color: T.textPrimary }}>{row.customer}</td>
                    <td style={{ padding: "9px 12px", fontSize: 11, color: T.textMuted }}>{row.town}</td>
                    <td style={{ padding: "9px 12px", fontSize: 12, fontWeight: 700, color: positive ? T.success : T.danger, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                      {positive ? "+" : ""}{inr(Math.abs(row.delta))}/mo
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>

      {/* ── Churned Customers ── */}
      <div style={{ fontSize: 13, fontWeight: 600, color: T.textSecondary, marginBottom: 12 }}>🧲 Churned Customers</div>
      <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden", marginBottom: 8 }}>
        {/* Summary chips */}
        <div style={{ padding: "12px 16px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: T.danger, background: `${T.danger}14`, border: `1px solid ${T.danger}30`, padding: "3px 10px", borderRadius: 999 }}>
            Churned: 4
          </span>
          <span style={{ fontSize: 11, fontWeight: 600, color: T.textMuted, background: T.cardElevated, border: `1px solid ${T.border}`, padding: "3px 10px", borderRadius: 999 }}>
            At-Risk (behavioural): 0
          </span>
          <span style={{ fontSize: 11, fontWeight: 600, color: T.warning, background: `${T.warning}12`, border: `1px solid ${T.warning}30`, padding: "3px 10px", borderRadius: 999 }}>
            Est. Monthly Loss: ₹97.1K
          </span>
        </div>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["Customer", "Town", "Last Order", "Days Since", "Monthly Rev", "Recent Orders", "Status"].map(h => (
                <th key={h} style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.07em", color: T.textMuted, padding: "9px 12px", textAlign: ["Days Since", "Monthly Rev", "Recent Orders"].includes(h) ? "right" as const : "left" as const, background: T.appBg, borderBottom: `1px solid ${T.border}`, whiteSpace: "nowrap" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {churnedRows.map((row, i) => (
              <tr key={row.customer}
                style={{ borderBottom: i < churnedRows.length - 1 ? `1px solid ${T.border}` : "none" }}
                onMouseEnter={e => (e.currentTarget.style.background = T.cardElevated)}
                onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
              >
                <td style={{ padding: "11px 12px", fontSize: 13, fontWeight: 500, color: T.textPrimary }}>{row.customer}</td>
                <td style={{ padding: "11px 12px", fontSize: 12, color: T.textSecondary }}>{row.town}</td>
                <td style={{ padding: "11px 12px", fontSize: 11, fontFamily: "monospace", color: T.textMuted }}>{row.lastOrder}</td>
                <td style={{ padding: "11px 12px", fontSize: 12, fontWeight: 600, color: T.danger, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{row.daysSince}d</td>
                <td style={{ padding: "11px 12px", fontSize: 12, fontWeight: 600, color: T.textPrimary, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{inr(row.monthlyRev)}/mo</td>
                <td style={{ padding: "11px 12px", fontSize: 12, color: T.textMuted, textAlign: "right" }}>{row.recent}</td>
                <td style={{ padding: "11px 12px" }}>
                  <span style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.07em", background: `${T.danger}18`, color: T.danger, padding: "3px 8px", borderRadius: 999 }}>CHURNED</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ fontSize: 11, color: T.textMuted, lineHeight: "16px" }}>
        Churn alerts = previously regular buyers with zero recent orders; the Lost RFM segment uses a broader definition — the two numbers intentionally differ.
      </div>

    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// AI BUSINESS ANALYST SCREEN
// ══════════════════════════════════════════════════════════════════════════════

const SUGGESTED_QUESTIONS = [
  "Give me today's business briefing.",
  "Which customers currently owe me the most?",
  "Show me overdue customers in Uniara.",
  "Who should I contact first for collections?",
  "Why is Patel Stores high risk?",
  "Which customers are Champions?",
  "Which products are approaching stockout?",
  "What should I buy before the next seasonal peak?",
  "Which territory is underperforming?",
  "What is my current inventory value?",
  "Show me the immutable ledger.",
];

const COLLECTION_TABLE = [
  { customer: "Patel Stores",          outstanding: 272414, days: 149, risk: "WRITE-OFF", expected: 81700  },
  { customer: "Kumawat General Store", outstanding: 240000, days: 687, risk: "WRITE-OFF", expected: 24000  },
  { customer: "Jain Brothers",         outstanding: 195000, days: 138, risk: "WRITE-OFF", expected: 48750  },
  { customer: "Yadav Traders",         outstanding: 93500,  days: 669, risk: "WRITE-OFF", expected: 9350   },
  { customer: "Sharma Kirana",         outstanding: 41200,  days: 12,  risk: "MEDIUM",    expected: 28000  },
];

function AiBusinessAnalyst() {
  const [input, setInput] = useState("");
  const [traceExpanded, setTraceExpanded] = useState(false);
  const [rawExpanded, setRawExpanded] = useState(false);
  const [agentExpanded, setAgentExpanded] = useState(false);
  const [geminiKey, setGeminiKey] = useState("");
  const [groqKey, setGroqKey] = useState("");
  const [hovSugg, setHovSugg] = useState<string | null>(null);

  // Custom API keys
  interface CustomKey { id: string; name: string; value: string; show: boolean }
  const [customKeys, setCustomKeys] = useState<CustomKey[]>([]);
  const [addingKey, setAddingKey] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [newKeyValue, setNewKeyValue] = useState("");
  const [showGemini, setShowGemini] = useState(false);
  const [showGroq, setShowGroq] = useState(false);

  function commitCustomKey() {
    if (!newKeyName.trim()) return;
    setCustomKeys(prev => [...prev, { id: crypto.randomUUID(), name: newKeyName.trim(), value: newKeyValue, show: false }]);
    setNewKeyName(""); setNewKeyValue(""); setAddingKey(false);
  }
  function removeCustomKey(id: string) {
    setCustomKeys(prev => prev.filter(k => k.id !== id));
  }
  function toggleCustomKeyVisibility(id: string) {
    setCustomKeys(prev => prev.map(k => k.id === id ? { ...k, show: !k.show } : k));
  }

  const anyKeySet = geminiKey || groqKey || customKeys.some(k => k.value);
  const activeModel = geminiKey ? "Gemini" : groqKey ? "Groq (llama3)" : customKeys.find(k => k.value)?.name ?? null;

  function riskTone(r: string): { bg: string; color: string } {
    if (r === "WRITE-OFF") return { bg: `${T.critical}18`, color: T.critical };
    if (r === "HIGH")      return { bg: `${T.danger}18`,   color: T.danger   };
    if (r === "MEDIUM")    return { bg: `${T.warning}18`,  color: T.warning  };
    return                        { bg: `${T.success}18`,  color: T.success  };
  }

  const traceSteps = [
    { label: "User Intent",  value: "Collection prioritization",                    icon: "👤" },
    { label: "Tool",         value: "get_outstanding_payments",                     icon: "🔧", mono: true },
    { label: "Observation",  value: "312 open receivables · ₹45.92L total",        icon: "🔍" },
    { label: "Action",       value: "Ranked by expected recovery; top 10 returned", icon: "✅" },
  ];

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>

      {/* ── Main chat column ── */}
      <div style={{ flex: 3, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <div style={{ flex: 1, overflowY: "auto", padding: "28px 28px 0 32px" }}>

          {/* Page header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
            <div>
              <h1 style={{ fontSize: 24, lineHeight: "32px", fontWeight: 600, color: T.textPrimary, margin: "0 0 4px", letterSpacing: "-0.015em" }}>
                🤖 AI Business Analyst
              </h1>
              <p style={{ fontSize: 13, color: T.textSecondary, margin: 0 }}>
                Ask questions about cash, customers, inventory and operations.
              </p>
            </div>
            <div style={{ textAlign: "right", fontSize: 12, lineHeight: "20px", color: T.textMuted, flexShrink: 0 }}>
              <div style={{ fontWeight: 500, color: T.textSecondary }}>Business: Tonk, Rajasthan</div>
              <div>ERP: Kuber / Tally / Marg</div>
              <div style={{ marginTop: 3 }}>FY 2024–25</div>
            </div>
          </div>

          {/* Suggested questions */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.08em", color: T.textMuted, marginBottom: 10 }}>
              💡 Suggested Questions
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
              {SUGGESTED_QUESTIONS.map(q => (
                <button
                  key={q}
                  onClick={() => setInput(q)}
                  onMouseEnter={() => setHovSugg(q)}
                  onMouseLeave={() => setHovSugg(null)}
                  style={{
                    fontSize: 12, fontWeight: 500, padding: "5px 13px", borderRadius: 999,
                    border: `1px solid ${hovSugg === q ? T.accent : T.border}`,
                    background: hovSugg === q ? `${T.accent}12` : T.card,
                    color: hovSugg === q ? T.link : T.textSecondary,
                    cursor: "pointer", transition: "all 0.1s", whiteSpace: "nowrap" as const,
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>

          {/* ── Completed exchange ── */}
          {/* User bubble */}
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 14 }}>
            <div style={{
              background: `${T.accent}22`, border: `1px solid ${T.accent}40`,
              borderRadius: "12px 12px 3px 12px", padding: "10px 16px",
              maxWidth: "70%", fontSize: 13, fontWeight: 500, color: T.textPrimary,
            }}>
              Who should I contact first for collections?
            </div>
          </div>

          {/* Assistant answer */}
          <div style={{ marginBottom: 14 }}>
            {/* Header */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
              <div style={{ width: 28, height: 28, borderRadius: 8, background: T.accent, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, flexShrink: 0 }}>🤖</div>
              <span style={{ fontSize: 12, fontWeight: 600, color: T.textSecondary }}>AI Business Analyst</span>
              <span style={{ fontSize: 10, color: T.textMuted }}>· 09:14 AM</span>
            </div>

            <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: "3px 12px 12px 12px", padding: "18px 20px" }}>
              {/* Prose */}
              <p style={{ fontSize: 13, color: T.textSecondary, lineHeight: "20px", margin: "0 0 16px" }}>
                Based on your current ledger, I've ranked overdue accounts by <strong style={{ color: T.textPrimary }}>expected recovery value</strong> — prioritising accounts where there is realistic probability of collection. Here are the top contacts for today:
              </p>

              {/* KPI chips row */}
              <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap" }}>
                {[
                  { label: "Collectible from top 10", value: "₹12.4L", color: T.accent },
                  { label: "High-risk customers",      value: "247",    color: T.danger  },
                  { label: "Expected recovery",        value: "₹14.2L", color: T.success },
                ].map(chip => (
                  <div key={chip.label} style={{
                    background: `${chip.color}12`, border: `1px solid ${chip.color}30`,
                    borderRadius: 8, padding: "8px 14px",
                    display: "flex", flexDirection: "column" as const, gap: 3,
                  }}>
                    <span style={{ fontSize: 10, color: T.textMuted, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.07em" }}>{chip.label}</span>
                    <span style={{ fontSize: 18, fontWeight: 700, color: chip.color, fontVariantNumeric: "tabular-nums" }}>{chip.value}</span>
                  </div>
                ))}
              </div>

              {/* Mini table */}
              <div style={{ border: `1px solid ${T.border}`, borderRadius: 8, overflow: "hidden", marginBottom: 12 }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      {["Customer", "Outstanding", "Days Overdue", "Risk", "Expected Recovery", ""].map(h => (
                        <th key={h} style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.07em", color: T.textMuted, padding: "8px 10px", textAlign: ["Outstanding", "Days Overdue", "Expected Recovery"].includes(h) ? "right" as const : "left" as const, background: T.appBg, borderBottom: `1px solid ${T.border}`, whiteSpace: "nowrap" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {COLLECTION_TABLE.map((row, i) => {
                      const rt = riskTone(row.risk);
                      return (
                        <tr key={row.customer}
                          style={{ borderBottom: i < COLLECTION_TABLE.length - 1 ? `1px solid ${T.border}` : "none" }}
                          onMouseEnter={e => (e.currentTarget.style.background = T.cardElevated)}
                          onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                        >
                          <td style={{ padding: "9px 10px", fontSize: 12, fontWeight: 500, color: T.textPrimary, whiteSpace: "nowrap" }}>{row.customer}</td>
                          <td style={{ padding: "9px 10px", fontSize: 12, fontWeight: 600, color: T.textPrimary, textAlign: "right", fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>
                            {row.outstanding >= 100000 ? `₹${(row.outstanding / 100000).toFixed(1)}L` : `₹${(row.outstanding / 1000).toFixed(0)}K`}
                          </td>
                          <td style={{ padding: "9px 10px", fontSize: 12, color: row.days > 90 ? T.critical : T.danger, fontWeight: 600, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{row.days}d</td>
                          <td style={{ padding: "9px 10px" }}>
                            <span style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.06em", background: rt.bg, color: rt.color, padding: "2px 7px", borderRadius: 999 }}>{row.risk}</span>
                          </td>
                          <td style={{ padding: "9px 10px", fontSize: 12, color: T.success, fontWeight: 600, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{inr(row.expected)}</td>
                          <td style={{ padding: "9px 10px", whiteSpace: "nowrap" }}>
                            <a href="#" style={{ fontSize: 11, color: T.link, textDecoration: "none", fontWeight: 500 }}>Open in Recovery →</a>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <p style={{ fontSize: 12, color: T.textMuted, margin: 0, lineHeight: "18px" }}>
                Call or WhatsApp these accounts in order — highest expected recovery first minimises working capital impact.
              </p>
            </div>

            {/* TRACE CARD */}
            <div style={{ marginTop: 10 }}>
              <button
                onClick={() => setTraceExpanded(p => !p)}
                style={{
                  display: "flex", alignItems: "center", gap: 6, fontSize: 11,
                  fontWeight: 600, color: T.textMuted, background: "none", border: "none",
                  cursor: "pointer", padding: 0, letterSpacing: "0.04em",
                  textTransform: "uppercase" as const,
                }}
              >
                <span style={{ fontSize: 10 }}>🔍</span>
                TRACE
                <span style={{ fontSize: 9, transform: traceExpanded ? "rotate(180deg)" : "rotate(0deg)", display: "inline-block", transition: "transform 0.15s" }}>▾</span>
              </button>

              {traceExpanded && (
                <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 10, padding: "16px 18px", marginTop: 8 }}>
                  <div style={{ display: "flex", flexDirection: "column" as const, gap: 0 }}>
                    {traceSteps.map((step, i) => (
                      <div key={step.label} style={{ display: "flex", gap: 12 }}>
                        {/* Spine */}
                        <div style={{ display: "flex", flexDirection: "column" as const, alignItems: "center", width: 24, flexShrink: 0 }}>
                          <div style={{ width: 24, height: 24, borderRadius: "50%", background: i === traceSteps.length - 1 ? T.accent : T.cardElevated, border: `1px solid ${i === traceSteps.length - 1 ? T.accent : T.border}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11 }}>
                            {step.icon}
                          </div>
                          {i < traceSteps.length - 1 && (
                            <div style={{ width: 1, flex: 1, background: T.border, margin: "3px 0" }} />
                          )}
                        </div>
                        {/* Content */}
                        <div style={{ paddingBottom: i < traceSteps.length - 1 ? 14 : 0 }}>
                          <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.08em", color: T.textMuted, marginBottom: 3 }}>{step.label}</div>
                          <div style={{ fontSize: 12, color: T.textSecondary, fontFamily: step.mono ? "monospace" : undefined }}>
                            {step.mono ? (
                              <span style={{ background: T.appBg, border: `1px solid ${T.border}`, padding: "2px 8px", borderRadius: 5, color: T.link }}>{step.value}</span>
                            ) : step.value}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Raw trace expander */}
                  <div style={{ borderTop: `1px solid ${T.border}`, marginTop: 12, paddingTop: 10 }}>
                    <button
                      onClick={() => setRawExpanded(p => !p)}
                      style={{ fontSize: 11, color: T.textMuted, background: "none", border: "none", cursor: "pointer", padding: 0, display: "flex", alignItems: "center", gap: 4 }}
                    >
                      Raw trace
                      <span style={{ fontSize: 9, transform: rawExpanded ? "rotate(180deg)" : "rotate(0deg)", display: "inline-block", transition: "transform 0.15s" }}>▾</span>
                    </button>
                    {rawExpanded && (
                      <pre style={{ margin: "8px 0 0", fontSize: 10, fontFamily: "monospace", color: T.textMuted, background: T.appBg, border: `1px solid ${T.border}`, borderRadius: 6, padding: "10px 12px", overflowX: "auto", lineHeight: "16px" }}>
{`{
  "intent": "collection_prioritization",
  "tools_called": ["get_outstanding_payments"],
  "tool_args": {"sort_by": "expected_recovery", "limit": 10},
  "result_count": 312,
  "total_outstanding": 4592000,
  "latency_ms": 42,
  "model": "rule-based-fallback",
  "session_query_id": "sq_003"
}`}
                      </pre>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Typing state bubble */}
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 14 }}>
            <div style={{
              background: `${T.accent}22`, border: `1px solid ${T.accent}40`,
              borderRadius: "12px 12px 3px 12px", padding: "10px 16px",
              maxWidth: "70%", fontSize: 13, fontWeight: 500, color: T.textPrimary,
              display: "flex", alignItems: "center", gap: 8,
            }}>
              <span>Which products are approaching stockout?</span>
              <span style={{ fontSize: 10, color: T.link }}>✎</span>
            </div>
          </div>

          {/* Typing indicator from AI */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 20 }}>
            <div style={{ width: 28, height: 28, borderRadius: 8, background: T.accent, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>🤖</div>
            <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: "3px 12px 12px 12px", padding: "12px 16px", display: "flex", gap: 5, alignItems: "center" }}>
              {[0, 1, 2].map(i => (
                <div key={i} style={{
                  width: 6, height: 6, borderRadius: "50%", background: T.accent,
                  animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
                  opacity: 0.6,
                }} />
              ))}
            </div>
            <span style={{ fontSize: 11, color: T.textMuted }}>Querying inventory…</span>
          </div>

          <div style={{ height: 16 }} />
        </div>

        {/* ── Chat input bar ── */}
        <div style={{ borderTop: `1px solid ${T.border}`, padding: "14px 32px 20px", background: T.sidebarBg, flexShrink: 0 }}>
          <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
            <div style={{ flex: 1, position: "relative" as const }}>
              <textarea
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); setInput(""); } }}
                placeholder="Ask anything… e.g. 'Which customers won't pay me this month?'"
                rows={1}
                style={{
                  width: "100%", fontSize: 13, padding: "11px 14px", borderRadius: 10,
                  border: `1px solid ${T.borderStrong}`, background: T.card,
                  color: T.textPrimary, outline: "none", resize: "none",
                  fontFamily: "inherit", lineHeight: "20px",
                  boxSizing: "border-box" as const,
                }}
              />
            </div>
            <button
              style={{
                padding: "10px 18px", borderRadius: 10, border: "none",
                background: T.accent, color: "#fff", fontSize: 13,
                fontWeight: 600, cursor: "pointer", flexShrink: 0,
                display: "flex", alignItems: "center", gap: 6,
              }}
            >
              Send ↵
            </button>
          </div>
          <div style={{ fontSize: 10, color: T.textMuted, marginTop: 6, lineHeight: "14px" }}>
            Shift+Enter for newline · Answers draw from your live ERP data · No queries leave your session without consent
          </div>
        </div>
      </div>

      {/* ── Right rail ── */}
      <div style={{
        width: "25%", flexShrink: 0,
        borderLeft: `1px solid ${T.border}`,
        background: T.sidebarBg,
        overflowY: "auto",
        padding: "28px 18px",
      }}>

        {/* Agent Config */}
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden", marginBottom: 14 }}>
          <button
            onClick={() => setAgentExpanded(p => !p)}
            style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              width: "100%", padding: "13px 16px", background: "none", border: "none",
              cursor: "pointer", borderBottom: agentExpanded ? `1px solid ${T.border}` : "none",
            }}
          >
            <span style={{ fontSize: 12, fontWeight: 600, color: T.textPrimary }}>⚙️ Agent Config</span>
            <span style={{ fontSize: 10, color: T.textMuted, transform: agentExpanded ? "rotate(180deg)" : "rotate(0deg)", display: "inline-block", transition: "transform 0.15s" }}>▾</span>
          </button>

          {agentExpanded && (
            <div style={{ padding: "14px 16px" }}>

              {/* Status badge */}
              <div style={{
                background: anyKeySet ? `${T.success}12` : `${T.warning}12`,
                border: `1px solid ${anyKeySet ? T.success : T.warning}30`,
                borderRadius: 8, padding: "8px 12px", marginBottom: 14,
              }}>
                <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.07em", color: anyKeySet ? T.success : T.warning, marginBottom: 2 }}>
                  {anyKeySet ? `LLM: ${activeModel}` : "LLM: Rule-based fallback"}
                </div>
                <div style={{ fontSize: 11, color: T.textSecondary, lineHeight: "15px" }}>
                  {anyKeySet ? "Full LLM reasoning active." : "Add a key below for full LLM reasoning."}
                </div>
              </div>

              {/* Preset keys section label */}
              <div style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.1em", color: T.textMuted, marginBottom: 8 }}>
                Preset Providers
              </div>

              {/* Gemini key */}
              <div style={{ marginBottom: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                  <label style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.07em", color: T.textMuted }}>
                    Gemini API Key
                  </label>
                  {geminiKey && (
                    <button onClick={() => setGeminiKey("")} style={{ fontSize: 10, color: T.danger, background: "none", border: "none", cursor: "pointer", padding: 0 }}>Remove</button>
                  )}
                </div>
                <div style={{ display: "flex", gap: 5 }}>
                  <input
                    type={showGemini ? "text" : "password"}
                    value={geminiKey}
                    onChange={e => setGeminiKey(e.target.value)}
                    placeholder="AIza••••••••••••••••"
                    style={{ flex: 1, fontSize: 12, padding: "6px 9px", borderRadius: 7, border: `1px solid ${geminiKey ? T.success : T.border}`, background: T.appBg, color: T.textPrimary, outline: "none", fontFamily: "monospace", boxSizing: "border-box" as const }}
                  />
                  <button onClick={() => setShowGemini(p => !p)} style={{ fontSize: 11, color: T.textMuted, background: T.appBg, border: `1px solid ${T.border}`, borderRadius: 6, padding: "0 8px", cursor: "pointer" }}>
                    {showGemini ? "Hide" : "Show"}
                  </button>
                </div>
              </div>

              {/* Groq key */}
              <div style={{ marginBottom: 14 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                  <label style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.07em", color: T.textMuted }}>
                    Groq API Key
                  </label>
                  {groqKey && (
                    <button onClick={() => setGroqKey("")} style={{ fontSize: 10, color: T.danger, background: "none", border: "none", cursor: "pointer", padding: 0 }}>Remove</button>
                  )}
                </div>
                <div style={{ display: "flex", gap: 5 }}>
                  <input
                    type={showGroq ? "text" : "password"}
                    value={groqKey}
                    onChange={e => setGroqKey(e.target.value)}
                    placeholder="gsk_••••••••••••••••"
                    style={{ flex: 1, fontSize: 12, padding: "6px 9px", borderRadius: 7, border: `1px solid ${groqKey ? T.success : T.border}`, background: T.appBg, color: T.textPrimary, outline: "none", fontFamily: "monospace", boxSizing: "border-box" as const }}
                  />
                  <button onClick={() => setShowGroq(p => !p)} style={{ fontSize: 11, color: T.textMuted, background: T.appBg, border: `1px solid ${T.border}`, borderRadius: 6, padding: "0 8px", cursor: "pointer" }}>
                    {showGroq ? "Hide" : "Show"}
                  </button>
                </div>
              </div>

              {/* Custom keys section */}
              <div style={{ borderTop: `1px solid ${T.border}`, paddingTop: 12, marginBottom: 10 }}>
                <div style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.1em", color: T.textMuted, marginBottom: 8 }}>
                  Custom Keys
                </div>

                {/* Existing custom keys */}
                {customKeys.map(ck => (
                  <div key={ck.id} style={{ marginBottom: 8 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                      <span style={{ fontSize: 10, fontWeight: 600, color: T.textSecondary, textTransform: "uppercase" as const, letterSpacing: "0.07em" }}>
                        {ck.name}
                      </span>
                      <div style={{ display: "flex", gap: 8 }}>
                        <button onClick={() => toggleCustomKeyVisibility(ck.id)} style={{ fontSize: 10, color: T.textMuted, background: "none", border: "none", cursor: "pointer", padding: 0 }}>
                          {ck.show ? "Hide" : "Show"}
                        </button>
                        <button onClick={() => removeCustomKey(ck.id)} style={{ fontSize: 10, color: T.danger, background: "none", border: "none", cursor: "pointer", padding: 0 }}>
                          Remove
                        </button>
                      </div>
                    </div>
                    <input
                      type={ck.show ? "text" : "password"}
                      value={ck.value}
                      onChange={e => setCustomKeys(prev => prev.map(k => k.id === ck.id ? { ...k, value: e.target.value } : k))}
                      style={{ width: "100%", fontSize: 12, padding: "6px 9px", borderRadius: 7, border: `1px solid ${ck.value ? T.accent : T.border}`, background: T.appBg, color: T.textPrimary, outline: "none", fontFamily: "monospace", boxSizing: "border-box" as const }}
                    />
                  </div>
                ))}

                {/* Add key form */}
                {addingKey ? (
                  <div style={{ background: T.appBg, border: `1px solid ${T.border}`, borderRadius: 8, padding: "10px 12px" }}>
                    <div style={{ fontSize: 10, fontWeight: 600, color: T.textMuted, textTransform: "uppercase" as const, letterSpacing: "0.07em", marginBottom: 6 }}>
                      New API Key
                    </div>
                    <input
                      autoFocus
                      value={newKeyName}
                      onChange={e => setNewKeyName(e.target.value)}
                      placeholder="Provider name (e.g. OpenAI, Anthropic, Mistral…)"
                      style={{ width: "100%", fontSize: 12, padding: "6px 9px", borderRadius: 6, border: `1px solid ${T.border}`, background: T.card, color: T.textPrimary, outline: "none", marginBottom: 6, boxSizing: "border-box" as const }}
                    />
                    <input
                      type="password"
                      value={newKeyValue}
                      onChange={e => setNewKeyValue(e.target.value)}
                      onKeyDown={e => e.key === "Enter" && commitCustomKey()}
                      placeholder="Paste API key…"
                      style={{ width: "100%", fontSize: 12, padding: "6px 9px", borderRadius: 6, border: `1px solid ${T.border}`, background: T.card, color: T.textPrimary, outline: "none", fontFamily: "monospace", marginBottom: 8, boxSizing: "border-box" as const }}
                    />
                    <div style={{ display: "flex", gap: 6 }}>
                      <button
                        onClick={commitCustomKey}
                        style={{ flex: 1, fontSize: 11, fontWeight: 600, padding: "6px 0", borderRadius: 6, border: "none", background: T.accent, color: "#fff", cursor: "pointer" }}
                      >
                        Add Key
                      </button>
                      <button
                        onClick={() => { setAddingKey(false); setNewKeyName(""); setNewKeyValue(""); }}
                        style={{ fontSize: 11, padding: "6px 10px", borderRadius: 6, border: `1px solid ${T.border}`, background: "transparent", color: T.textMuted, cursor: "pointer" }}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => setAddingKey(true)}
                    style={{
                      display: "flex", alignItems: "center", gap: 6, width: "100%",
                      fontSize: 11, fontWeight: 500, padding: "7px 10px", borderRadius: 7,
                      border: `1px dashed ${T.border}`, background: "transparent",
                      color: T.textSecondary, cursor: "pointer", transition: "all 0.1s",
                    }}
                    onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = T.accent; (e.currentTarget as HTMLButtonElement).style.color = T.link; }}
                    onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = T.border; (e.currentTarget as HTMLButtonElement).style.color = T.textSecondary; }}
                  >
                    <span style={{ fontSize: 14, lineHeight: 1 }}>+</span>
                    Add any API key…
                  </button>
                )}
              </div>

              <button style={{ fontSize: 11, fontWeight: 500, padding: "7px 14px", borderRadius: 7, border: "none", background: T.accent, color: "#fff", cursor: "pointer", width: "100%" }}>
                Save Configuration
              </button>
            </div>
          )}
        </div>

        {/* Session stats */}
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "14px 16px", marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.08em", color: T.textMuted, marginBottom: 10 }}>Session</div>
          <div style={{ display: "flex", flexDirection: "column" as const, gap: 8 }}>
            {[
              { l: "Queries",    v: "3"               },
              { l: "Tool calls", v: "12"              },
              { l: "Model",      v: "Rule-based"      },
              { l: "Started",    v: "09:12 AM"        },
              { l: "Data scope", v: "FY 2024–25"      },
            ].map(({ l, v }) => (
              <div key={l} style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <span style={{ fontSize: 11, color: T.textMuted }}>{l}</span>
                <span style={{ fontSize: 12, fontWeight: 600, color: T.textPrimary, fontVariantNumeric: "tabular-nums" }}>{v}</span>
              </div>
            ))}
          </div>
        </div>

        {/* What the analyst can do */}
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "14px 16px", marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.08em", color: T.textMuted, marginBottom: 10 }}>
            Available Tools
          </div>
          <div style={{ display: "flex", flexDirection: "column" as const, gap: 7 }}>
            {[
              { icon: "💳", label: "get_outstanding_payments",  desc: "Receivables & overdue"  },
              { icon: "📦", label: "get_inventory_status",      desc: "Stock & coverage"        },
              { icon: "👥", label: "get_customer_segments",     desc: "RFM segmentation"        },
              { icon: "📍", label: "get_territory_summary",     desc: "Town & beat data"        },
              { icon: "🔐", label: "get_immutable_ledger",      desc: "Audit trail"             },
              { icon: "📈", label: "get_sales_trends",          desc: "Historical revenue"      },
            ].map(t => (
              <div key={t.label} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <span style={{ fontSize: 13, flexShrink: 0, marginTop: 1 }}>{t.icon}</span>
                <div>
                  <div style={{ fontSize: 10, fontFamily: "monospace", color: T.link }}>{t.label}</div>
                  <div style={{ fontSize: 10, color: T.textMuted }}>{t.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Disclaimer */}
        <div style={{ fontSize: 10, color: T.textMuted, lineHeight: "15px", padding: "0 2px" }}>
          Answers are generated from your ERP data using deterministic rules + optional LLM synthesis. Verify critical decisions with source records.
        </div>
      </div>

      {/* Keyframe for typing dots */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.3; transform: translateY(0); }
          50%       { opacity: 1;   transform: translateY(-3px); }
        }
      `}</style>
    </div>
  );
}

export default function App() {
  const [activeNav, setActiveNav] = useState("ai");

  const screenMap: Record<string, React.ReactNode> = {
    command:   <CommandCenter />,
    recovery:  <RevenueRecovery />,
    inventory: <InventoryOperations />,
    customers: <CustomerIntelligence />,
    ai:        <AiBusinessAnalyst />,
  };

  return (
    <div style={{ display: "flex", height: "100vh", background: T.appBg, fontFamily: "'Inter', system-ui, sans-serif", overflow: "hidden" }}>
      <Sidebar active={activeNav} onNav={setActiveNav} />
      <main style={{ flex: 1, overflow: activeNav === "ai" ? "hidden" : "auto", minWidth: 0, display: "flex", flexDirection: "column" }}>
        {screenMap[activeNav]}
      </main>
    </div>
  );
}
