"""Validation tests for the Black-Scholes-Merton pricer.

These tests implement the validation principles of methodology
Section 5.2 for analytical methods:

  - correctness against a known reference value,
  - structural identities (put-call parity, methodology Section 3.1),
  - Greek identities (Gamma and Vega equal for calls and puts, 3.5),
  - rejection of ill-posed problem definitions.

The full statistical battery and regime sweeps belong in the test
procedure document; this file covers the analytical correctness
checks that the methodology already lets us state.

Run with:  pytest test_black_scholes.py -v
"""

import math

import pytest

from black_scholes import EuropeanOption, OptionType, price_european_option


# A canonical textbook instance: an at-the-money option with one year
# to maturity. The Black-Scholes call value for these parameters is a
# widely tabulated reference, approximately 10.4506.
ATM_PARAMS = dict(
    spot=100.0,
    strike=100.0,
    maturity=1.0,
    rate=0.05,
    volatility=0.20,
    dividend_yield=0.0,
)


def _call() -> EuropeanOption:
    return EuropeanOption(option_type=OptionType.CALL, **ATM_PARAMS)


def _put() -> EuropeanOption:
    return EuropeanOption(option_type=OptionType.PUT, **ATM_PARAMS)


def test_call_price_matches_reference():
    """Call price matches the known textbook reference value (~10.4506)."""
    result = price_european_option(_call())
    assert result.price == pytest.approx(10.4506, abs=1e-4)


def test_put_call_parity():
    """Priced call and put satisfy put-call parity (methodology 3.1):

        C - P = S_0 e^{-qT} - K e^{-rT}

    This is an exact algebraic identity of the formulas, so it must
    hold to machine precision, not merely approximately.
    """
    call = price_european_option(_call())
    put = price_european_option(_put())

    S = ATM_PARAMS["spot"]
    K = ATM_PARAMS["strike"]
    r = ATM_PARAMS["rate"]
    q = ATM_PARAMS["dividend_yield"]
    T = ATM_PARAMS["maturity"]

    parity_lhs = call.price - put.price
    parity_rhs = S * math.exp(-q * T) - K * math.exp(-r * T)

    assert parity_lhs == pytest.approx(parity_rhs, abs=1e-10)


def test_gamma_equal_for_call_and_put():
    """Gamma is identical for calls and puts (methodology 3.5)."""
    call = price_european_option(_call())
    put = price_european_option(_put())
    assert call.gamma == pytest.approx(put.gamma, abs=1e-12)


def test_vega_equal_for_call_and_put():
    """Vega is identical for calls and puts (methodology 3.5)."""
    call = price_european_option(_call())
    put = price_european_option(_put())
    assert call.vega == pytest.approx(put.vega, abs=1e-12)


def test_call_delta_in_unit_interval():
    """Call delta lies in [0, 1]; with zero dividends it equals N(d1)."""
    result = price_european_option(_call())
    assert 0.0 <= result.delta <= 1.0


def test_put_delta_in_unit_interval():
    """Put delta lies in [-1, 0]."""
    result = price_european_option(_put())
    assert -1.0 <= result.delta <= 0.0


def test_call_theta_is_negative():
    """A vanilla call with zero dividends loses value as time passes,
    so dV/dt is negative."""
    result = price_european_option(_call())
    assert result.theta < 0.0


def test_invalid_inputs_rejected():
    """Ill-posed problem definitions fail loudly at construction
    (methodology 3.7 assumes a well-posed problem)."""
    with pytest.raises(ValueError):
        EuropeanOption(
            spot=-100.0, strike=100.0, maturity=1.0,
            rate=0.05, volatility=0.20, option_type=OptionType.CALL,
        )
    with pytest.raises(ValueError):
        EuropeanOption(
            spot=100.0, strike=100.0, maturity=0.0,
            rate=0.05, volatility=0.20, option_type=OptionType.CALL,
        )
    with pytest.raises(ValueError):
        EuropeanOption(
            spot=100.0, strike=100.0, maturity=1.0,
            rate=0.05, volatility=-0.20, option_type=OptionType.CALL,
        )
