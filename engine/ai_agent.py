"""
engine/ai_agent.py
==================
ReAct-style Agentic Business Intelligence Engine.

Implements a Reason + Act (ReAct) loop where the agent:
  1. Receives a natural language business question
  2. Thinks about which tool(s) to use
  3. Calls the tool, gets a data observation
  4. Reasons over the observation
  5. Repeats until it can give a grounded final answer

Every answer is backed by real data from the existing engine modules —
no hallucination, no fabricated numbers.

Architecture
------------
  WholesaleAgent
    ├── ToolRegistry      — maps tool names → callable wrappers of engine fns
    ├── AgentContext      — holds loaded DataFrames + formats them as text for LLM
    ├── LLMClient         — Gemini Flash → Groq Llama 3 → rule-based fallback
    └── ReAct loop        — Thought → Action → Observation → repeat → Final Answer

LLM Priority:
  1. Google Gemini Flash  (set GEMINI_API_KEY env var or pass directly)
  2. Groq Llama 3         (set GROQ_API_KEY env var)
  3. Rule-based fallback  (no API key needed — still shows full reasoning trace)

Razorpay Parallels:
  This agent is architecturally similar to Razorpay's "Slash" assistant and
  "Agent Studio" — tools that let business teams query operational data in
  natural language and get grounded, actionable answers.

Author: Wholesale BI System — Agent Edition
Python: 3.12
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
MAX_REACT_STEPS = 6          # safety ceiling on reasoning steps
FALLBACK_MODEL  = "rule-based"
GEMINI_MODEL    = "gemini-1.5-flash"
GROQ_MODEL      = "llama3-8b-8192"


# ═════════════════════════════════════════════════════════════════════════════
# 1. Agent Step — one round-trip in the ReAct loop
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class AgentStep:
    """Records one full step (Thought → Action → Observation) in the ReAct loop."""
    step_num:    int
    thought:     str
    action:      str
    action_args: dict
    observation: str
    elapsed_ms:  int = 0

    def to_display(self) -> dict:
        return {
            "step":        self.step_num,
            "thought":     self.thought,
            "action":      self.action,
            "observation": self.observation[:800] + ("…" if len(self.observation) > 800 else ""),
        }


@dataclass
class AgentResult:
    """Final output of the agent after completing the ReAct loop."""
    question:     str
    answer:       str
    steps:        list[AgentStep]
    llm_used:     str
    total_ms:     int
    tool_calls:   list[str]
    confidence:   str  # "HIGH" / "MEDIUM" / "LOW"

    @property
    def step_count(self) -> int:
        return len(self.steps)


# ═════════════════════════════════════════════════════════════════════════════
# 2. Agent Context — holds DataFrames + formats text summaries for LLM
# ═════════════════════════════════════════════════════════════════════════════

class AgentContext:
    """
    Packages all loaded business DataFrames into text summaries that the LLM
    can reason over. Keeps summaries short to fit within token limits.
    """

    def __init__(
        self,
        sales_df:     Optional[pd.DataFrame] = None,
        inventory_df: Optional[pd.DataFrame] = None,
        customer_df:  Optional[pd.DataFrame] = None,
    ):
        self.sales_df     = sales_df     if sales_df is not None     else pd.DataFrame()
        self.inventory_df = inventory_df if inventory_df is not None else pd.DataFrame()
        self.customer_df  = customer_df  if customer_df is not None  else pd.DataFrame()

    def is_empty(self) -> bool:
        return self.sales_df.empty and self.inventory_df.empty and self.customer_df.empty

    def business_summary(self) -> str:
        """One-paragraph text summary of the business state for the system prompt."""
        parts = []

        if not self.sales_df.empty:
            n_txn     = len(self.sales_df)
            date_col  = "date" if "date" in self.sales_df.columns else None
            date_range = ""
            if date_col:
                try:
                    dates      = pd.to_datetime(self.sales_df[date_col], errors="coerce").dropna()
                    date_range = f" from {dates.min().date()} to {dates.max().date()}"
                except Exception:
                    pass
            rev = 0.0
            if "sale_price" in self.sales_df.columns and "quantity" in self.sales_df.columns:
                rev = float(
                    (pd.to_numeric(self.sales_df["sale_price"], errors="coerce").fillna(0)
                     * pd.to_numeric(self.sales_df["quantity"], errors="coerce").fillna(0)
                    ).sum()
                )
            parts.append(
                f"Sales: {n_txn:,} transactions{date_range}. "
                f"Total revenue: ₹{rev:,.0f}."
            )

        if not self.inventory_df.empty:
            n_sku = len(self.inventory_df)
            stock_val = 0.0
            if "purchase_price" in self.inventory_df.columns and "quantity_in_stock" in self.inventory_df.columns:
                stock_val = float(
                    (pd.to_numeric(self.inventory_df["purchase_price"],  errors="coerce").fillna(0)
                     * pd.to_numeric(self.inventory_df["quantity_in_stock"], errors="coerce").fillna(0)
                    ).sum()
                )
            parts.append(f"Inventory: {n_sku} SKUs. Estimated stock value: ₹{stock_val:,.0f}.")

        if not self.customer_df.empty:
            n_cust = len(self.customer_df)
            parts.append(f"Customers: {n_cust} retailers/customers in the system.")

        return " ".join(parts) if parts else "No data loaded yet."

    def get_dataframes(self) -> dict[str, pd.DataFrame]:
        return {
            "sales":     self.sales_df,
            "inventory": self.inventory_df,
            "customer":  self.customer_df,
        }


# ═════════════════════════════════════════════════════════════════════════════
# 3. Tool Registry — wraps engine functions as agent-callable tools
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class Tool:
    """An agent-callable tool that wraps an engine function."""
    name:        str
    description: str
    fn:          Callable
    category:    str = "analytics"

    def call(self, **kwargs) -> str:
        """Call the tool and return a plain-text observation."""
        try:
            result = self.fn(**kwargs)
            return _format_result(result)
        except Exception as exc:
            return f"Tool error: {exc}"


def _format_result(result: Any) -> str:
    """Convert any engine output (DataFrame, dict, list, str) to readable text."""
    if isinstance(result, pd.DataFrame):
        if result.empty:
            return "No results found."
        # Show top rows as a compact text table
        n = min(10, len(result))
        return f"Found {len(result)} records. Top {n}:\n{result.head(n).to_string(index=False, max_colwidth=40)}"
    if isinstance(result, dict):
        lines = []
        for k, v in result.items():
            if isinstance(v, pd.DataFrame):
                lines.append(f"{k}: {len(v)} records")
            elif isinstance(v, float):
                lines.append(f"{k}: ₹{v:,.2f}")
            else:
                lines.append(f"{k}: {v}")
        return "\n".join(lines)
    if isinstance(result, list):
        return "\n".join(str(r) for r in result[:10])
    return str(result)


def build_tool_registry(context: AgentContext) -> dict[str, Tool]:
    """
    Build the complete tool registry by wrapping existing engine functions.
    Each tool receives pre-loaded DataFrames from the context — no re-loading.
    """
    sales     = context.sales_df
    inventory = context.inventory_df
    customers = context.customer_df

    tools: dict[str, Tool] = {}

    # ── Inventory / Dead Stock ─────────────────────────────────────────────
    def _dead_stock():
        from engine.analytics import detect_dead_stock
        if inventory.empty:
            return "No inventory data loaded."
        return detect_dead_stock(inventory)

    tools["get_dead_stock"] = Tool(
        name="get_dead_stock",
        description=(
            "Returns products that haven't sold recently. "
            "Shows days_unsold, capital_blocked (₹), and stock_status (DEAD/SLOW/ACTIVE). "
            "Use when asked about slow-moving stock, dead inventory, or capital blocked in stock."
        ),
        fn=_dead_stock,
        category="inventory",
    )

    # ── Outstanding Payments ───────────────────────────────────────────────
    def _outstanding_payments():
        from engine.analytics import get_outstanding_payments
        if sales.empty:
            return "No sales data loaded."
        return get_outstanding_payments(sales, customers)

    tools["get_outstanding_payments"] = Tool(
        name="get_outstanding_payments",
        description=(
            "Returns overdue customer invoices ranked by urgency. "
            "Shows customer_name, invoice_no, days_overdue, invoice_amount, risk_level (HIGH/MEDIUM/LOW). "
            "Use when asked about payments, collections, who owes money, or cash flow."
        ),
        fn=_outstanding_payments,
        category="payments",
    )

    # ── Payment Risk Score ─────────────────────────────────────────────────
    def _payment_risk():
        from engine.payment_intelligence import score_payment_risk
        if sales.empty:
            return "No sales data loaded."
        return score_payment_risk(sales, customers)

    tools["get_payment_risk_scores"] = Tool(
        name="get_payment_risk_scores",
        description=(
            "Predicts which customers are UNLIKELY to pay. Returns collection_probability (0-100%), "
            "recommended_action (Call/WhatsApp/Legal/Write-off), and risk tier per customer. "
            "Use when asked who won't pay, payment default risk, or collection strategy."
        ),
        fn=_payment_risk,
        category="payments",
    )

    # ── Customer Segments ──────────────────────────────────────────────────
    def _segments():
        from engine.segmentation import compute_rfm, segment_customers
        if sales.empty or customers.empty:
            return "Need both sales and customer data."
        rfm = compute_rfm(sales, customers)
        return segment_customers(rfm)

    tools["get_customer_segments"] = Tool(
        name="get_customer_segments",
        description=(
            "Segments customers into Champions / Loyal / At Risk / Lost using RFM + K-Means. "
            "Use when asked about customer health, churn risk, who to retain, or customer value."
        ),
        fn=_segments,
        category="customers",
    )

    # ── Anomalies ──────────────────────────────────────────────────────────
    def _anomalies():
        from engine.anomaly_detector import detect_anomalies
        if sales.empty:
            return "No sales data loaded."
        df = detect_anomalies(sales)
        return df[df["is_anomaly"] == True] if "is_anomaly" in df.columns else df

    tools["get_anomalies"] = Tool(
        name="get_anomalies",
        description=(
            "Detects suspicious transactions using Isolation Forest. Flags anomalies in "
            "discount_pct, quantity, and price. Use when asked about fraud, suspicious sales, "
            "unusual discounts, or data integrity issues."
        ),
        fn=_anomalies,
        category="anomaly",
    )

    # ── Demand Forecast / Restock Alerts ──────────────────────────────────
    def _forecast_alerts():
        from engine.forecasting import forecast_demand, detect_demand_spikes
        if sales.empty:
            return "No sales data loaded."
        try:
            top_cat = sales["category"].mode().iloc[0] if "category" in sales.columns else "FMCG"
            fc      = forecast_demand(sales, top_cat, 30)
            return detect_demand_spikes({top_cat: fc}, inventory)
        except Exception as exc:
            return f"Forecast not available: {exc}"

    tools["get_restock_alerts"] = Tool(
        name="get_restock_alerts",
        description=(
            "Runs Prophet demand forecast and returns items where stock will run out soon. "
            "Shows days_coverage, predicted_demand, stock_gap. "
            "Use when asked about restock, what to order, stock running out, or upcoming demand."
        ),
        fn=_forecast_alerts,
        category="forecast",
    )

    # ── CEO Morning Briefing ───────────────────────────────────────────────
    def _briefing():
        from engine.analytics import detect_dead_stock, get_outstanding_payments
        from engine.recommender import generate_recommendations, ceo_morning_briefing
        try:
            ds_df   = detect_dead_stock(inventory) if not inventory.empty else None
            out_df  = get_outstanding_payments(sales, customers) if not sales.empty else None
            recs    = generate_recommendations(dead_stock_df=ds_df, outstanding_df=out_df)
            return ceo_morning_briefing(recs)
        except Exception as exc:
            return f"Could not generate briefing: {exc}"

    tools["get_morning_briefing"] = Tool(
        name="get_morning_briefing",
        description=(
            "Generates a CEO Morning Briefing — a prioritised summary of the top actions "
            "for today covering payments, inventory, and customer alerts. "
            "Use when asked 'what should I do today', 'morning briefing', or 'top priorities'."
        ),
        fn=_briefing,
        category="summary",
    )

    # ── Area / Town Performance ────────────────────────────────────────────
    def _area_rank():
        from engine.analytics import area_sales_ranking
        if sales.empty:
            return "No sales data loaded."
        return area_sales_ranking(sales)

    tools["get_area_performance"] = Tool(
        name="get_area_performance",
        description=(
            "Ranks towns/areas by revenue, growth, and number of customers. "
            "Use when asked about which area/town is performing best or worst, "
            "geographic performance, or regional insights."
        ),
        fn=_area_rank,
        category="analytics",
    )

    return tools


# ═════════════════════════════════════════════════════════════════════════════
# 4. LLM Client — Gemini → Groq → Rule-based fallback
# ═════════════════════════════════════════════════════════════════════════════

class LLMClient:
    """
    Tries LLM providers in priority order:
      1. Google Gemini Flash  (GEMINI_API_KEY)
      2. Groq Llama 3         (GROQ_API_KEY)
      3. Rule-based fallback  (always works, no key needed)
    """

    def __init__(self, gemini_key: Optional[str] = None, groq_key: Optional[str] = None):
        self.gemini_key = gemini_key or os.getenv("GEMINI_API_KEY", "")
        self.groq_key   = groq_key   or os.getenv("GROQ_API_KEY",   "")
        self.backend    = self._detect_backend()
        logger.info("LLMClient: using backend '%s'", self.backend)

    def _detect_backend(self) -> str:
        if self.gemini_key:
            try:
                import google.generativeai  # noqa: F401
                return "gemini"
            except ImportError:
                logger.warning("google-generativeai not installed. Trying Groq.")
        if self.groq_key:
            try:
                import groq  # noqa: F401
                return "groq"
            except ImportError:
                logger.warning("groq not installed. Using rule-based fallback.")
        return FALLBACK_MODEL

    @property
    def name(self) -> str:
        return self.backend

    def generate(self, prompt: str, system: str = "") -> str:
        """Generate a completion. Returns plain text."""
        if self.backend == "gemini":
            return self._gemini(prompt, system)
        if self.backend == "groq":
            return self._groq(prompt, system)
        return self._fallback(prompt)

    def _gemini(self, prompt: str, system: str) -> str:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_key)
            model = genai.GenerativeModel(
                GEMINI_MODEL,
                system_instruction=system or _SYSTEM_PROMPT,
            )
            resp = model.generate_content(prompt)
            return resp.text.strip()
        except Exception as exc:
            logger.error("Gemini error: %s. Falling back.", exc)
            return self._fallback(prompt)

    def _groq(self, prompt: str, system: str) -> str:
        try:
            from groq import Groq
            client = Groq(api_key=self.groq_key)
            msgs = []
            if system:
                msgs.append({"role": "system", "content": system or _SYSTEM_PROMPT})
            msgs.append({"role": "user", "content": prompt})
            resp = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=msgs,
                max_tokens=1024,
                temperature=0.3,
            )
            return resp.choices[0].message.content.strip()
        except Exception as exc:
            logger.error("Groq error: %s. Falling back.", exc)
            return self._fallback(prompt)

    def _fallback(self, prompt: str) -> str:
        """
        Rule-based fallback: parses the prompt to determine which tool
        the agent should call next, without an LLM.
        """
        p = prompt.lower()

        # If this is a "final answer" request (observation already in prompt)
        if "observation:" in p and "based on" in p:
            return "Final Answer: Based on the data retrieved, I have analyzed your business situation. Please review the detailed observations above for specific numbers and recommendations."

        # Tool selection heuristics
        if any(w in p for w in ["dead stock", "slow moving", "not sold", "capital blocked", "inventory"]):
            return 'Thought: I need to check inventory data for dead or slow-moving stock.\nAction: get_dead_stock\nAction Input: {}'

        if any(w in p for w in ["pay", "overdue", "outstanding", "collection", "owes", "dues", "receivable", "payment"]):
            if any(w in p for w in ["risk", "default", "won't pay", "predict", "probability", "likely to not pay", "most likely"]):
                return 'Thought: I need to score payment default risk for customers.\nAction: get_payment_risk_scores\nAction Input: {}'
            return 'Thought: I need to check outstanding payments and overdue invoices.\nAction: get_outstanding_payments\nAction Input: {}'

        if any(w in p for w in ["churn", "segment", "loyal", "at risk", "lost customer", "retain"]):
            return 'Thought: I need customer segmentation data to identify at-risk customers.\nAction: get_customer_segments\nAction Input: {}'

        if any(w in p for w in ["fraud", "anomal", "suspicious", "unusual", "discount abuse"]):
            return 'Thought: I need to check for anomalous or suspicious transactions.\nAction: get_anomalies\nAction Input: {}'

        if any(w in p for w in ["restock", "order", "stock out", "running out", "demand", "forecast"]):
            return 'Thought: I need demand forecasts and restock alerts.\nAction: get_restock_alerts\nAction Input: {}'

        if any(w in p for w in ["area", "town", "region", "geography", "uniara", "tonk"]):
            return 'Thought: I need area/town performance data.\nAction: get_area_performance\nAction Input: {}'

        if any(w in p for w in ["today", "morning", "briefing", "priority", "what should", "what to do"]):
            return 'Thought: The user wants an executive summary of today\'s priorities.\nAction: get_morning_briefing\nAction Input: {}'

        # Default
        return 'Thought: Let me get an overview of the business priorities.\nAction: get_morning_briefing\nAction Input: {}'


# ═════════════════════════════════════════════════════════════════════════════
# 5. System Prompt
# ═════════════════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = """You are an expert AI Business Analyst for a wholesale distribution business in India.
You help the business owner make data-driven decisions about inventory, payments, customers, and sales.

You have access to these tools:
{tools}

You follow the ReAct pattern strictly:
- Thought: reason about what to do next
- Action: tool name to call
- Action Input: JSON dict of arguments (use {{}} if no arguments needed)
- Observation: [tool result will be inserted here]
- ... repeat as needed ...
- Final Answer: your grounded, specific, actionable answer in plain English

Rules:
1. ALWAYS ground your answer in the actual data from tool observations
2. Use ₹ for all Indian Rupee amounts
3. Be specific — name customers, products, and amounts
4. Keep Final Answer under 200 words but make it actionable
5. If data is missing or tools return no results, say so clearly
6. Never make up numbers — only use what the tools return
"""


# ═════════════════════════════════════════════════════════════════════════════
# 6. ReAct Agent — the main loop
# ═════════════════════════════════════════════════════════════════════════════

class WholesaleAgent:
    """
    ReAct-style agent for wholesale business intelligence.

    Usage::

        from engine.ai_agent import WholesaleAgent, AgentContext

        ctx   = AgentContext(sales_df=sales, inventory_df=inv, customer_df=cust)
        agent = WholesaleAgent(context=ctx, gemini_key="YOUR_KEY")
        result = agent.run("Which customers are at risk of churning?")

        print(result.answer)
        for step in result.steps:
            print(step.to_display())
    """

    def __init__(
        self,
        context:    AgentContext,
        gemini_key: Optional[str] = None,
        groq_key:   Optional[str] = None,
    ):
        self.context  = context
        self.llm      = LLMClient(gemini_key=gemini_key, groq_key=groq_key)
        self.tools    = build_tool_registry(context)

    @property
    def llm_name(self) -> str:
        return self.llm.name

    def _tool_descriptions(self) -> str:
        return "\n".join(
            f"- {name}: {tool.description}"
            for name, tool in self.tools.items()
        )

    def _build_react_prompt(
        self,
        question: str,
        history:  list[AgentStep],
        context_summary: str,
    ) -> str:
        """Build the full prompt for the next ReAct step."""
        tool_desc = self._tool_descriptions()

        lines = [
            f"Business Context: {context_summary}",
            "",
            f"Available Tools:\n{tool_desc}",
            "",
            f"Question: {question}",
            "",
        ]

        for step in history:
            lines += [
                f"Thought: {step.thought}",
                f"Action: {step.action}",
                f"Action Input: {json.dumps(step.action_args)}",
                f"Observation: {step.observation}",
                "",
            ]

        lines.append("What is your next Thought? (or write 'Final Answer: ...' if ready)")
        return "\n".join(lines)

    def _parse_llm_response(self, response: str) -> tuple[str, str, dict, bool]:
        """
        Parse LLM response into (thought, action, action_args, is_final).
        Returns is_final=True when the LLM writes 'Final Answer: ...'.
        """
        # Check for final answer
        final_match = re.search(r"Final Answer:\s*(.+)", response, re.DOTALL | re.IGNORECASE)
        if final_match:
            return "", "", {}, True

        # Extract Thought
        thought_match = re.search(r"Thought:\s*(.+?)(?=Action:|$)", response, re.DOTALL | re.IGNORECASE)
        thought = thought_match.group(1).strip() if thought_match else response.strip()

        # Extract Action
        action_match = re.search(r"Action:\s*(\w+)", response, re.IGNORECASE)
        action = action_match.group(1).strip() if action_match else "get_morning_briefing"

        # Extract Action Input
        args_match = re.search(r"Action Input:\s*(\{.*?\})", response, re.DOTALL | re.IGNORECASE)
        args = {}
        if args_match:
            try:
                args = json.loads(args_match.group(1))
            except json.JSONDecodeError:
                args = {}

        # Validate action name
        if action not in self.tools:
            # Try fuzzy match
            for tool_name in self.tools:
                if tool_name.lower() in action.lower() or action.lower() in tool_name.lower():
                    action = tool_name
                    break
            else:
                action = "get_morning_briefing"

        return thought, action, args, False

    def _extract_final_answer(self, response: str) -> str:
        match = re.search(r"Final Answer:\s*(.+)", response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # If it doesn't say "Final Answer:" but it doesn't have an Action either, treat it as the final answer
        if "Action:" not in response and "Thought:" not in response:
            return response.strip()
        return ""

    def run(self, question: str) -> AgentResult:
        """
        Run the full ReAct loop for the given question.

        Returns an AgentResult with the answer, all reasoning steps,
        and metadata about which LLM was used.
        """
        t_start     = time.time()
        history: list[AgentStep] = []
        tool_calls: list[str]    = []
        context_summary          = self.context.business_summary()
        final_answer             = ""
        confidence               = "HIGH"

        logger.info("Agent starting. LLM: %s. Question: %s", self.llm.name, question[:80])

        for step_num in range(1, MAX_REACT_STEPS + 1):
            t_step = time.time()

            # Build prompt for this step
            system_prompt = _SYSTEM_PROMPT.format(tools=self._tool_descriptions())
            react_prompt  = self._build_react_prompt(question, history, context_summary)

            # Ask LLM what to do next
            llm_response = self.llm.generate(react_prompt, system=system_prompt)
            thought, action, action_args, is_final = self._parse_llm_response(llm_response)

            if is_final:
                final_answer = self._extract_final_answer(llm_response)
                break

            # Call the tool
            tool = self.tools.get(action)
            if tool is None:
                observation = f"Tool '{action}' not found. Available: {list(self.tools.keys())}"
                confidence  = "LOW"
            else:
                if len(history) > 0 and history[-1].action == action and history[-1].action_args == action_args:
                    observation = "I already called this tool and got the same result. I should stop and provide a Final Answer."
                else:
                    observation = tool.call(**action_args)
                tool_calls.append(action)

            elapsed_ms = int((time.time() - t_step) * 1000)

            step = AgentStep(
                step_num    = step_num,
                thought     = thought,
                action      = action,
                action_args = action_args,
                observation = observation,
                elapsed_ms  = elapsed_ms,
            )
            history.append(step)
            logger.debug("Step %d: action=%s elapsed=%dms", step_num, action, elapsed_ms)

            # Forcefully break out if we are in a loop
            if len(history) > 1 and history[-1].action == history[-2].action and history[-1].action_args == history[-2].action_args:
                logger.warning("Agent is looping on %s. Breaking.", action)
                break

            # After last allowed step, force final answer
            if step_num == MAX_REACT_STEPS:
                final_prompt = (
                    react_prompt
                    + f"\nThought: {thought}\nAction: {action}\nObservation: {observation}\n"
                    + "Based on all the above data, write your Final Answer:"
                )
                final_response = self.llm.generate(final_prompt, system=system_prompt)
                final_answer   = self._extract_final_answer(final_response)
                if not final_answer:
                    final_answer = self._synthesize_from_history(question, history)
                    confidence   = "MEDIUM"

        if not final_answer:
            final_answer = self._synthesize_from_history(question, history)
            confidence   = "MEDIUM"

        total_ms = int((time.time() - t_start) * 1000)
        logger.info(
            "Agent done. Steps: %d, Tools: %s, LLM: %s, Time: %dms",
            len(history), tool_calls, self.llm.name, total_ms,
        )

        return AgentResult(
            question   = question,
            answer     = final_answer,
            steps      = history,
            llm_used   = self.llm.name,
            total_ms   = total_ms,
            tool_calls = tool_calls,
            confidence = confidence,
        )

    def _synthesize_from_history(self, question: str, history: list[AgentStep]) -> str:
        """
        Fallback synthesis when LLM doesn't produce a Final Answer.
        Extracts key info from observations and builds a structured answer.
        """
        if not history:
            return (
                "I don't have enough data to answer that question. "
                "Please make sure your sales, inventory, and customer data are loaded."
            )

        parts = [f"Here's what I found about '{question}':\n"]
        for step in history:
            # Don't show duplicate identical steps in the fallback synthesis
            if step.step_num > 1 and history[step.step_num - 2].action == step.action:
                continue
            tool_display = step.action.replace("_", " ").title()
            obs_short    = step.observation[:300]
            parts.append(f"**{tool_display}:** {obs_short}")

        parts.append(
            "\nReview the detailed observations above for specific numbers. "
            "For a more precise answer, set a GEMINI_API_KEY in your environment."
        )
        return "\n\n".join(parts)


# ═════════════════════════════════════════════════════════════════════════════
# 7. Convenience Function — quick single-call interface
# ═════════════════════════════════════════════════════════════════════════════

def ask(
    question:     str,
    sales_df:     Optional[pd.DataFrame] = None,
    inventory_df: Optional[pd.DataFrame] = None,
    customer_df:  Optional[pd.DataFrame] = None,
    gemini_key:   Optional[str] = None,
    groq_key:     Optional[str] = None,
) -> AgentResult:
    """
    One-line interface to the WholesaleAgent.

    Example::

        result = ask(
            "Which customers are at risk of churning?",
            sales_df=sales, inventory_df=inv, customer_df=cust,
        )
        print(result.answer)
    """
    ctx   = AgentContext(sales_df=sales_df, inventory_df=inventory_df, customer_df=customer_df)
    agent = WholesaleAgent(context=ctx, gemini_key=gemini_key, groq_key=groq_key)
    return agent.run(question)


# ─── Suggested questions for the UI ──────────────────────────────────────────
SUGGESTED_QUESTIONS = [
    "What should I focus on today?",
    "Which customers are most likely to not pay me?",
    "Which products should I reorder this week?",
    "Are there any suspicious or fraudulent transactions?",
    "Which customers are about to churn?",
    "Which area/town is performing best this month?",
    "What is my dead stock situation?",
    "Give me my morning briefing.",
]
