# Feature Request: E-Flow Indices & Ecological Status Assessment Package

**Date:** 2026-02-04
**Priority:** Medium
**Requested by:** Bea

---

## Overview

This feature request outlines indices to be implemented in a **new standalone package** for ecological river assessment. The package will:

1. Calculate hydrological and water quality indices according to **multiple regulatory frameworks**
2. Be integrated into **Taqsim** (river basin management & optimization tool)
3. Support assessment of **individual river stretches** (e.g., rapid multi-framework impact assessment for hydropower projects)
4. Provide comparable outputs across different national/regional standards

**Note:** Taqsim API specification will be defined separately by the Taqsim development team.

---

## Priority 1: Hydrological Indices (E-Flow Assessment)

**Data requirement:** Daily discharge time series only

### 1.1 IHA (Indicators of Hydrologic Alteration) - 33 Parameters

The foundational framework from [The Nature Conservancy](https://www.conservationgateway.org/ConservationPractices/Freshwater/EnvironmentalFlows/MethodsandTools/IndicatorsofhydrologicAlteration/Pages/indicators-hydrologic-alt.aspx). [Software Manual v7.1 (PDF)](https://www.conservationgateway.org/Documents/IHAV7.pdf)

| Group | Focus | Parameters |
|-------|-------|------------|
| **1** | Magnitude of monthly water conditions | 12 monthly means/medians |
| **2** | Magnitude & duration of annual extremes | 1,3,7,30,90-day min/max + baseflow index + zero-flow days (12 total) |
| **3** | Timing of annual extremes | Julian date of annual min & max (2) |
| **4** | Frequency & duration of high/low pulses | Pulse count & duration for high/low (4) |
| **5** | Rate & frequency of change | Rise rate, fall rate, reversals (3) |

**Total: 33 parameters**

### 1.2 DHRAM Classification (WFD Mapping)

Maps IHA metrics to WFD-compatible 5-class system. [Black et al. (2005)](https://onlinelibrary.wiley.com/doi/abs/10.1002/aqc.707)

**Method:**
1. Calculate mean and CV for each of 5 IHA groups → 10 categories
2. Compute % deviation from reference conditions
3. Assign impact points (0-3) per category based on thresholds
4. Sum → max 30 points → map to WFD class

| Score | WFD Class | Status |
|-------|-----------|--------|
| 0 | High | No alteration |
| 1-4 | Good | Low risk |
| 5-10 | Moderate | Moderate risk |
| 11-20 | Poor | High risk |
| 21-30 | Bad | Severely impacted |

---

## Priority 2: Thermal Regime Indices

**Data requirement:** Daily water temperature time series (or estimated via Air2Stream from air temp + discharge)

Critical for assessing dam release impacts and protecting endemic Central Asian species (Amu Darya sturgeon, snow trout).

### 2.1 Thermal Metrics (28 metrics, IHA-parallel structure)

Following [StreamThermal (USGS)](https://github.com/tsangyp/StreamThermal):

| Group | Count | Metrics | Ecological Relevance |
|-------|-------|---------|----------------------|
| **1** Magnitude | 13 | Monthly mean temps (12) + annual mean | Seasonal habitat suitability |
| **2** Extremes | 6 | MWAT (7-day max), 7-day min, annual max/min, annual range, diel range | Stress/lethal thresholds |
| **3** Timing | 2 | Julian day of annual max/min | Life cycle alignment |
| **4** Duration | 5 | Days above/below thresholds, max consecutive stress days, stress event count | Chronic stress |
| **5** Rate | 2 | Spring warming rate (°C/day), max hourly change | Thermal shock (dam releases) |

### 2.2 Key Thermal Indices

| Index | Description | Critical Threshold |
|-------|-------------|-------------------|
| **MWAT** | Maximum Weekly Average Temperature (7-day max) | Species-specific (see below) |
| **Thermal shock rate** | Max °C/hour change | >2°C/hr = shock risk |
| **Stress duration** | Consecutive days above threshold | Species-specific |

### 2.3 Central Asian Fish Thermal Guilds

| Species | Common Name | Optimal (°C) | Stress (°C) | Lethal (°C) |
|---------|-------------|--------------|-------------|-------------|
| *Pseudoscaphirhynchus kaufmannii* | Amu Darya sturgeon | 10-20 | >22 | >25 |
| *Schizothorax* spp. | Snow trout | 8-18 | >20 | >24 |
| *Cyprinus carpio* | Common carp | 18-28 | >30 | >34 |
| *Silurus glanis* | Wels catfish | 16-28 | >30 | >34 |

### 2.4 Temperature Estimation (Air2Stream)

For data-sparse regions, estimate water temperature from air temperature + discharge:

```
T_water(t) = a₁ + a₂·T_air + a₃·T_air·e^(-Q/a₄) + a₅·cos(2π·t/365 - a₆)
```

**Accuracy:** RMSE ~1.0°C with 1-2 years calibration data

**Reference:** [Toffolon & Piccolroaz (2015)](https://github.com/marcotoffolon/air2stream)

---

## Priority 3: ICWC/IFAS Transboundary Framework

**Critical for Central Asian regulatory acceptance.** The Interstate Commission for Water Coordination (ICWC) and International Fund for Saving the Aral Sea (IFAS) are the primary regulatory mechanisms for Amu Darya and Syr Darya management.

### 3.1 ICWC Water Allocation Framework

| River | Annual Allocation | Ecological Minimum | Key Constraint |
|-------|-------------------|-------------------|----------------|
| Amu Darya | ~62 km³ | 27 km³/yr to Aral Sea delta | Biota reserve release |
| Syr Darya | ~37 km³ | Variable by season | Northern Aral Sea restoration |

### 3.2 IFAS Ecological Requirements

**Aral Sea Restoration Targets:**
- Minimum flow to Northern Aral Sea (Syr Darya): Maintained via Kok-Aral Dam
- Minimum flow to Amu Darya delta wetlands: Critical for biodiversity
- Salinity targets for delta ecosystems

### 3.3 Transboundary Coordination Requirements

| Aspect | Requirement |
|--------|-------------|
| **Data sharing** | Results must be reproducible/auditable for transboundary negotiations |
| **Upstream compatibility** | Indices should align with Tajik/Kyrgyz national standards |
| **Transparency** | Open-source methodology eliminates "black box" accusations |

**TODO:** Document specific ICWC minimum flow requirements per reach and season.

---

## Priority 4: Water Quality Indices (CIS Standards)

### 4.1 IZV (Uzbekistan) - Индекс Загрязнения Воды

**Formula:**
```
IZV = (1/n) × Σ(Ci / PDKi)
```

| IZV Score | Class | Description |
|-----------|-------|-------------|
| ≤0.3 | I | Very Clean |
| 0.3-1.0 | II | Clean |
| 1.0-2.5 | III | Moderately Polluted |
| 2.5-4.0 | IV | Polluted |
| 4.0-6.0 | V | Dirty |
| 6.0-10.0 | VI | Very Dirty |
| >10.0 | VII | Extremely Dirty |

**Parameters:** 6 mandatory (to be confirmed)

**Status:** ⏳ **AWAITING MINISTRY FEEDBACK** on current PDK values and mandatory parameter list.
- Contacted: Uzbek Ministry of Ecology / Oyture / Committee
- Reference baseline: Госкомгидромет СССР (1988), SanPiN standards
- Need: Current (2020+) Uzbekistan PDK values for implementation

### 4.2 UKIZV (Kazakhstan/Russia) - Удельный Комбинаторный Индекс

More comprehensive than IZV. Per [РД 52.24.643-2002](https://meganorm.ru/Data2/1/4293831/4293831806.htm).

**Method:**
1. For each parameter: Sα (frequency score) × Sβ (intensity score) = Si
2. KIZV = Σ Si (combinatorial index)
3. UKIZV = KIZV / N (specific combinatorial index)

| UKIZV | Class | Description |
|-------|-------|-------------|
| <1 | 1 | Conditionally clean |
| 1-2 | 2 | Slightly polluted |
| 2-4 | 3 | Polluted / Very polluted |
| 4-11 | 4 | Dirty (subclasses a-d) |
| >11 | 5 | Extremely dirty |

**Critical Pollution Indicators (КПЗ):** Parameters with Sα ≥ 2 AND Sβ ≥ 3 are flagged.

### 4.3 FAO IWQI (Irrigation Water Quality Index)

Critical for Amu Darya / Syr Darya irrigation contexts.

**Formula:**
```
IWQI = Σ(wi × qi)
```

| Parameter | Weight | Excellent (100) | Unsuitable (0) |
|-----------|--------|-----------------|----------------|
| EC (µS/cm) | 0.211 | <700 | >3000 |
| SAR | 0.189 | <3 | >9 |
| Na (meq/L) | 0.204 | <3 | >9 |
| Cl (meq/L) | 0.194 | <4 | >10 |
| HCO3 (meq/L) | 0.202 | <1.5 | >8.5 |

| Score | Class | Recommendation |
|-------|-------|----------------|
| 85-100 | Excellent | No restrictions |
| 70-84 | Good | Minor restrictions |
| 55-69 | Moderate | Sensitive crops affected |
| 40-54 | Poor | Tolerant crops only (cotton, barley) |
| 0-39 | Unsuitable | Not recommended |

**Reference:** [FAO Irrigation and Drainage Paper 29](https://www.fao.org/3/T0234E/T0234E00.htm)

---

## Priority 5: EU WFD & Switzerland

### 5.1 EU WFD Assessment

The EU WFD does **not prescribe specific hydrological indices**. Each member state develops their own methods. Since DHRAM (Section 1.2) already maps IHA → WFD classes, this provides WFD-compatible output.

**For hydrological regime**, the WFD requires assessment of:
- Quantity and dynamics of flow
- Connection to groundwaters

Reference: [Hydrological Regime Alteration Assessment in the Context of WFD](https://www.mdpi.com/2071-1050/15/22/15704)

### 5.2 Switzerland (Modul-Stufen-Konzept)

Switzerland uses its own national framework ([BAFU Modular Stepwise Procedure](https://www.bafu.admin.ch/bafu/en/home/topics/water/state-of-watercourses/modular-stepwise-procedure.html)).

**Structure:**
- **Level F:** Comprehensive surveys with minimal effort
- **Level S:** Detailed investigation of selected systems

**TODO:** Research specific hydrological indices from [Swiss hydrology module (PDF)](https://modul-stufen-konzept.ch/wp-content/uploads/2020/12/Modul_Hydrologie_DE-1.pdf).

---

## Summary: Implementation Phases

| Phase | Component | Data Required | Status |
|-------|-----------|---------------|--------|
| **1** | IHA (33 parameters) | Daily Q | Core |
| **1** | DHRAM (WFD classification) | IHA output | Core |
| **2** | Thermal metrics (28) | Daily T (or estimated) | High |
| **2** | Air2Stream (T estimation) | Daily Q + air T | High |
| **3** | ICWC/IFAS minimum flows | Reach definitions | High |
| **4** | IZV (Uzbekistan) | WQ samples | ⏳ Awaiting PDK values |
| **4** | UKIZV (Kazakhstan/Russia) | WQ samples | Medium |
| **4** | FAO IWQI + SAR | Ion chemistry | Medium |
| **5** | Switzerland hydrology module | Daily Q | Lower |

---

## Open Questions

1. **IZV PDK values:** ⏳ Awaiting Ministry of Ecology feedback on current Uzbekistan standards
2. **ICWC minimum flows:** Document specific requirements per reach and season
3. **Swiss hydrology module:** Extract specific indices from BAFU documentation
4. **UKIZV scoring matrices:** Need complete Sα/Sβ tables from РД 52.24.643-2002
5. **Reference conditions:** How to establish natural baseline for DHRAM in heavily regulated rivers?

---

## Key References

### Hydrological
- [IHA Manual v7.1 (TNC)](https://www.conservationgateway.org/Documents/IHAV7.pdf)
- [DHRAM - Black et al. (2005)](https://onlinelibrary.wiley.com/doi/abs/10.1002/aqc.707)

### Thermal
- [StreamThermal (USGS)](https://github.com/tsangyp/StreamThermal)
- [Air2Stream](https://github.com/marcotoffolon/air2stream)

### Transboundary (ICWC/IFAS)
- [ICWC Official Portal](http://www.icwc-aral.uz/)
- [IFAS Executive Committee](http://ec-ifas.waterunites-ca.org/)

### Water Quality (CIS)
- [РД 52.24.643-2002 (UKIZV)](https://meganorm.ru/Data2/1/4293831/4293831806.htm)
- [Uzbekistan wastewater standards overview (UNECE 2024)](https://unece.org/sites/default/files/2024-04/2.%20wastewater%20standards%20overview_Viacheslav%20Shi-Syan_Engl%20%28automatic%29.pdf)
- [FAO Irrigation and Drainage Paper 29](https://www.fao.org/3/T0234E/T0234E00.htm)

### EU WFD & Switzerland
- [WFD Ecological Status Portal](https://water.europa.eu/freshwater/europe-freshwater/water-framework-directive/ecological-status-of-surface-water)
- [BAFU Modular Stepwise Procedure](https://www.bafu.admin.ch/bafu/en/home/topics/water/state-of-watercourses/modular-stepwise-procedure.html)
- [Swiss hydrology module (PDF)](https://modul-stufen-konzept.ch/wp-content/uploads/2020/12/Modul_Hydrologie_DE-1.pdf)

---

**Integration Target:** Taqsim River Basin Management Tool (API to be defined by Taqsim team)
**Primary Use Case:** Rapid multi-framework impact assessment for hydropower and water management projects
