"""
Tests for unified model probability, edge calculation, and recommendation logic.

Three canonical scenarios:
  a) Pisa-type: model ≈ market → SKIP, edge ~0, Kelly=0
  b) Strong YES edge: model >> market → BUY YES
  c) Strong NO edge: model << market → BUY NO
"""

import sys
import os
import pytest

# Add project root to path so we can import analytics modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analytics.orchestrator import _compute_model_probability
from analytics.kelly import calculate_kelly
from analytics.bayesian import BayesianResult, Evidence
from analytics.monte_carlo import MonteCarloResult


# =====================================================================
# Helpers to build test fixtures
# =====================================================================

def make_bayesian(prior: float, posterior: float) -> BayesianResult:
    """Create a BayesianResult with given prior/posterior."""
    evidence = []
    if abs(posterior - prior) >= 0.03:
        evidence = [Evidence(
            name="Test Evidence",
            description="test",
            likelihood_ratio=1.5 if posterior > prior else 0.67,
        )]
    return BayesianResult(
        prior=prior,
        posterior=posterior,
        evidence_list=evidence,
        combined_lr=1.0,
        update_magnitude=abs(posterior - prior),
    )


def make_mc(probability_yes: float, market_price: float, mode: str = "generic") -> MonteCarloResult:
    """Create a MonteCarloResult with given probability."""
    return MonteCarloResult(
        mode=mode,
        num_simulations=10000,
        probability_yes=probability_yes,
        market_price=market_price,
        edge=probability_yes - market_price,
    )


# =====================================================================
# Test A: Pisa-type — model ≈ market → SKIP
# =====================================================================

class TestPisaTypeSkip:
    """
    Scenario: 'Will Pisa SC win?' — YES 13¢, NO 86¢
    MC = 13.5%, Bayesian prior=13% → posterior=13.5%
    |posterior - prior| = 0.5 p.p. < 2 p.p. → model confirms market
    Expected: model_prob ≈ 13%, edge ≈ 0, Kelly = 0, SKIP
    """

    def test_model_probability_confirms_market(self):
        market_price = 0.13
        bayes = make_bayesian(prior=0.13, posterior=0.135)
        mc = make_mc(probability_yes=0.135, market_price=market_price)

        model_prob = _compute_model_probability(
            mc_result=mc,
            bayesian_result=bayes,
            market_price=market_price,
        )

        # Model should equal market price (confirms market)
        assert model_prob == market_price, (
            f"Expected model_prob={market_price}, got {model_prob}. "
            f"When Bayesian shift < 2pp, model should confirm market."
        )

    def test_edge_is_zero(self):
        market_price = 0.13
        bayes = make_bayesian(prior=0.13, posterior=0.135)
        mc = make_mc(probability_yes=0.135, market_price=market_price)

        model_prob = _compute_model_probability(
            mc_result=mc,
            bayesian_result=bayes,
            market_price=market_price,
        )

        edge_yes = model_prob - market_price
        edge_no = market_price - model_prob

        assert abs(edge_yes) < 0.02, f"edge_yes should be ~0, got {edge_yes}"
        assert abs(edge_no) < 0.02, f"edge_no should be ~0, got {edge_no}"

    def test_kelly_is_zero_when_no_edge(self):
        market_price = 0.13
        # model_prob = market_price when model confirms market
        kelly = calculate_kelly(
            model_prob=market_price,
            market_price=market_price,
            bankroll=10000,
            fraction=0.25,
            days_to_resolve=1,
        )

        assert kelly.kelly_full == 0.0, f"Kelly full should be 0, got {kelly.kelly_full}"
        assert kelly.kelly_final_pct == 0.0, f"Kelly final should be 0, got {kelly.kelly_final_pct}"
        assert kelly.recommended_size == 0.0, f"Rec size should be 0, got {kelly.recommended_size}"

    def test_recommendation_is_skip(self):
        market_price = 0.13
        bayes = make_bayesian(prior=0.13, posterior=0.135)
        mc = make_mc(probability_yes=0.135, market_price=market_price)

        model_prob = _compute_model_probability(
            mc_result=mc,
            bayesian_result=bayes,
            market_price=market_price,
        )

        EDGE_THRESHOLD = 0.02
        edge_yes = model_prob - market_price
        edge_no = -edge_yes

        if edge_yes > EDGE_THRESHOLD:
            rec_side = "YES"
        elif edge_no > EDGE_THRESHOLD:
            rec_side = "NO"
        else:
            rec_side = "NEUTRAL"

        assert rec_side == "NEUTRAL", (
            f"Expected NEUTRAL/SKIP, got {rec_side}. "
            f"model_prob={model_prob}, market={market_price}, edge_yes={edge_yes}"
        )


# =====================================================================
# Test B: Strong YES edge — model >> market → BUY YES
# =====================================================================

class TestStrongYesEdge:
    """
    Scenario: Bayesian detects strong whale surge pushing YES
    Market YES = 40¢, Bayesian prior=40% → posterior=55%
    MC (crypto) = 52%
    |posterior - prior| = 15 p.p. >> 2 p.p. → Bayesian has signal
    model_prob = 0.7 * 0.55 + 0.3 * 0.52 = 0.385 + 0.156 = 0.541
    edge_yes = 0.541 - 0.40 = 0.141 = 14.1 p.p. >> 2 p.p. → BUY YES
    """

    def test_model_probability_above_market(self):
        market_price = 0.40
        bayes = make_bayesian(prior=0.40, posterior=0.55)
        mc = make_mc(probability_yes=0.52, market_price=market_price, mode="crypto")

        model_prob = _compute_model_probability(
            mc_result=mc,
            bayesian_result=bayes,
            market_price=market_price,
        )

        expected = 0.7 * 0.55 + 0.3 * 0.52  # = 0.541
        assert abs(model_prob - expected) < 0.001, (
            f"Expected model_prob≈{expected}, got {model_prob}"
        )

    def test_edge_is_positive_for_yes(self):
        market_price = 0.40
        bayes = make_bayesian(prior=0.40, posterior=0.55)
        mc = make_mc(probability_yes=0.52, market_price=market_price, mode="crypto")

        model_prob = _compute_model_probability(
            mc_result=mc,
            bayesian_result=bayes,
            market_price=market_price,
        )

        edge_yes = model_prob - market_price
        assert edge_yes > 0.02, f"edge_yes should be > 2pp, got {edge_yes*100:.1f}pp"

    def test_recommendation_is_buy_yes(self):
        market_price = 0.40
        bayes = make_bayesian(prior=0.40, posterior=0.55)
        mc = make_mc(probability_yes=0.52, market_price=market_price, mode="crypto")

        model_prob = _compute_model_probability(
            mc_result=mc,
            bayesian_result=bayes,
            market_price=market_price,
        )

        EDGE_THRESHOLD = 0.02
        edge_yes = model_prob - market_price
        edge_no = -edge_yes

        if edge_yes > EDGE_THRESHOLD:
            rec_side = "YES"
        elif edge_no > EDGE_THRESHOLD:
            rec_side = "NO"
        else:
            rec_side = "NEUTRAL"

        assert rec_side == "YES", f"Expected YES, got {rec_side}"

    def test_kelly_is_positive(self):
        market_price = 0.40
        model_prob = 0.541  # pre-computed

        kelly = calculate_kelly(
            model_prob=model_prob,
            market_price=market_price,
            bankroll=10000,
            fraction=0.25,
            days_to_resolve=7,
        )

        assert kelly.kelly_full > 0, f"Kelly full should be > 0, got {kelly.kelly_full}"
        assert kelly.kelly_final_pct > 0, f"Kelly final should be > 0, got {kelly.kelly_final_pct}"
        assert kelly.recommended_side == "YES", f"Kelly side should be YES, got {kelly.recommended_side}"


# =====================================================================
# Test C: Strong NO edge — model << market → BUY NO
# =====================================================================

class TestStrongNoEdge:
    """
    Scenario: Bayesian detects bearish evidence (price-volume divergence)
    Market YES = 70¢, Bayesian prior=70% → posterior=52%
    MC (generic) = 70% (market price, neutral)
    |posterior - prior| = 18 p.p. >> 2 p.p. → Bayesian has signal
    model_prob = 0.7 * 0.52 + 0.3 * 0.70 = 0.364 + 0.210 = 0.574
    model_no_prob = 1 - 0.574 = 0.426
    market_no_prob = 1 - 0.70 = 0.30
    edge_no = 0.426 - 0.30 = 0.126 = 12.6 p.p. → BUY NO
    edge_yes = 0.574 - 0.70 = -0.126 → negative
    """

    def test_model_probability_below_market(self):
        market_price = 0.70
        bayes = make_bayesian(prior=0.70, posterior=0.52)
        mc = make_mc(probability_yes=0.70, market_price=market_price)

        model_prob = _compute_model_probability(
            mc_result=mc,
            bayesian_result=bayes,
            market_price=market_price,
        )

        expected = 0.7 * 0.52 + 0.3 * 0.70  # = 0.574
        assert abs(model_prob - expected) < 0.001, (
            f"Expected model_prob≈{expected}, got {model_prob}"
        )
        assert model_prob < market_price, "model_prob should be below market for NO edge"

    def test_recommendation_is_buy_no(self):
        market_price = 0.70
        bayes = make_bayesian(prior=0.70, posterior=0.52)
        mc = make_mc(probability_yes=0.70, market_price=market_price)

        model_prob = _compute_model_probability(
            mc_result=mc,
            bayesian_result=bayes,
            market_price=market_price,
        )

        EDGE_THRESHOLD = 0.02
        edge_yes = model_prob - market_price
        edge_no = -edge_yes

        if edge_yes > EDGE_THRESHOLD:
            rec_side = "YES"
        elif edge_no > EDGE_THRESHOLD:
            rec_side = "NO"
        else:
            rec_side = "NEUTRAL"

        assert rec_side == "NO", f"Expected NO, got {rec_side}. edge_no={edge_no}"

    def test_kelly_recommends_no(self):
        market_price = 0.70
        model_prob = 0.574  # pre-computed

        kelly = calculate_kelly(
            model_prob=model_prob,
            market_price=market_price,
            bankroll=10000,
            fraction=0.25,
            days_to_resolve=14,
        )

        assert kelly.kelly_full > 0, f"Kelly full should be > 0, got {kelly.kelly_full}"
        assert kelly.recommended_side == "NO", f"Kelly side should be NO, got {kelly.recommended_side}"

    def test_edge_no_is_positive(self):
        market_price = 0.70
        model_prob = 0.574

        edge_yes = model_prob - market_price  # negative
        edge_no = -edge_yes  # positive

        assert edge_yes < 0, f"edge_yes should be negative, got {edge_yes}"
        assert edge_no > 0.02, f"edge_no should be > 2pp, got {edge_no}"


# =====================================================================
# Additional edge cases
# =====================================================================

class TestEdgeCases:
    """Test boundary conditions and guardrails."""

    def test_no_bayesian_no_mc_returns_market_price(self):
        """When both models are unavailable, model = market → SKIP."""
        model_prob = _compute_model_probability(
            mc_result=None,
            bayesian_result=None,
            market_price=0.50,
        )
        assert model_prob == 0.50

    def test_bayesian_shift_exactly_2pp(self):
        """Boundary: |shift| == 2pp should trigger blend (>= 0.02)."""
        market_price = 0.50
        bayes = make_bayesian(prior=0.50, posterior=0.52)
        mc = make_mc(probability_yes=0.50, market_price=market_price)

        model_prob = _compute_model_probability(
            mc_result=mc,
            bayesian_result=bayes,
            market_price=market_price,
        )

        # Should blend: 0.7*0.52 + 0.3*0.50 = 0.364 + 0.15 = 0.514
        expected = 0.7 * 0.52 + 0.3 * 0.50
        assert abs(model_prob - expected) < 0.001, (
            f"At exactly 2pp shift, should blend. Expected {expected}, got {model_prob}"
        )

    def test_bayesian_shift_just_below_2pp(self):
        """Shift = 1.9pp should confirm market."""
        market_price = 0.50
        bayes = make_bayesian(prior=0.50, posterior=0.519)

        model_prob = _compute_model_probability(
            mc_result=None,
            bayesian_result=bayes,
            market_price=market_price,
        )

        assert model_prob == market_price, (
            f"Shift < 2pp should confirm market. Got {model_prob}"
        )

    def test_kelly_capped_at_20_percent(self):
        """Full Kelly should never exceed 20%."""
        kelly = calculate_kelly(
            model_prob=0.95,
            market_price=0.50,
            bankroll=10000,
            fraction=0.25,
            days_to_resolve=1,
        )
        assert kelly.kelly_full <= 0.20, (
            f"Kelly full should be capped at 20%, got {kelly.kelly_full}"
        )

    def test_model_prob_clamped(self):
        """Model probability should be clamped to [0.03, 0.97]."""
        bayes = make_bayesian(prior=0.01, posterior=0.005)
        model_prob = _compute_model_probability(
            mc_result=None,
            bayesian_result=bayes,
            market_price=0.01,
        )
        assert model_prob >= 0.03, f"Should be clamped to >= 0.03, got {model_prob}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
