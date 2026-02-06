# DHRAM Design Specification

## Dundee Hydrological Regime Alteration Method

**Purpose:** This document provides a complete, implementation-ready specification of the DHRAM framework (Black et al., 2005). It is intended for developers who will implement DHRAM as part of the eflow package's alteration assessment pipeline.

**Reference:** Black, A.R., Rowan, J.S., Duck, R.W., Bragg, O.M. & Clelland, B.E. (2005). DHRAM: a method for classifying river flow regime alterations for the EC Water Framework Directive. *Aquatic Conservation: Marine and Freshwater Ecosystems*, 15, 427–446.

---

## 1. What DHRAM Does

DHRAM takes two daily flow time series — one representing **un-impacted (natural/reference)** conditions and one representing **impacted (altered)** conditions at the same site — and produces a single integer classification from **1** (un-impacted) to **5** (severely impacted). This classification is compatible with the EU Water Framework Directive's five-class ecological status scheme (High, Good, Moderate, Poor, Bad).

The method works by measuring how much the altered regime has deviated from the natural regime across all five IHA groups, then accumulating "impact points" based on the magnitude of those deviations.

---

## 2. Conceptual Overview

The pipeline has four stages:

1. **Compute IHA parameters** for each year, separately for the un-impacted and impacted time series.
2. **Summarise** those annual parameter values into 10 summary indicators (one for mean change and one for CV change per IHA group).
3. **Score** each summary indicator against deviation thresholds to accumulate impact points (0–30 possible).
4. **Classify** the total points into a DHRAM class (1–5), with possible adjustment from two yes/no supplementary questions.

---

## 3. Inputs

DHRAM requires exactly two inputs:

- **Un-impacted daily flow series:** A time series of daily mean discharge (m³/s) representing the natural or reference condition. This can be observed pre-impact data, synthetic modelled data, or data from an analogue catchment.
- **Impacted daily flow series:** A time series of daily mean discharge (m³/s) representing conditions after the anthropogenic impact (dam, abstraction, discharge, etc.). This can be observed post-impact data or synthetically generated.

Both series should ideally cover the **same time period** and span **at least 20 years** to minimize climate variability effects. If covering different periods, the method still works but results may be confounded by climatic differences between the two periods. Shorter records (down to ~13–15 years) have been used in practice but are less robust.

---

## 4. Stage 1 — Compute IHA Parameters Per Year

For each water year in both the un-impacted and impacted series, compute the standard 32 IHA descriptors. (The original DHRAM paper uses 32 parameters — the 33 standard IHA parameters minus zero-flow days. However, zero-flow days appear in the output tables but are **not included** in the impact points calculation.)

The 32 parameters are organized into 5 groups:

### Group 1: Magnitude of Monthly Water Conditions (12 parameters)

For each calendar month (January through December), compute the **mean daily flow** within that month for each year.

- Result: 12 values per year (one per month).

### Group 2: Magnitude and Duration of Annual Extremes (10 parameters)

For each year, compute rolling-window minima and maxima:

- **1-day minimum:** The single lowest daily flow value in the year.
- **3-day minimum:** The lowest value of the 3-day rolling mean in the year.
- **7-day minimum:** The lowest value of the 7-day rolling mean in the year.
- **30-day minimum:** The lowest value of the 30-day rolling mean in the year.
- **90-day minimum:** The lowest value of the 90-day rolling mean in the year.
- **1-day maximum:** The single highest daily flow value in the year.
- **3-day maximum:** The highest value of the 3-day rolling mean in the year.
- **7-day maximum:** The highest value of the 7-day rolling mean in the year.
- **30-day maximum:** The highest value of the 30-day rolling mean in the year.
- **90-day maximum:** The highest value of the 90-day rolling mean in the year.

The rolling mean for window size *k* at position *i* is the arithmetic mean of the *k* consecutive daily values ending at position *i*.

**Note on zero-flow days:** The number of zero-flow days per year is computed and reported but is **excluded from the impact points calculation**.

### Group 3: Timing of Annual Extremes (2 parameters)

For each year:

- **Date of 1-day minimum:** The Julian day (1–366) on which the annual minimum daily flow occurs.
- **Date of 1-day maximum:** The Julian day (1–366) on which the annual maximum daily flow occurs.

If multiple days share the same extreme value, use the first occurrence.

**Critical implementation detail for multi-year aggregation:** When computing mean and CV of Julian dates across years, the DHRAM paper uses **circular statistics** to handle the December–January wraparound correctly. For the mean:

- Convert each Julian date DOY to an angle: θ = 2π × DOY / 365.25
- Compute x̄ = mean(cos(θ)) and ȳ = mean(sin(θ))
- Mean DOY = atan2(ȳ, x̄) × 365.25 / (2π), adjusted to be positive

For the CV of timing, the DHRAM paper reports CV as a percentage. The circular dispersion should be converted to an equivalent CV. In the original DHRAM case studies, the CV values for timing are reported in percentage terms directly on the Julian day values, which suggests the implementation uses a simpler linear approach for CV (treating DOY values directly). Follow the convention used in your IHA computation module — just ensure consistency between un-impacted and impacted calculations.

### Group 4: Frequency and Duration of High and Low Pulses (4 parameters)

First, define pulse thresholds from the **un-impacted** flow record:

- **Low pulse threshold:** The 25th percentile of the entire un-impacted daily flow series.
- **High pulse threshold:** The 75th percentile of the entire un-impacted daily flow series.

Then, for each year in **both** the un-impacted and impacted series, using the thresholds derived from the un-impacted record:

- **Annual number of low pulses:** Count the number of distinct events where flow drops below the low threshold. An "event" starts when flow transitions from above-threshold to below-threshold, and ends when flow returns above-threshold.
- **Mean duration of low pulses:** The arithmetic mean of the durations (in days) of all low pulse events in that year. If there are no events, assign 0.
- **Annual number of high pulses:** Count the number of distinct events where flow rises above the high threshold.
- **Mean duration of high pulses:** The arithmetic mean of the durations (in days) of all high pulse events in that year. If there are no events, assign 0.

**Important:** The DHRAM paper (Table 1) lists these as "mean duration" not "median duration." This differs from some IHA implementations that use the median. For DHRAM, use the **mean** duration to match the original method.

### Group 5: Rate and Frequency of Change in Conditions (3 parameters)

For each year:

- **Mean daily flow increase (rise rate):** Compute day-to-day differences ΔQ[i] = Q[i] − Q[i−1]. Take the **mean** of all positive ΔQ values. (Note: the DHRAM paper uses "mean" for rise/fall rates, not "median" as in some other IHA implementations.)
- **Mean daily flow decrease (fall rate):** Take the **mean** of the absolute values of all negative ΔQ values. Report as a positive number.
- **Number of rises:** Count the number of days where ΔQ > 0. (Note: the DHRAM paper uses "number of rises" and "number of falls" rather than "number of reversals." The paper's Group 5 lists three parameters: mean increase, mean decrease, and number of rises.)

**Critical difference from standard IHA:** The original DHRAM paper's Group 5 contains "Number of rises" and "Number of falls" as separate items in Table 1 (4 items listed), but the scoring examples in Tables 5 and 6 show only 3 parameters being used: mean increase, mean decrease, and number of rises. Follow the 3-parameter convention from the scoring tables for implementation.

---

## 5. Stage 2 — Compute the 10 Summary Indicators

Once you have the 32 IHA parameter values for each year in both the un-impacted and impacted records, proceed as follows.

### Step 2a: Compute inter-annual mean and CV for each parameter

For each of the 32 parameters, across all years:

- **Mean_natural:** The arithmetic mean of that parameter across all years of the un-impacted record.
- **CV_natural:** The coefficient of variation (standard deviation / mean × 100) of that parameter across all years of the un-impacted record.
- **Mean_impacted:** Same for the impacted record.
- **CV_impacted:** Same for the impacted record.

### Step 2b: Compute absolute percentage change for each parameter

For each parameter:

- **Absolute % change in mean** = |Mean_impacted − Mean_natural| / Mean_natural × 100
- **Absolute % change in CV** = |CV_impacted − CV_natural| / CV_natural × 100

Note: These are absolute percentage changes — always non-negative.

**Edge case — timing parameters:** For the timing parameters (Group 3), the percentage change in mean should account for the circular nature of dates. The DHRAM paper reports this as a percentage of the year. In the Megget case study, a shift from Julian day 198 to Julian day 26 is reported as a 47.1% change (i.e., 172 days / 365.25 × 100 ≈ 47.1%). So the formula for timing mean change is:

- Compute the circular distance between the two mean dates (the shorter arc around the year).
- Express as: circular_distance_days / 365.25 × 100

**Edge case — zero or near-zero denominators:** If Mean_natural or CV_natural is zero or very close to zero, the percentage change formula breaks. Options:

- If both natural and impacted are zero, the change is 0%.
- If natural is zero but impacted is non-zero, treat as 100% change or cap at a maximum.
- Document the chosen convention and handle gracefully.

### Step 2c: Average within each IHA group to get 10 summary indicators

For each IHA group (1 through 5), compute:

- **Summary indicator Xa (group mean change):** The arithmetic mean of all "absolute % change in mean" values for all parameters in that group.
- **Summary indicator Xb (group CV change):** The arithmetic mean of all "absolute % change in CV" values for all parameters in that group.

This produces exactly 10 summary indicators:

| Indicator | Description |
|-----------|-------------|
| 1a | Average absolute % change in means for Group 1 (12 monthly flow parameters) |
| 1b | Average absolute % change in CVs for Group 1 |
| 2a | Average absolute % change in means for Group 2 (10 extreme magnitude parameters) |
| 2b | Average absolute % change in CVs for Group 2 |
| 3a | Average absolute % change in means for Group 3 (2 timing parameters) |
| 3b | Average absolute % change in CVs for Group 3 |
| 4a | Average absolute % change in means for Group 4 (4 pulse parameters) |
| 4b | Average absolute % change in CVs for Group 4 |
| 5a | Average absolute % change in means for Group 5 (3 rate-of-change parameters) |
| 5b | Average absolute % change in CVs for Group 5 |

---

## 6. Stage 3 — Assign Impact Points

Each of the 10 summary indicators is scored against **three thresholds** to accumulate 0–3 impact points per indicator. The maximum total is 30 points.

### Threshold Table

These thresholds were empirically derived by Black et al. (2005) using 20 natural Scottish catchments (to establish the lower threshold from modelling errors) and 11 impacted catchments (to establish the upper benchmark):

| Summary Indicator | Lower Threshold (1 point) | Intermediate Threshold (2 points) | Upper Threshold (3 points) |
|---|---|---|---|
| **1a** — Group 1 means | 19.9% | 43.7% | 67.5% |
| **1b** — Group 1 CVs | 29.4% | 97.6% | 165.7% |
| **2a** — Group 2 means | 42.9% | 88.2% | 133.4% |
| **2b** — Group 2 CVs | 84.5% | 122.7% | 160.8% |
| **3a** — Group 3 means | 7.0% | 21.2% | 35.5% |
| **3b** — Group 3 CVs | 33.4% | 50.3% | 67.3% |
| **4a** — Group 4 means | 36.4% | 65.1% | 93.8% |
| **4b** — Group 4 CVs | 30.5% | 76.1% | 121.6% |
| **5a** — Group 5 means | 46.0% | 82.7% | 119.4% |
| **5b** — Group 5 CVs | 49.1% | 79.9% | 110.6% |

### Scoring Rule

For each summary indicator value *V* and its three thresholds (lower *L*, intermediate *M*, upper *U*):

- If V < L → 0 points
- If L ≤ V < M → 1 point
- If M ≤ V < U → 2 points
- If V ≥ U → 3 points

Sum the points across all 10 summary indicators. This gives the **total impact points** (range: 0–30).

### How the thresholds were derived (for context, not implementation)

The lower threshold for each indicator was set at the mean plus one standard deviation of the modelling errors observed when applying the method to 20 essentially natural (un-impacted) Scottish catchments. This represents the level of "change" you'd see purely from modelling noise — anything below this is indistinguishable from error.

The upper threshold was set at the maximum observed value of that indicator across 11 known-impacted Scottish catchments. The two intermediate thresholds were then obtained by dividing the range between lower and upper into three equal intervals.

These thresholds are **fixed constants** in the DHRAM method. They are not re-derived per study.

---

## 7. Stage 4 — Classify into DHRAM Classes

### Preliminary Classification

Map the total impact points to a preliminary DHRAM class:

| Total Points | Preliminary Class | Description | WFD Equivalent |
|---|---|---|---|
| 0 | Class 1 | Un-impacted condition | High |
| 1–4 | Class 2 | Low risk of impact | Good |
| 5–10 | Class 3 | Moderate risk of impact | Moderate |
| 11–20 | Class 4 | High risk of impact | Poor |
| 21–30 | Class 5 | Severely impacted condition | Bad |

### Supplementary Questions (Optional Downgrade)

Two additional yes/no questions can each cause the classification to be **dropped by one class** (i.e., made worse by one level):

1. **Sub-daily flow oscillations:** Do anthropogenic sub-daily flow variations exceed 25% of the un-impacted 95% exceedance flow? If YES → drop one class.

2. **Flow cessation:** Do the anthropogenic impact(s) cause flow cessation (zero flow where naturally there would be flow)? If YES → drop one class.

The maximum class is 5 — it cannot go beyond 5 even if both questions apply.

**Implementation note:** These two questions require information **outside** of the daily mean flow data (sub-daily patterns and knowledge of whether zero flows are anthropogenic). In an automated implementation:

- Question 1 typically requires sub-daily flow data or operational knowledge of the scheme (e.g., hydropeaking). If this information is unavailable, the question is skipped (answered "No").
- Question 2 can be partially automated: if the impacted series contains zero-flow days but the un-impacted series does not, this is strong evidence of anthropogenic flow cessation.

### Final Classification

Final DHRAM Class = min(Preliminary Class + Q1_adjustment + Q2_adjustment, 5)

Where each adjustment is 1 if the answer is "Yes" and 0 if "No."

---

## 8. Worked Example — Interpreting the Output

To make the scoring concrete, here is a walkthrough based on the Megget Water case study from the original paper (a supply reservoir in Scotland, 13 years of data):

**Summary indicator values computed:**

| Indicator | Value (%) | Points |
|---|---|---|
| 1a (Group 1 means) | 21.7 | 1 |
| 1b (Group 1 CVs) | 39.8 | 1 |
| 2a (Group 2 means) | 31.0 | 0 |
| 2b (Group 2 CVs) | 124.0 | 2 |
| 3a (Group 3 means) | 30.9 | 2 |
| 3b (Group 3 CVs) | 17.6 | 0 |
| 4a (Group 4 means) | 46.3 | 1 |
| 4b (Group 4 CVs) | 22.7 | 0 |
| 5a (Group 5 means) | 34.2 | 0 |
| 5b (Group 5 CVs) | 41.4 | 0 |

**Total points:** 7 → **Preliminary Class 3** (Moderate risk)

No flow cessation, no significant sub-daily oscillation → **Final Class 3**.

Interpretation: The reservoir has moderately altered the flow regime. The biggest impacts are on the variability of extreme flows (2b = 124%, scoring 2 points) and the timing shift of annual extremes (3a = 30.9%, scoring 2 points — the annual minimum shifted from mid-summer to mid-winter).

---

## 9. Important Design Decisions and Edge Cases

### 9.1 Mean vs. Median in IHA Computation

The DHRAM paper consistently uses **mean** for all IHA parameter computations (monthly mean flow, mean rise rate, mean pulse duration). This differs from some modern IHA implementations that prefer medians. For DHRAM, use means throughout to match the original method.

### 9.2 Number of Parameters per Group

Ensure the correct count of parameters being averaged into each summary indicator:

- Group 1: 12 parameters (monthly means)
- Group 2: 10 parameters (5 min windows + 5 max windows; zero-flow days excluded)
- Group 3: 2 parameters (date of min, date of max)
- Group 4: 4 parameters (low count, low duration, high count, high duration)
- Group 5: 3 parameters (mean increase, mean decrease, number of rises)

Total: 31 parameters contributing to scoring (or 32 if "number of falls" is included in Group 5 — the paper is slightly ambiguous here; Tables 5 and 6 show 3 Group 5 parameters).

### 9.3 Pulse Thresholds

The DHRAM paper uses the 25th and 75th percentile thresholds (IQR convention) from the Richter et al. (1996) IHA method. These thresholds are computed from the entire un-impacted daily flow record (not per-year), and then applied to both the un-impacted and impacted records for pulse detection.

### 9.4 Water Year vs. Calendar Year

The DHRAM paper does not mandate a specific year type. It processes "each year of record." For consistency with the rest of the eflow package, use whatever year type (calendar or water year) is configured by the user. Just ensure the same year definition is used for both series.

### 9.5 Unequal Record Lengths

Ideally both series cover the same number of years and the same time period. If they differ in length, compute the IHA statistics independently for each series using all available years, then proceed with the comparison. The paper explicitly notes that using different time periods opens up the possibility of climate variability confounding results.

### 9.6 The "Simplified" DHRAM (without empirical thresholds)

Some implementations in the literature use a simplified version of DHRAM with uniform deviation thresholds rather than the empirically-derived ones from Table 3. This simplified version uses:

- 0 points: < 10% deviation
- 1 point: 10–30% deviation
- 2 points: 30–50% deviation
- 3 points: > 50% deviation

This is a common simplification seen in the broader literature and in the specification document for this project. It is computationally simpler but does **not** match the original DHRAM paper. The original thresholds vary per indicator because different IHA groups naturally exhibit different levels of modelling noise and sensitivity.

**Recommendation:** Implement both variants. Use the original empirical thresholds as the default, and offer the simplified uniform thresholds as an option. Clearly label which is being used.

---

## 10. Output Specification

The DHRAM computation should return a structured result containing:

### 10.1 Detailed Per-Parameter Results

For each of the 32 IHA parameters:
- Parameter name and group membership
- Un-impacted multi-year mean
- Un-impacted multi-year CV (%)
- Impacted multi-year mean
- Impacted multi-year CV (%)
- Absolute % change in mean
- Absolute % change in CV

### 10.2 Summary Indicators

For each of the 10 summary indicators (1a through 5b):
- Summary indicator value (%)
- Impact points assigned (0–3)
- Which threshold tier was triggered

### 10.3 Classification

- Total impact points (0–30)
- Preliminary DHRAM class (1–5)
- Sub-daily oscillation flag (boolean) and its adjustment (0 or 1)
- Flow cessation flag (boolean) and its adjustment (0 or 1)
- Final DHRAM class (1–5)
- WFD-equivalent status label (High / Good / Moderate / Poor / Bad)

### 10.4 Metadata

- Number of years analysed (un-impacted)
- Number of years analysed (impacted)
- Start and end years for each series
- Year type used (calendar / water year)
- Threshold variant used (original empirical / simplified uniform)

---

## 11. Relationship to Other Alteration Indices

DHRAM and IARI serve complementary roles:

- **DHRAM** produces a categorical classification (1–5) based on deviation thresholds. It is designed for regulatory screening — quickly identifying which sites need further ecological investigation. Its output maps directly to WFD status classes.

- **IARI** produces a continuous score (0 to unbounded, with 0 = no alteration) based on how far altered parameter values fall outside the natural interquartile range. It provides more granular, continuous information about the degree of alteration.

- **Ecodeficit/Ecosurplus** (Vogel et al., 2007) provides a complementary FDC-based perspective. Gao et al. (2009) demonstrated that total seasonal ecochange, summer ecosurplus, and winter ecosurplus are the most effective generalized indicators for representing the variability captured by the full set of 32 IHA parameters. DHRAM scores showed weaker correlation with the full IHA suite than these eco-flow statistics in empirical datasets (R²-adj = 0.540 for DHRAM vs. 0.807 for total seasonal ecochange across 189 US dams).

All three should be computed and reported together to give users both a regulatory classification and continuous alteration metrics.

---

## 12. Summary Flowchart

```
Daily flow (natural) ──┐
                       ├──▶ Compute 32 IHA params per year (each series)
Daily flow (altered) ──┘
                              │
                              ▼
                  Multi-year mean & CV per parameter (each series)
                              │
                              ▼
                  Absolute % change in mean & CV per parameter
                              │
                              ▼
                  Average within each IHA group → 10 summary indicators
                              │
                              ▼
                  Score each indicator against thresholds → 0-3 points each
                              │
                              ▼
                  Sum points (0–30) → Preliminary class (1–5)
                              │
                              ▼
                  Apply supplementary questions → Final class (1–5)
```

---

## References

- Black, A.R., Rowan, J.S., Duck, R.W., Bragg, O.M. & Clelland, B.E. (2005). DHRAM: a method for classifying river flow regime alterations for the EC Water Framework Directive. *Aquatic Conservation: Marine and Freshwater Ecosystems*, 15, 427–446.
- Gao, Y., Vogel, R.M., Kroll, C.N., Poff, N.L. & Olden, J.D. (2009). Development of representative indicators of hydrologic alteration. *Journal of Hydrology*, 374, 136–147.
- Richter, B.D., Baumgartner, J.V., Powell, J. & Braun, D.P. (1996). A method for assessing hydrologic alteration within ecosystems. *Conservation Biology*, 10(4), 1163–1174.
- Vogel, R.M., Sieber, J., Archfield, S.A., Smith, M.P., Apse, C.D. & Huber-Lee, A. (2007). Relations among storage, yield and instream flow. *Water Resources Research*, 43.
