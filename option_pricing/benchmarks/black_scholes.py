"""Black-Scholes-Merton analytical pricer for European options.

Implements the classical benchmark specified in the option pricing
methodology, version 0.1:

  - Section 3.3: Black-Scholes-Merton pricing formulas.
  - Section 3.5: Analytical Greeks (Delta, Gamma, Vega, Theta, Rho).

This module is the analytical ground truth against which all other
implementations (Monte Carlo, quantum amplitude estimation) are
validated, per methodology Section 5.

Notation follows methodology Section 2.2:

    S_0    spot price                  -> spot
    K      strike price                -> strike
    T      maturity, in years          -> maturity
    r      risk-free rate              -> rate
    sigma  volatility                  -> volatility
    q      continuous dividend yield   -> dividend_yield
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from scipy.stats import norm


class OptionType(Enum):
    """Exercise direction of a vanilla European option."""

    CALL = "call"
    PUT = "put"


@dataclass(frozen=True)
class EuropeanOption:
    """Problem definition for a vanilla European option.

    Corresponds to the product definition in methodology Section 3.1.
    The instance is frozen (immutable): a problem definition should not
    change after construction. Immutability also helps reproducibility
    (methodology Section 2.3) -- a result can always be traced back to
    an input that has not been mutated.
    """

    spot: float                    # S_0   : current price of the underlying
    strike: float                  # K     : strike price
    maturity: float                # T     : time to maturity, in years
    rate: float                    # r     : risk-free rate, cont. compounded
    volatility: float              # sigma : annualised volatility
    option_type: OptionType
    dividend_yield: float = 0.0    # q     : continuous dividend yield

    def __post_init__(self) -> None:
        # The methodology assumes a well-posed problem. These checks make
        # ill-posed inputs fail loudly rather than silently producing a
        # meaningless price (e.g. math.log of a negative spot).
        if self.spot <= 0:
            raise ValueError("spot must be strictly positive")
        if self.strike <= 0:
            raise ValueError("strike must be strictly positive")
        if self.maturity <= 0:
            raise ValueError("maturity must be strictly positive")
        if self.volatility <= 0:
            raise ValueError("volatility must be strictly positive")


@dataclass(frozen=True)
class PricingResult:
    """Price and Greeks for a European option under Black-Scholes.

    All Greeks are raw continuous-time sensitivities, exactly as defined
    in methodology Section 3.5. Market-convention scaling (Theta per
    calendar day, Rho per 1% rate change) is a presentation-layer
    concern applied by the reporting layer, not here -- the core pricer
    returns the mathematically pure quantities.
    """

    price: float    # option value
    delta: float    # dV/dS_0
    gamma: float    # d2V/dS_0^2
    vega: float     # dV/dsigma   (raw: per unit of volatility)
    theta: float    # dV/dt       (raw: per year)
    rho: float      # dV/dr       (raw: per unit of rate)


def _d1_d2(option: EuropeanOption) -> tuple[float, float]:
    """Compute the d1 and d2 terms of the Black-Scholes formula.

    Methodology Section 3.3:

        d1 = [ln(S_0/K) + (r - q + sigma^2/2) T] / (sigma sqrt(T))
        d2 = d1 - sigma sqrt(T)
    """
    S, K = option.spot, option.strike
    T, r = option.maturity, option.rate
    sigma, q = option.volatility, option.dividend_yield

    sigma_sqrt_T = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / sigma_sqrt_T
    d2 = d1 - sigma_sqrt_T
    return d1, d2


def price_european_option(option: EuropeanOption) -> PricingResult:
    """Price a European option and compute its Greeks analytically.

    Implements methodology Section 3.3 (price) and Section 3.5 (Greeks).
    """
    S, K = option.spot, option.strike
    T, r = option.maturity, option.rate
    sigma, q = option.volatility, option.dividend_yield

    d1, d2 = _d1_d2(option)

    # N(.) is the standard normal CDF, phi(.) the standard normal PDF.
    # scipy.stats.norm is the implementation named in methodology 3.3.
    N = norm.cdf
    phi = norm.pdf

    disc_r = math.exp(-r * T)    # e^{-rT}, the discount factor
    disc_q = math.exp(-q * T)    # e^{-qT}, the dividend discount factor

    if option.option_type is OptionType.CALL:
        price = S * disc_q * N(d1) - K * disc_r * N(d2)
        delta = disc_q * N(d1)
        theta = (
            -(S * disc_q * phi(d1) * sigma) / (2.0 * math.sqrt(T))
            - r * K * disc_r * N(d2)
            + q * S * disc_q * N(d1)
        )
        rho = K * T * disc_r * N(d2)
    else:  # OptionType.PUT -- put forms follow by put-call parity
        price = K * disc_r * N(-d2) - S * disc_q * N(-d1)
        delta = -disc_q * N(-d1)
        theta = (
            -(S * disc_q * phi(d1) * sigma) / (2.0 * math.sqrt(T))
            + r * K * disc_r * N(-d2)
            - q * S * disc_q * N(-d1)
        )
        rho = -K * T * disc_r * N(-d2)

    # Gamma and Vega are identical for calls and puts (methodology 3.5).
    gamma = (disc_q * phi(d1)) / (S * sigma * math.sqrt(T))
    vega = S * disc_q * math.sqrt(T) * phi(d1)

    return PricingResult(
        price=price,
        delta=delta,
        gamma=gamma,
        vega=vega,
        theta=theta,
        rho=rho,
    )


if __name__ == "__main__":
    # Minimal demonstration: price the canonical at-the-money option.
    example = EuropeanOption(
        spot=100.0,
        strike=100.0,
        maturity=1.0,
        rate=0.05,
        volatility=0.20,
        option_type=OptionType.CALL,
    )
    result = price_european_option(example)

    print(f"European {example.option_type.value} option")
    print(f"  spot={example.spot}  strike={example.strike}  "
          f"maturity={example.maturity}  rate={example.rate}  "
          f"volatility={example.volatility}")
    print(f"  price : {result.price:10.6f}")
    print(f"  delta : {result.delta:10.6f}")
    print(f"  gamma : {result.gamma:10.6f}")
    print(f"  vega  : {result.vega:10.6f}   (raw, per unit volatility)")
    print(f"  theta : {result.theta:10.6f}   (raw, per year)")
    print(f"  rho   : {result.rho:10.6f}   (raw, per unit rate)")
