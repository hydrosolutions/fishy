"""Appendix A4 exact area operators and explicit suitability limitations."""

from dataclasses import replace
from fractions import Fraction

import pytest
from test_hydrological_condition import context

from fishy.hydrological_transfer import (
    CatchmentCharacteristic,
    Characteristic,
    HydrologicalValue,
    SpecificDischarge,
    Suitability,
    TransferQualification,
    TransferSetting,
    estimate_specific_discharge,
    extrapolate_discharge,
    interpolate_discharge,
    transfer_area_independent,
)
from fishy.quantities import Area

Q = TransferQualification(
    TransferSetting.SAME_WATERCOURSE,
    Suitability.SUITABLE,
    Suitability.SUITABLE,
    "no karst influence in synthetic case",
    "prepared similarity study",
)


def donor(name, area, value, kind=Characteristic.MEAN_FLOW, unit="m3/s"):
    return CatchmentCharacteristic(context(name), Area(area, "km2"), HydrologicalValue(kind, value, unit), Q)


def test_one_and_two_upstream_linear_interpolation():
    ctx = context("target")
    output = interpolate_discharge(ctx, Area(20, "km2"), (donor("up", 10, 2),), donor("down", 30, 8))
    assert output.value is not None
    assert output.value.value == 5
    assert output.weights == (Fraction(1, 2), Fraction(1, 2))
    output = interpolate_discharge(
        ctx,
        Area(40, "km2"),
        (
            replace(donor("up1", 15, 2), catchment_units=("west",)),
            replace(donor("up2", 15, 4), catchment_units=("east",)),
        ),
        donor("down", 60, 12),
    )
    assert output.value is not None
    assert output.value.value == 8
    assert len(output.donors) == 3


def test_one_two_donor_extrapolation_and_mhq_exponent():
    ctx = context("target")
    a = replace(donor("a", 20, 5), catchment_units=("west",))
    b = replace(donor("b", 30, 10), catchment_units=("east",))
    output = extrapolate_discharge(ctx, Area(40, "km2"), (a, b))
    assert output.value is not None
    assert output.value.value == 12
    single = extrapolate_discharge(ctx, Area(40, "km2"), (a,))
    assert single.value is not None
    assert single.value.value == 10
    flood = replace(a, value=HydrologicalValue(Characteristic.FLOOD_INSTANTANEOUS, 5, "m3/s"))
    output = extrapolate_discharge(ctx, Area(40, "km2"), (flood,))
    assert output.value is not None
    assert float(output.value.value) == pytest.approx(5 * 2**0.7, rel=1e-12)
    assert output.value is not None
    assert output.value.characteristic is Characteristic.FLOOD_INSTANTANEOUS
    assert "binary64" in output.reasons[0]


def test_area_independent_weights_not_inverse_distance():
    ds = tuple(
        donor(n, a, v, Characteristic.FLOOD_FREQUENCY, "events/year")
        for n, a, v in (("a", 15, 1), ("b", 30, 3), ("c", 40, 7))
    )
    output = transfer_area_independent(context("target"), Area(20, "km2"), ds)
    assert output.weights == (Fraction(3, 7), Fraction(5, 14), Fraction(3, 14))
    assert output.value is not None
    assert output.value.value == 3
    single = transfer_area_independent(context("target"), Area(20, "km2"), (ds[0],))
    assert single.value is not None
    assert single.value.value == 1
    equal = tuple(replace(d, area=Area(20, "km2")) for d in ds)
    assert transfer_area_independent(context("target"), Area(20, "km2"), equal).value is None


def test_specific_discharge_estimate_and_missing_qualification():
    specific = SpecificDischarge(Characteristic.LOW_FLOW, 2, "supplied similar catchment")
    output = estimate_specific_discharge(context(), Area(50, "km2"), specific, Q)
    assert output.value is not None
    assert output.value.value == Fraction(1, 10)
    limited = replace(Q, hydrological_similarity=Suitability.UNRESOLVED)
    assert estimate_specific_discharge(context(), Area(50, "km2"), specific, limited).value is None


def test_invalid_versus_unsupported_transfer():
    a = donor("a", 10, 5)
    assert extrapolate_discharge(context(), Area(100, "km2"), (a,)).value is None
    unsupported = replace(a, qualification=replace(Q, no_significant_intervening_change=Suitability.UNSUITABLE))
    assert extrapolate_discharge(context(), Area(20, "km2"), (unsupported,)).value is None
    with pytest.raises(ValueError, match="duplicate"):
        extrapolate_discharge(context(), Area(20, "km2"), (a, a))
    mismatch = replace(a, context=replace(a.context, provenance=replace(a.context.provenance, scenario="other")))
    with pytest.raises(ValueError, match="same reference"):
        extrapolate_discharge(context(), Area(20, "km2"), (mismatch,))
    with pytest.raises(ValueError, match="unit"):
        HydrologicalValue(Characteristic.LOW_FLOW, 5, "l/s")
    with pytest.raises(ValueError, match="area-dependent"):
        transfer_area_independent(context(), Area(20, "km2"), (a,))


def test_two_donor_sum_requires_independent_catchment_evidence():
    # Distinct gauge names do not establish that their catchments are disjoint.
    a = donor("a", 20, 5)
    b = donor("b", 30, 10)
    assert extrapolate_discharge(context("target"), Area(40, "km2"), (a, b)).value is None


def test_nested_transfer_catchments_are_not_summed():
    a = replace(donor("a", 20, 5), catchment_units=("upstream",))
    b = replace(donor("b", 30, 10), catchment_units=("upstream", "increment"))
    with pytest.raises(ValueError, match="nested/overlapping"):
        extrapolate_discharge(context("target"), Area(40, "km2"), (a, b))


@pytest.mark.parametrize("side", ["donor", "target", "specific"])
@pytest.mark.parametrize("restriction", ["missing", "warmup"])
def test_transfer_cannot_promote_missing_or_excluded_source(side, restriction):
    from fishy.evidence import CorrectionState

    ctx = context("target")
    source = donor("source", 20, 5)
    changed = ctx if side != "donor" else source.context
    prov = (
        replace(changed.provenance, correction_state=CorrectionState.MISSING)
        if restriction == "missing"
        else replace(changed.provenance, excluded_warmup=(changed.period,))
    )
    changed = replace(changed, provenance=prov)
    if side == "specific":
        output = estimate_specific_discharge(
            changed, Area(40, "km2"), SpecificDischarge(Characteristic.LOW_FLOW, 2, "study"), Q
        )
    elif side == "donor":
        output = extrapolate_discharge(ctx, Area(40, "km2"), (replace(source, context=changed),))
    else:
        output = extrapolate_discharge(changed, Area(40, "km2"), (source,))
    assert output.value is None
    assert output.reasons
