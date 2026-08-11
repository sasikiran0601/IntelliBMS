# IntelliBMS — Hackathon Evaluation Guide

> **Project:** IntelliBMS — AI-Powered Battery Management Intelligence Platform
> **Stack:** Python · FastAPI · TensorFlow · XGBoost · React · Docker · AWS EC2

---

## ROUND 1 — 11:00 AM (25 Marks)

---

### 1. Problem Understanding & Analysis (10 Marks)

#### What is the problem?

Lithium-ion batteries power electric vehicles, renewable energy storage grids, and critical medical and industrial devices. The central operational challenge is: **operators do not know how healthy their battery is right now, or how many cycles it has left.**

Traditional Battery Management Systems (BMS) use two crude signals:
- **Fixed voltage cutoff thresholds** — the battery is "okay" until voltage drops below a hardcoded limit
- **Simple cycle counters** — treat every battery identically regardless of actual usage

This approach fails because battery degradation is **non-linear, history-dependent, and multi-factorial.** The same cell cycled at 40°C degrades 2–3x faster than one at 25°C. Deep discharge cycles below 20% accelerate lithium plating. High C-rate charging causes thermal stress. None of this is captured by a cycle counter.

#### What are the consequences of this gap?

| Failure Mode | Cause | Impact |
|---|---|---|
| Premature Retirement | BMS is over-conservative | Wastes 15–25% of remaining capacity, inflates cost |
| Over-operation | BMS misses actual degradation | Thermal runaway, fire risk, catastrophic failure |
| No actionable warning | Rule-based threshold triggers too late | No time for maintenance planning |

#### What does IntelliBMS solve?

IntelliBMS delivers two outputs that rule-based systems cannot produce:

1. **State of Health (SOH):** A continuous percentage (100% = new, 70% = end-of-life) derived from real electrochemical measurements — not just voltage thresholds.
2. **Remaining Useful Life (RUL):** A forward-looking cycle projection (best-case / likely / worst-case) that enables proactive, data-driven maintenance scheduling.

Additionally, the system explains *why* a battery is degrading — identifying active mechanisms like high temperature exposure, deep discharge, or internal resistance growth — and translates all of this into a plain-language AI safety narrative accessible to non-technical operators.

#### Why does this matter now?

- Global EV fleet projected to exceed 300 million vehicles by 2030.
- Battery replacement is the single largest cost driver in EV total cost of ownership.
- Unplanned battery failures in energy storage grids cause grid instability events.
- Proprietary BMS hardware costs $10,000–$50,000 per installation. IntelliBMS achieves the same intelligence using open datasets and open-source tooling.

---

### 2. AI Approach & Solution Design (10 Marks)

#### Why two separate models?

SOH and RUL are fundamentally different prediction problems requiring different AI paradigms:

| Property | SOH | RUL |
|---|---|---|
| What it is | Current capacity as % of rated | Cycles remaining to 70% SOH |
| Input domain | Fine-grained within-cycle time-series | Aggregate cycle-level statistics |
| Temporal nature | Sequential — each reading depends on prior readings | Tabular — features summarize the whole cycle |
| Best model type | Sequence model (LSTM) | Tree-based regression (XGBoost) |

#### Model 1: Stacked LSTM for SOH

**Architecture:**
```
Input: (batch, 50 timesteps, 3 features: voltage, current, temperature)
  -> LSTM(64 units, return_sequences=True)
  -> LSTM(32 units)
  -> Dense(1)
Output: SOH as a scalar percentage
```

**Why LSTM:**
Battery degradation is temporally dependent. Voltage at timestep T is not independent of voltages at T-1 through T-49. A cell under high load for 30 consecutive seconds behaves differently from one that just started discharging. LSTM's gated memory mechanism explicitly models these long-range dependencies — something a feedforward network or XGBoost cannot do on raw time-series.

**Training Strategy:**
- GroupShuffleSplit by `battery_id` ensures the test set contains an entirely different battery cell — true cross-battery generalization, not just held-out timesteps
- Train batteries: B0005, B0007, B0018
- Test battery: **B0006** (held out completely, never seen during training)
- Sequence length: 50 consecutive timesteps per window
- Features normalized using MinMaxScaler fitted only on training data (no data leakage)

#### Model 2: XGBoost Regressor for RUL

**Configuration:**
```
n_estimators = 500
learning_rate = 0.05
max_depth = 5
reg_alpha (L1) = 0.1
reg_lambda (L2) = 1.0
```

**Why XGBoost:**
RUL depends on summarized cycle-level patterns — average temperature, depth of discharge, charge time, internal resistance growth rate — not raw voltage readings. These are heterogeneous tabular features across different physical domains. Gradient boosting handles mixed-domain tabular data natively, is robust to outliers, and provides direct feature importance scores identifying which degradation mechanisms are most active per battery.

**Feature Set (20 dimensions):**
Temperature profile (avg, max, delta), C-rate, depth of discharge, charge duration, discharge duration, minimum voltage, end voltage, three internal resistance metrics (electrolyte resistance, charge transfer resistance, Warburg impedance), and SOH at cycle time.

**RUL Label Generation:**
For batteries that did not reach 70% SOH within the dataset, labels are generated by fitting a scipy exponential decay curve to the observed SOH trajectory and extrapolating to the end-of-life threshold. This avoids discarding valid training data.

**Inference Output:**
Three RUL bands — best-case (+20%), likely (median), worst-case (-20%) — giving operators a probabilistic range rather than a falsely precise single number.

#### Model 3: AI Safety Assistant (GPT-4o-mini)

The assistant receives the current SOH, RUL, and degradation driver list and generates a structured safety narrative under a strict system prompt that:
- Enforces one of three safety categories: *Normal Operation*, *Monitor Closely*, *Replace Soon*
- Requires a mandatory RUL uncertainty disclaimer on every response
- Prohibits unsafe instructions (no bypassing BMS, no overriding limits)

**Three-tier fallback chain:**
1. n8n workflow (primary)
2. n8n webhook (secondary)
3. Local deterministic rule engine (tertiary — guarantees 100% uptime)

#### Degradation Driver Detection

At every simulation step, the system evaluates current telemetry against physical thresholds:

| Driver | Threshold | Physical Mechanism |
|---|---|---|
| High Temperature | > 35°C | Accelerates SEI layer growth |
| Deep Discharge | > 85% DoD | Causes lithium plating |
| High C-Rate | > 1C / 40 A | Thermal stress, accelerated aging |
| Internal Resistance | > baseline Re | Electrolyte degradation |

---

### 3. Innovation & Feasibility (5 Marks)

#### What is innovative?

1. **Cross-battery generalization:** Most academic BMS models train and test on the same battery. IntelliBMS enforces GroupShuffleSplit — the test battery (B0006) is never seen during training. This is the difference between a lab demo and a deployable system.

2. **Explainable + quantitative outputs together:** Every prediction is accompanied by the active degradation drivers explaining *why* the battery is at that SOH and RUL. Operators understand the root cause, not just the metric.

3. **Natural language safety bridge:** The AI assistant converts statistical outputs into plain English safety classifications, making the platform accessible to non-technical operators.

4. **Production-grade deployment from open data:** The entire platform uses freely available NASA research datasets and open-source tooling, deployed on AWS with CI/CD, HTTPS, and infrastructure-as-code.

5. **Graceful degradation architecture:** Two-tier fallback (n8n to local rule engine) ensures the assistant always responds, even during full external API outages.

#### Is it feasible?

**Yes — it is already deployed and live.**

- Running on AWS EC2 at a public HTTPS endpoint
- LSTM and XGBoost models trained, serialized, and served via FastAPI
- React dashboard containerized and running
- GitHub Actions CI/CD automatically re-deploys on every push to main
- Terraform manages infrastructure as code — entire environment reproducible in under 10 minutes

---

## ROUND 2 — 2:00 PM (25 Marks)

---

### 4. Implementation & Functionality (10 Marks)

#### End-to-end architecture

```
[React Dashboard]
      |
      | REST API (HTTPS via NGINX)
      |
[FastAPI Backend — Uvicorn]
      |
      ├── /batteries        -> CRUD for battery entities (SQLAlchemy + SQLite)
      ├── /simulate         -> Real-time telemetry simulation + ML inference
      ├── /assistant/chat   -> AI safety narrative (GPT-4o-mini)
      └── /upload           -> CSV upload for custom battery data
      |
      ├── ModelService      -> Loads soh_model.h5 + rul_model.pkl at startup
      ├── SimulationService -> Generates telemetry, calls LSTM + XGBoost
      └── AssistantService  -> Manages 3-tier fallback chain
      |
[Docker Container] -> [AWS EC2] -> [NGINX HTTPS] -> [GitHub Actions CI/CD]
                                                  -> [Terraform IaC]
```

#### Key functional flows

**SOH Prediction Flow:**
1. Simulation generates voltage, current, temperature readings at each timestep
2. Readings appended to per-battery `history_buffer`
3. Once buffer reaches 50 readings, LSTM runs inference on the last 50 timesteps
4. Output is inverse-transformed from scaled space to SOH percentage
5. Returned in API response and rendered on dashboard trend chart

**RUL Prediction Flow:**
1. Each cycle, 20-dimensional feature vector computed from telemetry statistics
2. XGBoost predicts median RUL; +/-20% applied for best/worst-case bands
3. Degradation thresholds evaluated; active drivers labeled
4. All three values + driver list returned in API response

**Database:**
- SQLite via SQLAlchemy ORM
- Tables: `batteries`, `simulation_history`, `uploaded_datasets`
- All predictions logged per battery per cycle for trend visualization

#### What the demo shows

- Live battery simulation with real-time SOH decline curve (Recharts)
- RUL bands updating every cycle
- Active degradation drivers displayed as colored badges
- AI assistant generating a safety narrative on demand
- Multiple battery profiles (Tesla Model S, BMW i3, Nissan Leaf, Chevy Bolt) with different degradation rates
- CSV upload for custom battery data

---

### 5. AI Performance & Effectiveness (10 Marks)

#### LSTM SOH Performance

| Metric | Value | Context |
|---|---|---|
| Mean Absolute Error | **5.52 percentage points** | On fully unseen battery B0006 |
| R-squared Score | **0.678** | On fully unseen battery B0006 |
| Evaluation method | GroupShuffleSplit (battery-wise) | True cross-battery generalization |
| Training set | B0005, B0007, B0018 | 3 batteries, ~127,000 sequences |
| Test set | B0006 only | Never seen during training |

An MAE of 5.52 pp means when the model predicts SOH = 85%, the true SOH is within +/-5.52 pp on average. For maintenance scheduling this is actionable — it is the difference between scheduling a replacement at 79.5% vs. 90.5%, not the difference between healthy and end-of-life.

The R-squared of 0.678 on a completely unseen battery confirms the model has learned genuine degradation patterns, not battery-specific memorization.

#### XGBoost RUL Performance

- GroupKFold cross-validation enforces battery-wise evaluation splits
- Three-band output (best/likely/worst) explicitly communicates uncertainty rather than hiding it
- Feature importance scores identify dominant degradation mechanisms per battery
- Exponential decay extrapolation used for batteries that did not reach end-of-life, preventing training data loss

#### AI Safety Assistant Effectiveness

- Enforced category output prevents ambiguous responses
- Mandatory uncertainty disclaimer on every RUL output prevents over-reliance on point estimates
- Hard prohibition on unsafe instructions in system prompt
- Local fallback rule engine: SOH < 80 = "Replace Soon", SOH 80–90 = "Monitor Closely", SOH > 90 = "Normal Operation"

---

### 6. Demo, Presentation & Team Response (5 Marks)

#### Demo Script (suggested flow)

1. **Open the dashboard** — show 4 battery profiles, each with different SOH levels.
2. **Start simulation on Chevy Bolt (SOH 76.3%)** — show real-time SOH decline, degradation drivers activating, RUL bands narrowing.
3. **Trigger AI assistant** — show GPT-4o-mini returning "Replace Soon" classification with uncertainty disclaimer.
4. **Switch to Tesla Model S (SOH 98.5%)** — show "Normal Operation" response, flat RUL bands.
5. **Upload a CSV** — demonstrate custom battery data ingestion.
6. **Show key code files** — `generate_and_train.py` (LSTM), `preprocess_battery_dataset.py` (pipeline), `app/api/routes/assistant.py` (3-tier fallback).

#### Jury Q&A — Suggested Responses

**"Why LSTM and not a simpler model?"**
SOH is temporally dependent. A single voltage reading means nothing — it is the trajectory over 50 timesteps that reveals degradation. LSTM's gated memory captures this; a feedforward network treats each timestep independently and loses all temporal context.

**"Why XGBoost and not LSTM for RUL?"**
RUL needs cycle-level aggregates across heterogeneous physical features (temperature, resistance, C-rate), not timestep-level resolution. Gradient boosting handles mixed-domain tabular features natively and gives interpretable feature importance. LSTM would overfit to within-cycle noise when predicting a cycle-count horizon.

**"How does the model generalize to new batteries?"**
GroupShuffleSplit ensures the model trains on some batteries and tests on entirely different cells. B0006 was held out completely — the 5.52 pp MAE and 0.678 R-squared are measured on a battery the model never processed during training.

**"What happens if n8n is down?"**
The assistant has a two-tier fallback: n8n webhook primary, local deterministic rule engine secondary. The local engine applies explicit SOH/RUL thresholds to generate a correctly categorized safety narrative with zero external dependency.

**"How is this different from existing BMS?"**
Existing BMS uses fixed voltage thresholds and cycle counters with no per-cell learning. IntelliBMS trains on real electrochemical degradation measurements, adapts to actual usage history, explains which mechanisms are active, and provides a forward-looking RUL projection — none of which rule-based systems can deliver.

---

## Quick Reference Card

| Item | Value |
|---|---|
| SOH Model | Stacked LSTM (64 -> 32 -> Dense) |
| RUL Model | XGBoost (500 trees, depth 5) |
| SOH MAE | **5.18 percentage points** |
| SOH R-squared | 0.404 |
| SOH Training Batteries | 25 batteries (B0005–B0056, filtered) |
| SOH Test Batteries | 9 batteries — B0029, B0033, B0038, B0042, B0044, B0047, B0049, B0050, B0055 |
| SOH Training Rows | ~835,000 timestep-level rows |
| RUL CV MAE | ~46 cycles |
| RUL Training Batteries | 38 batteries (B0005–B0056) |
| RUL Features | 20-dimensional cycle-level vector |
| End-of-Life Threshold | SOH = 70% |
| AI Assistant | GPT-4o-mini + n8n + local fallback |
| Backend | FastAPI + SQLAlchemy + SQLite |
| Frontend | React + Recharts |
| Deployment | Docker + AWS EC2 + NGINX + HTTPS |
| CI/CD | GitHub Actions |
| IaC | Terraform |
| SOH Dataset | All 38 NASA ARC batteries (B0005–B0056), 6 batches |
| RUL Dataset | Same 38 NASA ARC batteries, cycle-level aggregation |
| Dataset Source | NASA Prognostics Center of Excellence (PCoE) |
