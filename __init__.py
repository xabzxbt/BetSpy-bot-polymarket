"""
BetSpy Advanced Analytics Package

Modules:
  - data_fetcher: CLOB price history + CoinGecko wrapper
  - probability: signal_score → model_probability converter
  - kelly: Kelly Criterion position sizing
  - greeks: Theta decay + Vega volatility
  - monte_carlo: Monte Carlo simulations
  - bayesian: Bayesian probability updater
  - orchestrator: Runs all modules, produces DeepAnalysis
"""

from analytics.orchestrator import DeepAnalysis, run_deep_analysis

__all__ = ["DeepAnalysis", "run_deep_analysis"]
