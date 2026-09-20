# Flow diagnostic sources

Diagnostic scores describe hydrological alteration. They do not certify biological status, scientific suitability or legal compliance.

## Verified sources

- The Nature Conservancy, *Indicators of Hydrologic Alteration*, version 7.1, April 2009. [Official manual](https://www.conservationgateway.org/content/dam/tnc/conservation/cg-documents/i/n/indicators-of-hydrologic-alteration-iha.pdf). SHA-256 `512aabc7455ec153a2394ebf372ab29b8b1f7fb27f46421ae7698ad70b448841`.
- ISPRA, *Implementazione della Direttiva 2000/60/CE. Analisi e valutazione degli aspetti idromorfologici*, version 1.1, August 2011. [Official original](https://www.isprambiente.gov.it/contentfiles/00010100/10147-analisi-e-valutazione-degli-aspetti-idromorfologici-agosto-2011.pdf). SHA-256 `102ad6211f55f9f9cc54d1a5253705efc9a0df9af85956470b35feaa670922d1`.
- Greco, Michele; Arbia, Francesco; Giampietro, Raffaele (2021). *Definition of Ecological Flow Using IHA and IARI as an Operative Procedure for Water Management*. Environments 8(8), 77. [DOI](https://doi.org/10.3390/environments8080077). Supplied PDF SHA-256 `ed4e0cee87b1ec1797d57f82034dab2d770564a7353be8b9af435ad26413b398`.

Original papers and report material are not redistributed. The cited Richter et al. (1996) paper has not been verified in full; the official manual supplies the IHA definition coverage below.

## Definition register

| Operation | Definition source | Convention |
|---|---|---|
| 33 annual IHA parameters | Manual §2.2 pp6–9, Table1 | Groups contain 12, 12, 2, 4, 3 parameters. Parametric means and nonparametric medians are separate profiles. Rolling averages are always arithmetic means. |
| Duration extrema | Manual p6 | Every complete 1-,3-,7-,30-,90-day window wholly within the selected year; no wrap or crossing-year window. |
| Zero days and baseflow index | Manual Table1 p8 | Exact zero count; seven-day minimum divided by annual mean. Zero annual mean leaves the ratio undefined. |
| Extreme date | Manual p6 | Earliest date in a tie. |
| Leap/calendar timing | Manual §5.3 pp61–62 | Fixed 366-position calendar: nonleap March1 is day61 and December31 day366. Leap observations remain present. |
| Pulses | Manual §2.2 pp6–7 | Strictly below/above thresholds. Two-period thresholds come from reference only. Runs belong to their start year and include their following-year duration. A run at the first dataset day is excluded; a terminal run is truncated and disclosed. |
| Rise, fall, reversal | Manual Table1 p9 and p7 | Positive/negative consecutive differences; unchanged flow does not end a trend. First change of each year is not a reversal. |
| Interannual timing | Manual §5.3 pp62–64 | Quarterly-bin unwrap, not trigonometric circular mean. Timing CV uses SD/366. Dominant-quarter ties are not defined by the manual. |
| Percentiles | Manual §5.2 p61 | IMSL named without routine/version/formula. No unverified estimator can claim exact IMSL equivalence. |
| Daily IARI | ISPRA §1.4.4.2.1 pp8–14, eqs1–2, Table1.2 | Reference at least20 years; current parameter mean/median from last five years; distance outside closed q25–q75 band divided by IQR. Overall arithmetic mean of all33 scores, not equal weighting of five groups. |
| Monthly IARI | ISPRA §1.4.4.2.2 pp15–16, eqs4–5 | Twelve monthly-mean discharge parameters; last-five-year mean/median or single assessment year. Single-year final index receives basin twelve-month SPI correction. Not a proxy for daily IHA. |
| IARI zero IQR | ISPRA eq1 | Exact equality is inside the band and scores zero. Outside a collapsed band has no supplied finite operator. |
| IARI classification | ISPRA Table1.4 p18 | <=0.05 high; >0.05 and <=0.15 good; >0.15 not-good. Prose Phase2 triggers conflict at0.15 and require separate treatment. |

## Unresolved source interpretations

Greco Table6 is not an exact numerical oracle: displayed July q25=1.00, q75=1.77, candidate=0.58 give0.54545 by its equation, not the printed0.13. The displayed monthly data imply an average around0.122264, not the reported0.05. Independent equation tests must not reproduce these inconsistencies.

## Approved omission

DHRAM is omitted, including supplied-summary scoring, under the
[approved diagnostic scope revision](https://github.com/hydrosolutions/taqsim/blob/13d4b00b4dd4105312fc141cc3db53f69763fa71/planning/visions/2026-09-20-fishy-assessment-foundation.md).
The supplied Black et al. (2005) paper was read and its tables visually checked:
Table1 lists32 descriptors while worked Tables5–6 score31. Historical timing
dispersion and general zero-denominator rules remained insufficiently specified.
The original2000 SNIFFER manual SR(00)01/2F was identified, but no readable copy
was obtained. This is not a claim that the2005 paper was unavailable or that no
manual copy exists. Research and experimental tests remain in historical Git
through`0b64901` and local source evidence, not as a supported feature. No author
contact or undocumented interpretation is required for this delivery.

- Black, A. R.; Rowan, J. S.; Duck, R. W.; Bragg, O. M.; Clelland, B. E. (2005). *DHRAM: a method for classifying river flow regime alterations for the EC Water Framework Directive*. Aquatic Conservation 15, 427–446. [DOI](https://doi.org/10.1002/aqc.707). Supplied PDF SHA-256 `8ea9d281675cdd488bc463c451b309fc25f036d66e73d66a09584293db5e5d44`.
