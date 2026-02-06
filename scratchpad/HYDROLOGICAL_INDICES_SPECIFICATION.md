# Hydrological Indices Technical Specification

## Document Purpose

Technical reference for implementing hydrological indices for environmental flow assessment. Contains index definitions, mathematical formulas, and interpretation guidelines.

---

## Table of Contents

1. [IHA Framework (33 Parameters)](#1-iha-framework-33-parameters)
2. [Extended IHA Metrics](#2-extended-iha-metrics)
3. [Flow Duration Curve Indices](#3-flow-duration-curve-indices)
4. [Baseflow Indices](#4-baseflow-indices)
5. [Recession Analysis Indices](#5-recession-analysis-indices)
6. [Seasonality Indices](#6-seasonality-indices)
7. [Variability Indices](#7-variability-indices)
8. [Aggregate Alteration Indices](#8-aggregate-alteration-indices)
9. [USGS Extended Statistics (171 HIT Indices)](#9-usgs-extended-statistics)
10. [Index Selection Guidance](#10-index-selection-guidance)

---

## 1. IHA Framework (33 Parameters)

The Indicators of Hydrologic Alteration (IHA) framework (Richter et al., 1996) defines 33 parameters across 5 groups characterizing ecologically relevant flow regime components.

### 1.1 Group 1: Magnitude of Monthly Water Conditions (12 parameters)

**Parameters:** Monthly mean (or median) discharge for each calendar month.

| Parameter | Definition |
|-----------|------------|
| MA_jan through MA_dec | Central tendency of daily flows within each month |

**Formula:**

```
MA_month = median(Q_daily | month)
```

or

```
MA_month = mean(Q_daily | month)
```

**Computation:**

1. Extract all daily flows for each calendar month across all years
2. Compute median (preferred) or mean for each month
3. Result: 12 values representing typical monthly flow magnitude

**Interpretation:** Characterizes seasonal water availability. Alterations indicate shifts in water supply timing affecting habitat, species life cycles, and riparian vegetation.

---

### 1.2 Group 2: Magnitude and Duration of Annual Extremes (12 parameters)

**Parameters:** Annual minimum and maximum flows at multiple temporal scales.

| Parameter | Definition | Formula |
|-----------|------------|---------|
| 1-day min | Annual minimum daily flow | `min(Q_daily)` per year |
| 3-day min | Annual minimum 3-day average | `min(rolling_mean(Q, 3))` per year |
| 7-day min | Annual minimum 7-day average | `min(rolling_mean(Q, 7))` per year |
| 30-day min | Annual minimum 30-day average | `min(rolling_mean(Q, 30))` per year |
| 90-day min | Annual minimum 90-day average | `min(rolling_mean(Q, 90))` per year |
| 1-day max | Annual maximum daily flow | `max(Q_daily)` per year |
| 3-day max | Annual maximum 3-day average | `max(rolling_mean(Q, 3))` per year |
| 7-day max | Annual maximum 7-day average | `max(rolling_mean(Q, 7))` per year |
| 30-day max | Annual maximum 30-day average | `max(rolling_mean(Q, 30))` per year |
| 90-day max | Annual maximum 90-day average | `max(rolling_mean(Q, 90))` per year |
| Zero-flow days | Days with Q below threshold per year | `count(Q < threshold)` per year |
| Base flow index | 7-day min / annual mean | `min(rolling_mean(Q, 7)) / mean(Q_annual)` |

**Rolling Mean Formula:**

```
rolling_mean(Q, k)[i] = (1/k) * Σ(Q[i-k+1 : i])
```

**Interpretation:**

- Minimum flows indicate drought severity and groundwater contribution
- Maximum flows indicate flood magnitude and disturbance intensity
- Multiple window sizes capture different ecological response timescales
- Zero-flow days critical for intermittent/ephemeral systems
- Zero-flow threshold: Default 0.001 m³/s (configurable); accounts for measurement noise

---

### 1.3 Group 3: Timing of Annual Extremes (2 parameters)

**Parameters:** Julian day (1-366) when annual extremes occur.

| Parameter | Definition |
|-----------|------------|
| Date of annual minimum | Day of year when minimum flow occurs |
| Date of annual maximum | Day of year when maximum flow occurs |

**Formula:**

```
DOY_min = day_of_year(argmin(Q_daily | year))
DOY_max = day_of_year(argmax(Q_daily | year))
```

**Handling Multiple Extremes:** If multiple days share the same extreme value, use:

- First occurrence, or
- Mean of all occurrence dates (ceiling)

**Circular Statistics for Multi-Year Aggregation:**

```
θ = 2π × DOY / 365.25
x = mean(cos(θ))
y = mean(sin(θ))
DOY_mean = atan2(y, x) × 365.25 / (2π)
```

**Implementation Note:**

- EflowStats (USGS): Uses circular statistics (proper for aggregating across years)
- sarawater: Uses linear day-of-year (does not account for year-wrap)

Circular statistics are preferred when computing multi-year mean timing to handle December-January transitions correctly.

**Interpretation:** Timing shifts indicate altered seasonal patterns affecting spawning cues, migration triggers, and phenological synchronization.

---

### 1.4 Group 4: Frequency and Duration of High/Low Pulses (4 parameters)

**Parameters:** Pulse events defined by exceedance of percentile thresholds.

| Parameter | Definition |
|-----------|------------|
| Low pulse count | Number of events where Q drops below threshold |
| Low pulse duration | Median duration (days) of low pulse events |
| High pulse count | Number of events where Q exceeds threshold |
| High pulse duration | Median duration (days) of high pulse events |

**Threshold Definitions:**

Two conventions exist in the literature:

| Convention | Low Threshold | High Threshold | Used By |
|------------|---------------|----------------|---------|
| IQR-based (default) | 25th percentile | 75th percentile | sarawater, jasonelaw_iha, USGS EflowStats |
| Extreme-based | 10th percentile | 90th percentile | icra_IHA, TNC IHA software |

**Important:** Thresholds should be computed from the **natural** (unaltered) flow record, not the altered flow. The altered flow is then compared against these natural thresholds to detect pulses.

**Percentile Computation:**

- Use Weibull plotting position (type 6) for consistency with hydrological conventions
- Alternative: Linear interpolation (type 7, NumPy/R default)

**Pulse Detection Algorithm:**

```python
def count_pulses(Q, threshold, direction='below'):
    if direction == 'below':
        in_pulse = Q < threshold
    else:
        in_pulse = Q > threshold

    # Count transitions into pulse state
    pulse_starts = sum((in_pulse[1:] == True) & (in_pulse[:-1] == False))
    return pulse_starts

def pulse_durations(Q, threshold, direction='below'):
    # Identify pulse periods using run-length encoding
    # Return list of consecutive day counts for each pulse event
```

**Formula for Duration:**

```
Low_pulse_duration = median(lengths of all low pulse events)
High_pulse_duration = median(lengths of all high pulse events)
```

**Interpretation:**

- Pulse count indicates disturbance frequency
- Pulse duration indicates stress persistence
- Low pulses: habitat disconnection, stranding risk
- High pulses: scouring, nutrient flushing, floodplain connectivity

---

### 1.5 Group 5: Rate and Frequency of Flow Changes (3 parameters)

**Parameters:** Day-to-day flow variability characteristics.

| Parameter | Definition | Formula |
|-----------|------------|---------|
| Rise rate | Central tendency of positive daily changes | `median(ΔQ | ΔQ > 0)` |
| Fall rate | Central tendency of negative daily changes | `median(ΔQ | ΔQ < 0)` |
| Number of reversals | Count of flow direction changes | See below |

**Daily Change:**

```
ΔQ[i] = Q[i] - Q[i-1]
```

**Rise/Fall Rate:**

```
Rise_rate = median(ΔQ where ΔQ > 0)
Fall_rate = median(ΔQ where ΔQ < 0)  # Negative value (sarawater convention)
```

**Sign Convention:**

- sarawater: Reports fall rate as negative (preserves sign)
- Some implementations: Report absolute value (|fall_rate|)
- Recommendation: Document which convention is used

**Reversal Count Algorithm:**

```python
def count_reversals(Q):
    dQ = diff(Q)
    # Classify each change: -1 = fall, 0 = no change, +1 = rise
    direction = sign(dQ)

    # Count transitions between rising and falling
    reversals = sum(direction[1:] != direction[:-1])
    return reversals
```

Alternative (run-length encoding):

```
reversals = len(monotonic_segments) - 1
```

**Interpretation:**

- Rapid rise/fall rates stress organisms through velocity changes
- High reversal counts indicate unnatural flow fluctuations (hydropeaking)
- Natural systems show gradual changes; altered systems show abrupt shifts

---

## 2. Extended IHA Metrics

### 2.1 Environmental Flow Components (EFC) - 34 Additional Parameters

The full IHA software (v7) includes 34 EFC parameters characterizing:

**Extreme Low Flows:**

- Peak (minimum value during event)
- Duration (days)
- Timing (start date)
- Frequency (events per year)

**Low Flows:**

- Same 4 metrics as extreme low flows

**High Flow Pulses:**

- Peak, duration, timing, frequency, rise rate, fall rate

**Small Floods:**

- Peak, duration, timing, frequency, rise rate, fall rate

**Large Floods:**

- Peak, duration, timing, frequency, rise rate, fall rate

**Threshold Definitions for EFC:**

- Extreme low flow: Below 10th percentile
- Low flow: 10th-50th percentile, decreasing
- High flow pulse: Above 75th percentile
- Small flood: 2-year return interval
- Large flood: 10-year return interval

---

### 2.2 Colwell's Predictability Indices

From information theory (Colwell, 1974), used in USGS EflowStats.

**Constancy (C):**

```
C = 1 - H(Y) / log(s)

where:
  H(Y) = -Σ (Y_j/Z) × log(Y_j/Z)  [entropy of state distribution]
  Y_j = column sum (total observations in state j)
  Z = total observations
  s = number of states (typically 11 flow categories)
```

**Contingency (M):**

```
M = (H(X) + H(Y) - H(XY)) / log(s)

where:
  H(X) = entropy of time (rows)
  H(XY) = joint entropy
```

**Predictability (P):**

```
P = C + M
```

**Flow State Categories (11 classes):**
Boundaries at: 0.1, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25 × log(mean flow)

**Interpretation:**

- C near 1: Flow is constant (same state throughout year)
- M high: Flow is variable but predictable (seasonal pattern)
- P high: Overall predictability (constant or seasonally patterned)

---

## 3. Flow Duration Curve Indices

### 3.1 Flow Duration Curve (FDC)

**Definition:** Cumulative frequency curve showing percentage of time flow is equaled or exceeded.

**Construction:**

```python
def flow_duration_curve(Q):
    Q_sorted = sort(Q, descending=True)
    n = len(Q)
    exceedance = [(i + 1) / (n + 1) * 100 for i in range(n)]
    return exceedance, Q_sorted
```

### 3.2 FDC Slope

**Formula:**

```
FDC_slope = (log(Q_upper) - log(Q_lower)) / (P_upper - P_lower)

Default: P_upper = 33, P_lower = 66 (mid-range slope)
```

Where Q_upper and Q_lower are flows at exceedance probabilities P_upper and P_lower.

**Interpretation:**

- Steep slope: Flashy, variable flows
- Flat slope: Stable, baseflow-dominated
- Typical range: 0.5-3.0 for natural streams

### 3.3 Ecodeficit and Ecosurplus (Vogel et al., 2007)

**Definition:** Dimensionless measures of flow alteration based on FDC comparison.

**Ecodeficit:**

```
Ecodeficit = Area(FDC_natural - FDC_altered) / Area(FDC_natural)
             where FDC_natural > FDC_altered
```

**Ecosurplus:**

```
Ecosurplus = Area(FDC_altered - FDC_natural) / Area(FDC_natural)
             where FDC_altered > FDC_natural
```

**Seasonal Variants:**

- Spring ecodeficit/ecosurplus (Mar-Jun)
- Summer ecodeficit/ecosurplus (Jul-Oct)
- Winter ecodeficit/ecosurplus (Nov-Feb)

**Total Seasonal Ecochange:**

```
Total_ecochange = Σ(seasonal_ecodeficits) + Σ(seasonal_ecosurpluses)
```

**Interpretation:**

- Ecodeficit > 0: Flow reduction (water withdrawal impact)
- Ecosurplus > 0: Flow augmentation (reservoir releases)
- Values typically 0-1; larger indicates greater alteration

---

## 4. Baseflow Indices

### 4.1 Baseflow Index (BFI)

**Definition:** Ratio of baseflow to total streamflow, indicating groundwater contribution.

**Two distinct BFI definitions exist:**

**BFI_IHA (Group 2, Parameter 12):**

```
BFI_IHA = min(rolling_mean(Q, 7)) / mean(Q_annual)
```

The ratio of the minimum 7-day moving average to the annual mean flow. Used in IHA 33 parameters (Richter et al., 1996).

**BFI_LH (Digital Filter Method):**

```
BFI_LH = Σ(Q_baseflow) / Σ(Q_total)
```

The ratio of filtered baseflow volume to total volume, where Q_baseflow is obtained via Lyne-Hollick or similar digital filter.

**Important:** These are different metrics with different ranges and interpretations:

- BFI_IHA typically ranges 0.1-0.5
- BFI_LH typically ranges 0.3-0.9

**Note:** sarawater uses annual mean flow as "base_flow" (not a filtered baseflow), which differs from both definitions above.

**Range:** 0 to 1 (typically 0.1-0.9 for natural streams with BFI_LH)

### 4.2 Lyne-Hollick Digital Filter

**Algorithm (Ladson et al., 2013):**

Forward pass:

```
q_f[0] = Q[0]
q_f[i] = α × q_f[i-1] + ((1 + α) / 2) × (Q[i] - Q[i-1])
Q_b[i] = Q[i] - q_f[i]  if q_f[i] > 0, else Q[i]
```

Backward pass (reverse direction, same formula)

**Parameters:**

- α (filter parameter): Default 0.925
- n_passes: Default 1 (TOSSH, hydrosignatures); some implementations use 3
- pad_width: 10 days to handle edge effects (optional)

**Note:** The number of passes varies by implementation:

- TOSSH, hydrosignatures: n_passes = 1 (default)
- Some Australian studies: n_passes = 3 (forward-backward-forward)
- EflowStats (USGS): Uses different baseflow separation methods

**Interpretation:**

- BFI < 0.2: Surface runoff dominated
- BFI 0.2-0.5: Mixed regime
- BFI > 0.5: Groundwater dominated
- BFI > 0.8: Strong baseflow contribution

### 4.3 UKIH Method (UK Institute of Hydrology)

**Algorithm:**

1. Divide record into 5-day non-overlapping blocks
2. Find minimum flow in each block
3. If 0.9 × block_min[i] < minimum of adjacent blocks, assign as baseflow turning point
4. Connect turning points; interpolate between
5. Baseflow = area under interpolated curve

### 4.4 Baseflow Recession Constant (K)

**Exponential Recession Model:**

```
Q(t) = Q_0 × exp(-K × t)
```

**Linear Regression in Log Space:**

```
ln(Q) = ln(Q_0) - K × t
K = -slope
```

**Interpretation (Safeeq et al., 2013):**

- K < 0.065 day⁻¹: Groundwater-dominated, slow-draining
- K ≥ 0.065 day⁻¹: Shallow subsurface flow, fast-draining

---

## 5. Recession Analysis Indices

### 5.1 Power-Law Recession Parameters

**Model:**

```
-dQ/dt = a × Q^b
```

**Log-Linear Form:**

```
log(-dQ/dt) = log(a) + b × log(Q)
```

**Parameters:**

- a: Scaling coefficient [mm/timestep^(2-b)]
- b: Non-linearity parameter [-]
  - b = 1: Linear reservoir (exponential recession)
  - b = 2: Quadratic reservoir
  - b > 2: Highly non-linear storage-discharge

### 5.2 Master Recession Curve (MRC)

**Construction (Matching Strip Method):**

1. Identify individual recession segments (monotonically decreasing periods)
2. Sort segments by starting flow (descending)
3. Shift segments horizontally to align overlapping flow ranges
4. Fit composite curve through aligned segments

**Recession Segment Detection:**

```python
def detect_recessions(Q, min_length=15, eps=0):
    """
    min_length: Minimum recession duration (days)
    eps: Allowed daily increase during recession (handles noise)
    """
    dQ = diff(Q)
    in_recession = dQ <= eps
    # Find consecutive recession periods >= min_length
```

### 5.3 MRC Slope Changes

**Multi-Segment Analysis:**

- 1-segment: Single exponential (homogeneous aquifer)
- 2-segment: Two slopes (dual reservoir)
- 3-segment: Three slopes (complex hydrogeology)

**Interpretation:**

- First segment (steep): Rapid depletion from fast stores
- Mid segment: Intermediate storage
- Late segment (flat): Deep groundwater contribution

### 5.4 Recession Uniqueness (Spearman's ρ)

**Formula:**

```
ρ = rank_correlation(Q, -dQ/dt)
```

**Interpretation:**

- ρ near 1: Unique storage-discharge relationship (deterministic)
- ρ near 0: Scattered relationship (multiple flow paths, hysteresis)

---

## 6. Seasonality Indices

### 6.1 Walsh and Lawler Seasonality Index (1981)

**Formula:**

```
SI = (1 / Q_annual) × Σ|Q_month - Q_annual/12|
```

**Interpretation:**

- SI ≈ 0: Uniform flow throughout year
- SI ≈ 1: Highly seasonal (concentrated in few months)
- Typical range: 0.1-0.8

### 6.2 Markham Seasonality Index (1970)

**Circular Statistics Approach:**

Monthly phase angles:

```
Φ = [15.8°, 44.9°, 74.0°, 104.1°, 134.1°, 164.2°,
     194.3°, 224.9°, 255.0°, 285.0°, 315.1°, 345.2°]
```

**Vector Components:**

```
S = Σ(Q_month × sin(Φ_month))
C = Σ(Q_month × cos(Φ_month))
```

**Results:**

```
Magnitude = √(S² + C²)
Angle = atan2(S, C)  [peak timing]
SI = Magnitude / Σ(Q_month) × 12
```

### 6.3 Half-Flow Date (HFD)

**Definition:** Day of year when 50% of annual discharge has passed.

**Formula:**

```
HFD = min(d) such that Σ(Q[1:d]) ≥ 0.5 × Σ(Q_annual)
```

**Interpretation:**

- Early HFD: Front-loaded hydrology (snowmelt, monsoon)
- Late HFD: Delayed runoff (groundwater, regulated)
- Typical range: 90-270 days from water year start

### 6.4 Half-Flow Interval (HFI)

**Definition:** Duration between 25% and 75% cumulative discharge dates.

**Formula:**

```
HFI = DOY_75% - DOY_25%
```

**Interpretation:**

- Short HFI: Concentrated flow period
- Long HFI: Distributed flow throughout year

---

## 7. Variability Indices

### 7.1 Coefficient of Variation (CV)

**Formula:**

```
CV = σ / μ × 100%

where:
  σ = standard deviation
  μ = mean
```

**Applications:**

- Daily CV: Overall flow variability
- Monthly CV: Seasonal variability
- Annual CV: Inter-annual variability
- Log-space CV: For skewed distributions

### 7.2 Flashiness Index (Richards-Baker)

**Standard Formula (Baker et al., 2004; TOSSH):**

```
FI = Σ|Q[i] - Q[i-1]| / Σ Q
```

**Alternative Formula (hydrosignatures):**

```
FI_alt = mean(|Q[i] - Q[i-1]| / Q[i])
```

**Warning:** These formulas produce different values. The standard Baker formula (sum of differences / sum of flows) is more widely used. The alternative normalizes each difference by instantaneous flow before averaging.

**Interpretation (standard formula):**

- FI ≈ 0: Stable flows
- FI > 0.5: Highly flashy
- Typical range: 0.05-0.5

### 7.3 Variability Index (TOSSH)

**Formula:**

```
VI = std(log₁₀(Q_percentiles))

where percentiles = [10%, 20%, ..., 90%]
```

### 7.4 Range Ratios

**Inter-percentile Ratios:**

```
Q90/Q10 = 90th percentile / 10th percentile
Q75/Q25 = 75th percentile / 25th percentile
```

**Interpretation:**

- High ratios indicate high variability
- Q90/Q10 > 10: Highly variable
- Q90/Q10 < 3: Low variability

### 7.5 Autocorrelation (AR1)

**Formula:**

```
AR(1) = Σ((Q[i] - μ)(Q[i-1] - μ)) / Σ(Q[i] - μ)²
```

**Interpretation:**

- AR(1) near 1: High persistence (slow-responding system)
- AR(1) near 0: Low persistence (flashy system)
- Typical range: 0.7-0.99 for daily streamflow

---

## 8. Aggregate Alteration Indices

### 8.1 DHRAM Score (Black et al., 2005)

**Dundee Hydrological Regime Alteration Method**

**Procedure:**

1. Calculate mean and CV for each IHA group (5 groups × 2 statistics = 10 categories)
2. Compute % deviation from natural reference for each category
3. Assign impact points (0-3) based on deviation thresholds:
   - 0 points: < 10% deviation
   - 1 point: 10-30% deviation
   - 2 points: 30-50% deviation
   - 3 points: > 50% deviation
4. Sum points across all 10 categories (max = 30)

**DHRAM Classification:**

| Score | Class | Status |
|-------|-------|--------|
| 0 | 1 (High) | No alteration |
| 1-4 | 2 (Good) | Low risk |
| 5-10 | 3 (Moderate) | Moderate risk |
| 11-20 | 4 (Poor) | High risk |
| 21-30 | 5 (Bad) | Severely impacted |

### 8.2 IARI (Index of Alteration of River Index)

**From SARAwater package**

**Per-Parameter Score:**

```
If Q25 ≤ X_altered ≤ Q75 (natural):
    p = 0
Else:
    p = min(|X - Q25|, |X - Q75|) / (Q75 - Q25)
```

**Group IARI:**

```
IARI_group = mean(p) for all parameters in group
```

**Aggregated IARI:**

```
IARI = Σ(w_j × IARI_group_j)

Default weights: w = 0.2 for each of 5 groups
```

**Interpretation:**

- IARI = 0: Unaltered
- IARI > 0.15: Severe alteration threshold

### 8.3 Normalized IHA Index

**Per-Parameter Score:**

```
p = |X_altered / mean(X_natural) - 1|
```

**With Zero Handling:**

```
if |mean(X_natural)| < ε:
    p = |(X_altered + 1) / (mean(X_natural) + 1) - 1|
```

**Interpretation:** Direct percentage deviation from natural baseline.

---

## 9. USGS Extended Statistics

### 9.1 Overview

The USGS Hydrologic Index Tool (HIT) calculates 171 indices across 11 categories, plus 7 "Magnificent Seven" (MAG7) indices.

### 9.2 Magnitude Indices Summary

**Average (MA1-MA45):**

- MA1-MA5: Basic statistics (mean, median, CV, skewness)
- MA6-MA11: Range ratios (percentile spreads)
- MA12-MA23: Monthly means
- MA24-MA35: Monthly CVs
- MA36-MA45: Annual statistics

**Low (ML1-ML22):**

- ML1-ML12: Monthly minima
- ML13: CV of monthly minima
- ML14-ML16: Annual minimum ratios
- ML17-ML20: Baseflow indices
- ML21-ML22: Annual minimum variability

**High (MH1-MH27):**

- MH1-MH12: Monthly maxima
- MH13-MH14: Maximum variability
- MH15-MH17: Exceedance ratios
- MH18-MH20: Maximum statistics
- MH21-MH27: High flow volume/peak indices

### 9.3 Duration Indices Summary

**Low (DL1-DL20):**

- DL1-DL5: Annual minimum n-day averages (1, 3, 7, 30, 90)
- DL6-DL10: Variability of above
- DL11-DL15: Normalized low flows
- DL16-DL17: Low pulse duration
- DL18-DL20: Zero-flow statistics

**High (DH1-DH24):**

- DH1-DH5: Annual maximum n-day averages
- DH6-DH10: Variability of above
- DH11-DH13: Normalized high flows
- DH14-DH21: High flow duration at various thresholds
- DH22-DH24: Flood duration statistics

### 9.4 Frequency Indices Summary

**Low (FL1-FL3):**

- FL1: Low pulse count
- FL2: Low pulse count variability
- FL3: Extreme low frequency (< 5% mean)

**High (FH1-FH11):**

- FH1-FH2: High pulse count and variability
- FH3-FH4: Days above 3×, 7× median
- FH5-FH10: Flood frequency at various thresholds
- FH11: 1.67-year flood frequency

### 9.5 Timing Indices Summary

**Average (TA1-TA3):**

- TA1: Constancy (Colwell)
- TA2: Predictability (Colwell)
- TA3: Seasonal flood predictability

**Low (TL1-TL4):**

- TL1-TL2: Julian date of minimum (mean, variability)
- TL3-TL4: Seasonal predictability

**High (TH1-TH3):**

- TH1-TH2: Julian date of maximum (mean, variability)
- TH3: Flood-free period predictability

### 9.6 Rate of Change Indices (RA1-RA9)

- RA1-RA2: Rise rate and variability
- RA3-RA4: Fall rate and variability
- RA5: Proportion of rising days
- RA6-RA7: Log-space rise/fall rates
- RA8-RA9: Reversals and variability

### 9.7 Magnificent Seven (MAG7)

**L-moment based indices (Archfield et al., 2013):**

| Index | Description | Formula |
|-------|-------------|---------|
| Lam1 | Mean flow | L-moment λ₁ |
| Tau2 | L-CV | λ₂/λ₁ |
| Tau3 | L-skewness | λ₃/λ₂ |
| Tau4 | L-kurtosis | λ₄/λ₂ |
| AR(1) | Autocorrelation | Lag-1 correlation |
| Amplitude | Seasonal amplitude | Sine fit amplitude |
| Phase | Seasonal timing | Sine fit phase (days) |

---

## 10. Index Selection Guidance

### 10.1 Minimal Set (6 ERHIs - Yang et al., 2008)

For rapid assessment:

1. Date of minimum
2. Rise rate
3. Number of reversals
4. 3-day maximum
5. 7-day minimum
6. May flow

### 10.2 Representative Set (Gao et al., 2009)

Best overall alteration indicators:

1. **Total seasonal ecochange** (strongest correlation with full IHA)
2. **Summer ecosurplus**
3. **Winter ecosurplus**

### 10.3 Process-Based Selection (McMillan, 2020)

**For groundwater-dominated systems:**

- BFI, BaseflowRecessionK, StorageFraction, RecessionParameters

**For surface-runoff dominated systems:**

- FlashinessIndex, FDC_slope, RisingLimbDensity, PeakDistribution

### 10.4 Recommended Tier Structure

**Tier 1 (Core - Always Compute):**

- Monthly means (12)
- 7-day min/max
- BFI
- FDC slope
- High/low pulse count and duration
- Rise rate, fall rate, reversals

**Tier 2 (Extended - When Data Permits):**

- Full IHA 33 parameters
- Seasonal ecodeficit/ecosurplus
- Recession constant K
- Seasonality index

**Tier 3 (Comprehensive - Research Applications):**

- Full USGS 171 indices
- Multi-segment recession analysis
- Storage-discharge relationships

---

## Appendix A: Data Requirements

| Index Category | Minimum Record Length | Temporal Resolution |
|----------------|----------------------|---------------------|
| Monthly statistics | 10 years | Daily |
| Annual extremes | 15 years | Daily |
| Pulse analysis | 10 years | Daily |
| Recession analysis | 5 years | Daily (sub-daily preferred) |
| Seasonality | 10 years | Daily |
| FDC indices | 10 years | Daily |

### Year Type

**Calendar Year:** January 1 - December 31 (sarawater default)

**Water Year:** Begins on first day of specified month (typically October 1 in Northern Hemisphere)

- US standard: October 1 - September 30
- Australian standard: July 1 - June 30

**Recommendation:** Use water year for snowmelt-dominated or monsoon-driven systems where the hydrologic cycle spans calendar year boundaries.

### Sub-daily Data Handling

If input data is sub-daily (e.g., hourly), aggregate to daily resolution before computing IHA indices:

```
Q_daily = mean(Q_subdaily) grouped by date
```

## Appendix B: Key References

### Core IHA References

1. Richter, B.D., et al. (1996). A method for assessing hydrologic alteration within ecosystems. Conservation Biology, 10(4), 1163-1174.

2. Poff, N.L., et al. (1997). The natural flow regime. BioScience, 47(11), 769-784.

3. Richter, B.D., et al. (1997). How much water does a river need? Freshwater Biology, 37, 231-249.

### Seasonality and Timing

1. Walsh, R.P.D., & Lawler, D.M. (1981). Rainfall seasonality: description, spatial patterns and change through time. Weather, 36, 201-208.

2. Markham, C.G. (1970). Seasonality of precipitation in the United States. Annals of the Association of American Geographers, 60, 593-597.

3. Colwell, R.K. (1974). Predictability, constancy, and contingency of periodic phenomena. Ecology, 55, 1148-1153.

### Alteration Assessment

1. Black, A.R., et al. (2005). DHRAM: A method for classifying river flow regime alterations. Aquatic Conservation, 15, 427-446.

2. Gao, Y., et al. (2009). Development of representative indicators of hydrologic alteration. Journal of Hydrology, 374, 136-147.

3. Vogel, R.M., et al. (2007). Relations among storage, yield, and instream flow. Water Resources Research, 43.

### Baseflow and Recession

1. Ladson, A.R., et al. (2013). A standard approach to baseflow separation using the Lyne and Hollick filter. Australasian Journal of Water Resources, 17(1).

2. Safeeq, M., et al. (2013). Coupling snowpack and groundwater dynamics to interpret historical streamflow trends in the western United States. Hydrological Processes, 27, 655-668.

### Variability and Flashiness

1. Baker, D.B., et al. (2004). A new flashiness index: characteristics and applications to midwestern rivers and streams. Journal of the American Water Resources Association, 40, 503-522.

2. Olden, J.D. & Poff, N.L. (2003). Redundancy and the choice of hydrologic indices. River Research and Applications, 19, 101-121.

### Index Selection

1. Yang, T., et al. (2008). Identification of homogeneous regions in terms of flood seasonality using a multivariate approach. Hydrological Sciences Journal, 53, 1042-1055.

2. McMillan, H.K. (2020). Linking hydrologic signatures to hydrologic processes: A review. Hydrological Processes, 34, 2836-2857.

### Toolboxes and Software

1. Gnann, S.J., et al. (2021). TOSSH: A toolbox for streamflow signatures in hydrology. Environmental Modelling & Software, 138.

2. Henriksen, J.A., et al. (2006). A computer program for calculation of 171 hydrologic indices. USGS Open-File Report.

3. Archfield, S.A., et al. (2013). An objective and parsimonious approach for classifying natural flow regimes. River Research and Applications, 30, 1166-1183.
