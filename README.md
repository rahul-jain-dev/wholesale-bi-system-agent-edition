# AI Revenue Recovery Agent for Wholesale Receivables

An autonomous AI agent designed for **Razorpay AI Buildathon — Track 3: AI Revenue Recovery**.

## 1. Problem
Wholesale B2B businesses suffer from severe cash flow bottlenecks due to outstanding receivables. Manually chasing payments is inefficient, emotionally taxing, and often targets the wrong customers. Businesses waste time on customers who were going to pay anyway, or too late on high-risk accounts that eventually default.

## 2. Why revenue recovery matters
Uncollected receivables directly constrain working capital. Accelerating cash conversion cycles through intelligent interventions can be the difference between a business scaling or collapsing.

## 3. Solution
An AI Revenue Recovery Agent that orchestrates a deterministic policy engine to automatically identify at-risk receivables, prioritize interventions by Expected Recoverable Value, and execute bounded recovery actions via simulated payment links and targeted communication.

## 4. Architecture
The system employs a **hybrid architecture** that guarantees safety in financial operations:
* **The Orchestrator:** An LLM (via Groq or Gemini) that parses intent, reasons over data, and calls deterministic tools.
* **The Engine:** A deterministic Recovery Policy Engine that strictly controls state transitions, bounds actions, and logs outcomes. The LLM cannot bypass the engine.

## 5. Agent workflow
1. **Detect Revenue at Risk:** Scans all open invoices and predicts default probability.
2. **Prioritize:** Ranks customers by Expected Recoverable Value.
3. **Choose Bounded Intervention:** Selects the precise action (Wait, Reminder, Payment Link, Escalation).
4. **Execute:** Generates targeted messaging and payment links.
5. **Check Outcome:** Deterministically simulates payment results based on probability and intervention effectiveness.
6. **State Transition:** Progresses the customer to Recovered, Escalated, or Stopped.
7. **Audit:** Writes every action to a canonical, append-only ledger.

## 6. ML payment-risk model
A Gradient Boosting classifier built on feature-engineered sales data (recency, frequency, monetary value, days overdue, 3-month trend) predicts the likelihood of payment. To ensure robustness, a rule-based heuristic acts as a fallback for sparse data or edge cases.

## 7. Recovery policy / state machine
The engine enforces a strict state machine:
`IDENTIFIED → FIRST_REMINDER → WAITING_FOR_PAYMENT → SECOND_REMINDER → ESCALATED → RECOVERED`
Transitions are strictly verified. Terminal states (`RECOVERED`, `STOPPED`) cannot be re-entered into the contact loop.

## 8. Expected vs actual recovery
Customers are prioritized by **Expected Recovery** (`Outstanding Amount × Collection Probability × Urgency Multiplier`). The simulation tracks **Actual Simulated Recovery** to measure the campaign's true financial impact (`Recovery Performance = Actual / Expected`).

## 9. Auditability
Every tool call, agent query, state transition, and payment outcome is written to a canonical, append-only CSV log (`data/recovery_audit.csv`). This ensures complete transparency for every automated decision.

## 10. Demo screenshots
*(Add screenshots of the **💳 Revenue Recovery & Risk** workspace and **🤖 AI Business Analyst** workspace here)*

## 11. How to run
```bash
# 1. Create a virtual environment and install requirements
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# 2. Run the application
python -m streamlit run app\streamlit_app.py
```

## 12. Demo questions

**Visual demo** — navigate to the **💳 Revenue Recovery & Risk** workspace and click **▶️ Run Today's Revenue Recovery Campaign**.

**Conversational demo** — navigate to the **🤖 AI Business Analyst** workspace and ask:
1. *"Who should we contact today to maximize expected revenue recovery?"*
2. *"Run today's recovery campaign."*
3. *"What happened in today's recovery campaign?"*

## 13. Simulation disclaimer
**Demo simulation — no real payments are processed.**
Payment links (`rzp.io/i/...`) are mock links generated deterministically for demonstration purposes. 

## 14. Limitations
* **Small Sample Size:** The demo data contains a limited number of overdue customers, resulting in high variance for probabilistic simulations.
* **Single-Node Execution:** The `csv.writer` audit logger is not thread-safe for high-concurrency environments.

## 15. Future production architecture
* **CURRENT DEMO:** Uses Streamlit session state for interactive campaign state orchestration and an append-only CSV for auditing.
* **PRODUCTION VERSION:** Would replace Streamlit session state with durable workflow storage (e.g., Temporal or AWS Step Functions) and PostgreSQL for transactional integrity, allowing the agent to run asynchronously and survive server restarts.
