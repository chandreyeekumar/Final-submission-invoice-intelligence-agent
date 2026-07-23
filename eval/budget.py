from __future__ import annotations


class BudgetExceeded(RuntimeError):
    pass


class CostBudget:
    def __init__(
        self,
        max_cost_usd: float | None,
    ) -> None:
        if (
            max_cost_usd is not None
            and max_cost_usd < 0
        ):
            raise ValueError(
                "max_cost_usd must be non-negative"
            )

        self.max_cost_usd = max_cost_usd
        self.spent_usd = 0.0

    def register(
        self,
        amount_usd: float,
    ) -> None:
        amount = max(
            float(amount_usd),
            0.0,
        )

        projected = (
            self.spent_usd + amount
        )

        if (
            self.max_cost_usd is not None
            and projected
            > self.max_cost_usd
        ):
            raise BudgetExceeded(
                "Evaluation stopped after the "
                "latest paid result was checkpointed. "
                f"Previously counted=${self.spent_usd:.4f}, "
                f"latest=${amount:.4f}, "
                f"limit=${self.max_cost_usd:.4f}"
            )

        self.spent_usd = projected