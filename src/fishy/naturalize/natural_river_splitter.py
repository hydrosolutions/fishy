"""NaturalRiverSplitter - split rule for natural river bifurcations."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from fishy.naturalize.types import NATURAL_TAG

if TYPE_CHECKING:
    from taqsim.node import Splitter
    from taqsim.time import Timestep


@dataclass(frozen=True)
class NaturalRiverSplitter:
    """SplitRule for natural river bifurcations.

    Distributes flow according to fixed or time-varying natural ratios.
    This rule is NOT optimizable - it represents physical river conditions.

    For splitters where ALL downstream edges are natural, assign this as the
    split_policy directly. For mixed splitters (some natural, some not), use
    NATURAL_SPLIT_RATIOS metadata on the Splitter node instead.

    Args:
        ratios: Mapping from downstream target_id to split ratio(s).
            - Fixed: {target_id: float} where all values sum to 1.0
            - Time-varying: {target_id: tuple[float, ...]} where sums equal 1.0 at each timestep
        cyclical: If True and ratios are time-varying, wrap around when t >= len(ratios).

    Raises:
        ValueError: If ratios are invalid (empty, don't sum to 1.0, negative, etc.)
    """

    ratios: Mapping[str, float | tuple[float, ...]]
    cyclical: bool = False

    __tags__: ClassVar[frozenset[str]] = frozenset({NATURAL_TAG})
    __metadata__: ClassVar[Mapping[str, object]] = {
        "description": "Natural river bifurcation split ratios",
        "preserves_natural_flow": True,
    }

    def __post_init__(self) -> None:
        """Validate ratios at construction time."""
        if not self.ratios:
            raise ValueError("ratios cannot be empty")

        # Check if all values are same type (all fixed or all time-varying)
        is_time_varying = [isinstance(v, tuple) for v in self.ratios.values()]
        if any(is_time_varying) and not all(is_time_varying):
            raise ValueError("All ratios must be the same type (all fixed floats or all time-varying tuples)")

        if all(is_time_varying):
            self._validate_time_varying()
        else:
            self._validate_fixed()

    def _validate_fixed(self) -> None:
        """Validate fixed (scalar) ratios."""
        for target_id, ratio in self.ratios.items():
            if not isinstance(ratio, (int, float)):
                raise ValueError(f"Ratio for '{target_id}' must be a float, got {type(ratio).__name__}")
            if ratio < 0.0 or ratio > 1.0:
                raise ValueError(f"Ratio for '{target_id}' must be in [0.0, 1.0], got {ratio}")

        total = sum(self.ratios.values())  # type: ignore
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"Ratios must sum to 1.0, got {total}")

    def _validate_time_varying(self) -> None:
        """Validate time-varying (tuple) ratios."""
        lengths = set()
        for target_id, ratio_tuple in self.ratios.items():
            if not isinstance(ratio_tuple, tuple):
                raise ValueError(f"Expected tuple for '{target_id}', got {type(ratio_tuple).__name__}")
            if len(ratio_tuple) == 0:
                raise ValueError(f"Ratio tuple for '{target_id}' cannot be empty")
            lengths.add(len(ratio_tuple))

            for i, r in enumerate(ratio_tuple):
                if not isinstance(r, (int, float)):
                    raise ValueError(f"Ratio[{i}] for '{target_id}' must be a float")
                if r < 0.0 or r > 1.0:
                    raise ValueError(f"Ratio[{i}] for '{target_id}' must be in [0.0, 1.0], got {r}")

        if len(lengths) > 1:
            raise ValueError(f"All ratio tuples must have the same length, got lengths: {lengths}")

        # Check sum at each timestep
        num_timesteps = next(iter(lengths))
        for t in range(num_timesteps):
            total = sum(r[t] for r in self.ratios.values())  # type: ignore
            if abs(total - 1.0) > 1e-9:
                raise ValueError(f"Ratios at timestep {t} must sum to 1.0, got {total}")

    @property
    def is_time_varying(self) -> bool:
        """Check if ratios vary over time."""
        return any(isinstance(v, tuple) for v in self.ratios.values())

    @property
    def num_timesteps(self) -> int | None:
        """Number of timesteps for time-varying ratios, or None if fixed."""
        if not self.is_time_varying:
            return None
        first_val = next(iter(self.ratios.values()))
        return len(first_val) if isinstance(first_val, tuple) else None

    def split(self, node: "Splitter", amount: float, t: "Timestep") -> dict[str, float]:
        """Distribute water according to natural ratios.

        Args:
            node: The Splitter node (provides target list).
            amount: Total amount of water to distribute.
            t: Current timestep.

        Returns:
            Mapping from target_id to allocated amount.
        """
        result: dict[str, float] = {}

        for target_id, ratio in self.ratios.items():
            if isinstance(ratio, tuple):
                # Time-varying ratio
                idx = t
                if self.cyclical:
                    idx = t % len(ratio)
                elif t >= len(ratio):
                    idx = len(ratio) - 1  # Clamp to last value if not cyclical
                r = ratio[idx]
            else:
                # Fixed ratio
                r = ratio

            result[target_id] = amount * r

        return result

    def tags(self) -> frozenset[str]:
        """Return the tags for this rule."""
        return self.__tags__

    def metadata(self) -> Mapping[str, object]:
        """Return the metadata for this rule."""
        return self.__metadata__
