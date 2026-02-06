# Hydrological Indices Formula Quick Reference

## IHA 33 Parameters - Implementation Formulas

### Group 1: Monthly Magnitude (12 indices)

```python
# For each month m in [1..12]:
MA[m] = median(Q[date.month == m])
```

---

### Group 2: Extreme Magnitude (12 indices)

```python
# Rolling window extremes
for k in [1, 3, 7, 30, 90]:
    Q_roll = rolling_mean(Q, window=k)
    min_k = min(Q_roll)  # per year
    max_k = max(Q_roll)  # per year

# Zero-flow days (configurable threshold, default 0.001 m³/s)
zero_days = sum(Q < zero_threshold)  # per year

# Base flow index
BFI = min(rolling_mean(Q, 7)) / mean(Q)  # per year
```

---

### Group 3: Timing (2 indices)

```python
# Julian date of extremes
DOY_min = day_of_year(Q.idxmin())  # per year
DOY_max = day_of_year(Q.idxmax())  # per year

# Multi-year circular mean
theta = 2 * pi * DOY / 365.25
DOY_mean = atan2(mean(sin(theta)), mean(cos(theta))) * 365.25 / (2 * pi)
```

---

### Group 4: Pulse Frequency/Duration (4 indices)

```python
# Thresholds (from NATURAL flow, not altered)
# Convention 1: IQR-based (sarawater, jasonelaw_iha, EflowStats)
Q_low = percentile(Q_natural, 25)
Q_high = percentile(Q_natural, 75)

# Convention 2: Extreme-based (icra_IHA, TNC)
# Q_low = percentile(Q_natural, 10)
# Q_high = percentile(Q_natural, 90)

# Pulse detection on ALTERED flow (per year)
low_events = detect_events(Q_altered < Q_low)
high_events = detect_events(Q_altered > Q_high)

low_count = len(low_events)
high_count = len(high_events)
low_duration = median([len(e) for e in low_events])  # 0 if no events
high_duration = median([len(e) for e in high_events])  # 0 if no events
```

---

### Group 5: Rate of Change (3 indices)

```python
dQ = diff(Q)

rise_rate = median(dQ[dQ >= 0])   # Non-negative changes
fall_rate = median(dQ[dQ <= 0])   # Non-positive changes (negative value)
# Note: sarawater preserves sign; some implementations use abs(fall_rate)

# Reversals (sarawater method)
reversals = sum(diff(signbit(dQ)))  # Count sign changes in dQ
```

---

## Flow Duration Curve Indices

```python
# FDC construction
Q_sorted = sort(Q, descending=True)
exceedance = arange(1, len(Q)+1) / (len(Q)+1) * 100

# FDC slope (33-66 percentile range)
Q_33 = percentile(Q, 67)  # 33% exceedance
Q_66 = percentile(Q, 34)  # 66% exceedance
FDC_slope = (log(Q_33) - log(Q_66)) / (66 - 33)

# Ecodeficit/Ecosurplus
area_natural = trapz(FDC_natural)
deficit_area = trapz(max(FDC_natural - FDC_altered, 0))
surplus_area = trapz(max(FDC_altered - FDC_natural, 0))
ecodeficit = deficit_area / area_natural
ecosurplus = surplus_area / area_natural
```

---

## Baseflow Indices

### Lyne-Hollick Filter

```python
def lyne_hollick(Q, alpha=0.925, n_passes=1):
    """
    n_passes: Default 1 (TOSSH, hydrosignatures); some use 3
    """
    Q_f = zeros_like(Q)
    for pass_i in range(n_passes):
        if pass_i % 2 == 0:  # forward
            for i in range(1, len(Q)):
                Q_f[i] = alpha * Q_f[i-1] + (1+alpha)/2 * (Q[i] - Q[i-1])
        else:  # backward
            for i in range(len(Q)-2, -1, -1):
                Q_f[i] = alpha * Q_f[i+1] + (1+alpha)/2 * (Q[i] - Q[i+1])
        Q_f = clip(Q_f, min=0)  # Quick flow must be non-negative
    Q_b = clip(Q - Q_f, 0, Q)  # Baseflow = total - quick
    return Q_b

# BFI from digital filter (BFI_LH)
BFI_LH = sum(Q_baseflow) / sum(Q_total)

# BFI from IHA Group 2 (BFI_IHA) - different metric!
BFI_IHA = min(rolling_mean(Q, 7)) / mean(Q_annual)
```

### Recession Constant

```python
def recession_constant(Q, recession_segments):
    """From log-linear regression on recession segments"""
    all_Q = []
    all_t = []
    for seg in recession_segments:
        all_Q.extend(seg)
        all_t.extend(range(len(seg)))

    # Linear regression in log space
    slope, intercept = linregress(all_t, log(all_Q))
    K = -slope  # units: 1/day
    return K
```

---

## Seasonality Indices

### Walsh-Lawler

```python
Q_annual = sum(Q_monthly)
SI = sum(abs(Q_monthly - Q_annual/12)) / Q_annual
```

### Markham

```python
# Monthly phase angles (degrees)
phi = [15.8, 44.9, 74.0, 104.1, 134.1, 164.2,
       194.3, 224.9, 255.0, 285.0, 315.1, 345.2]
phi_rad = [p * pi / 180 for p in phi]

S = sum(Q_monthly * sin(phi_rad))
C = sum(Q_monthly * cos(phi_rad))

magnitude = sqrt(S**2 + C**2)
angle = atan2(S, C) * 180 / pi
SI = magnitude / sum(Q_monthly) * 12
```

### Half-Flow Date

```python
Q_cumsum = cumsum(Q)
Q_half = sum(Q) / 2
HFD = argmax(Q_cumsum >= Q_half)  # day index
```

---

## Variability Indices

```python
# Coefficient of variation
CV = std(Q) / mean(Q) * 100

# Flashiness index (Baker et al., 2004 - standard)
FI = sum(abs(diff(Q))) / sum(Q)

# WARNING: hydrosignatures uses different formula:
# FI_alt = mean(abs(diff(Q)) / Q[1:])  # NOT equivalent!

# Autocorrelation (lag-1)
Q_demean = Q - mean(Q)
AR1 = sum(Q_demean[1:] * Q_demean[:-1]) / sum(Q_demean**2)
```

---

## Alteration Assessment

### DHRAM Score

```python
def dhram_points(natural_value, altered_value):
    deviation = abs(altered_value - natural_value) / natural_value * 100
    if deviation < 10:
        return 0
    elif deviation < 30:
        return 1
    elif deviation < 50:
        return 2
    else:
        return 3

# For each of 5 IHA groups, compute mean and CV
# Score = sum of points for all 10 metrics (max 30)
# Map to class: 0=High, 1-4=Good, 5-10=Moderate, 11-20=Poor, 21-30=Bad
```

### IARI

```python
def iari_parameter(x_altered, Q25_natural, Q75_natural):
    if Q25_natural <= x_altered <= Q75_natural:
        return 0
    else:
        return min(abs(x_altered - Q25_natural),
                   abs(x_altered - Q75_natural)) / (Q75_natural - Q25_natural)

# IARI = weighted mean across all parameters (default: equal weights per group)
```

---

## Recession Analysis

### Power-Law Parameters

```python
def recession_power_law(Q, dQdt):
    """
    Fit: -dQ/dt = a * Q^b
    """
    # Filter valid recession points
    mask = (dQdt < 0) & (Q > 0)
    Q_rec = Q[mask]
    dQdt_rec = -dQdt[mask]

    # Log-linear regression
    log_Q = log(Q_rec)
    log_dQdt = log(dQdt_rec)

    slope, intercept = linregress(log_Q, log_dQdt)

    b = slope      # non-linearity parameter
    a = exp(intercept)  # scaling parameter

    return a, b
```

### dQ/dt Calculation

```python
# Forward difference
dQdt = (Q[1:] - Q[:-1]) / dt

# Central difference (more accurate)
dQdt = (Q[2:] - Q[:-2]) / (2 * dt)

# ETS method (exponential time stepping)
dQdt = Q * (exp((log(Q[1:])-log(Q[:-1]))/dt) - 1)
```

---

## Data Structures

### Input Format

```python
# Minimal input
df = pd.DataFrame({
    'date': pd.DatetimeIndex,  # daily timestamps
    'Q': np.array,             # discharge (m³/s or mm/day)
})

# Optional
df['P'] = precipitation       # for runoff ratio, elasticity
df['T'] = temperature         # for snow indices
df['PET'] = potential_ET      # for aridity index
```

### Output Format

```python
# IHA results (per year)
iha_results = {
    'year': [2000, 2001, ...],
    'MA_jan': [...],
    'MA_feb': [...],
    # ... all 33 parameters
}

# Summary statistics
iha_summary = {
    'parameter': [...],
    'mean': [...],
    'median': [...],
    'cv': [...],
    'Q25': [...],
    'Q75': [...],
}
```

---

## Unit Conversions

```python
# m³/s to mm/day (for catchment)
Q_mm_day = Q_m3s * 86400 / (area_km2 * 1e6) * 1000

# L-moment estimation
# NOTE: Use established libraries (lmom R package, scipy.stats.mstats)
# The simplified formulas below are approximations only
from lmom import samlmu  # R: lmom::.samlmu()
L = samlmu(Q, nmom=4)
# L[0] = λ₁ (mean)
# L[1] = λ₂ (L-scale)
# L[2] = τ₃ (L-skewness = λ₃/λ₂)
# L[3] = τ₄ (L-kurtosis = λ₄/λ₂)
```

---

## Threshold Definitions Summary

| Threshold | Definition | Use |
|-----------|------------|-----|
| Q10 | 10th percentile | Low pulse (TNC/icra_IHA convention) |
| Q25 | 25th percentile | Low pulse (IQR convention - default) |
| Q50 | 50th percentile (median) | Central tendency |
| Q75 | 75th percentile | High pulse (IQR convention - default) |
| Q90 | 90th percentile | High pulse (TNC/icra_IHA convention) |
| Q95 | 95th percentile | Flood indicator |
| 3×median | 3 times median flow | Moderate flood |
| 7×median | 7 times median flow | Large flood |
| 1.67-yr flood | Return period threshold | Bankfull flow (USGS) |

**Percentile Method:** Use Weibull plotting position (type 6) for hydrological
consistency, or specify method explicitly (type 7 is NumPy/R default).

---

## Error Handling

```python
# Handle zero flows in log calculations
Q_safe = where(Q > 0, Q, 0.001 * min(Q[Q > 0]))

# Handle missing data
Q_clean = Q.dropna()
if len(Q_clean) < min_record_length:
    raise ValueError("Insufficient data")

# Handle all-zero years
if all(Q_year == 0):
    return np.nan  # Skip year

# Handle Q25 == Q75 in IARI (sarawater approach)
if Q75 == Q25:
    warn("Q25 equals Q75; IARI parameter set to 0")
    p_ik = 0
```

---

## Year Type Configuration

```python
# Calendar year (sarawater default)
years = [d.year for d in dates]

# Water year (October start, US convention)
def water_year(date, wy_month=10):
    return date.year if date.month < wy_month else date.year + 1
years = [water_year(d) for d in dates]
```
