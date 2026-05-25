# Methodology: Option Pricing

**Version:** 0.1 (draft)
**Last updated:** 2026-05-21
**Status:** Draft — content-complete pending market data source decisions (§3.6, §4.7).

---

## 1. Introduction

### 1.1 Purpose

This document specifies the methodology used by the platform to price options using both classical and quantum computational methods. It defines the financial models, the algorithmic approaches, the benchmarking protocol, and the criteria under which results should be interpreted.

The document is the canonical reference for any implementation, benchmark, or report produced on the topic of option pricing. **Code, tests, and reports are written to this document — not the reverse.** When implementation reveals a methodological issue, the resolution is to revise this document explicitly via a versioned change, not to silently diverge from it.

### 1.2 Audience

The intended readers are:

- Financial engineers and quantitative analysts evaluating quantum approaches to option pricing.
- Risk and validation professionals assessing the credibility of platform outputs.
- Researchers and practitioners interested in reproducing or extending the work.
- Developers implementing or modifying the underlying code.

A working knowledge of derivatives pricing under the risk-neutral measure and a basic familiarity with quantum circuits and amplitude estimation is assumed. Where specific results from the quantum literature are used, they are referenced explicitly in the bibliography.

### 1.3 Scope

This version covers two product families:

- **European options** with vanilla call and put payoffs, under the Black–Scholes–Merton framework.
- **Asian options** with geometric average payoffs, under the same framework.

The following are explicitly **out of scope** at this version:

- American and Bermudan exercise styles.
- Asian options with arithmetic averaging.
- Multi-asset options (basket, spread, rainbow).
- Options on assets with stochastic volatility, jumps, or stochastic interest rates.
- Exotic payoff structures (barrier, lookback, cliquet, digital, etc.).
- Real-time or intraday pricing workflows.

These may be addressed in future versions as scope expands. Expanding scope requires a methodology revision, not a code-only change.

### 1.4 Concepts and prerequisites

This document assumes working familiarity with the concepts listed below. The list serves two purposes: it states the prerequisites for readers, and it maps the knowledge surface used by the platform so that readers without a given concept know explicitly what to study. The bibliography (§6) provides starting points; the section reference next to each concept indicates where it is first used in the document.

**Financial engineering concepts**

- *Risk-neutral pricing and the martingale measure.* The principle that derivative prices are discounted expectations under a transformed probability measure. Used throughout (first in §2.1).
- *Geometric Brownian motion (GBM).* The continuous-time stochastic model for asset prices under which the methodology operates (§2.1).
- *Black–Scholes–Merton model.* The closed-form pricing framework for European options under GBM. Used as ground truth (§3.3) and as the basis for analytical Greeks (§3.5).
- *Vanilla options.* European calls and puts; the canonical instruments (§3.1).
- *Path-dependent options.* Options whose payoff depends on the trajectory of the underlying rather than only its terminal value. Asian options are the example used here (§4.1).
- *Greeks.* First- and second-order sensitivities of price to model inputs (§3.5, §4.6).
- *Put–call parity.* The structural arbitrage relation between calls and puts. Used as a sanity check (§3.1, §4.3).
- *Monte Carlo simulation.* The path-sampling approach to expected-value estimation. Specified as the competing classical method for Asians (§4.4).
- *Variance reduction (antithetic and control variates).* Techniques to reduce the variance of Monte Carlo estimators (§4.4).
- *Forward price and Black's formula.* The expected risk-neutral terminal value of an asset, and the option-pricing formula written in terms of forward prices. Used for Kemna–Vorst (§4.3).

**Quantum computing concepts**

- *Qubits, quantum states, and registers.* The basic units of quantum information and how they are grouped for computation. Used throughout the quantum sections.
- *Quantum circuits and gates.* Unitary operations on registers (§3.4, §4.5).
- *Ancilla qubits.* Auxiliary qubits used to extract information without disturbing the main register. Used in payoff encoding (§3.4).
- *Distribution loading (quantum state preparation).* The procedure for encoding a classical probability distribution into the amplitudes of a quantum state. Specified in §3.4 and §4.5; limitations in §3.7.
- *Quantum Amplitude Estimation (QAE).* The algorithm that gives the quadratic speedup over classical sampling for expected-value estimation (§3.4).
- *Iterative QAE (IQAE).* The variant of QAE used in this methodology, which avoids the Quantum Fourier Transform (§3.4).
- *Quantum Fourier Transform (QFT).* The quantum analogue of the discrete Fourier transform, used in canonical QAE but avoided in IQAE. Referenced in §3.4.
- *Payoff encoding via controlled rotations.* The mechanism for embedding a payoff function as an ancilla rotation angle (§3.4).
- *Statevector vs. shot-based simulation.* Two modes of classical simulation of quantum circuits, with different fidelity and cost properties. Used in benchmark configuration (§3.4).
- *Noise, decoherence, and gate errors.* Physical limitations of real quantum hardware; deferred to v2 (§3.7).

### 1.5 Versioning policy

This document is versioned alongside the implementation in the project repository. Material changes — to assumptions, models, benchmarks, or test procedures — require a pull request with explicit rationale, a version increment, and a changelog entry. The version history is part of the audit trail and is not rewritten retroactively.

Version increments follow semantic principles:

- **Major (1.0 → 2.0):** Breaking changes to scope, fundamental assumptions, or interfaces.
- **Minor (1.0 → 1.1):** Additive changes, new product families, expanded coverage.
- **Patch (1.0.0 → 1.0.1):** Corrections, clarifications, typographical fixes.

Any published result must cite the methodology version under which it was produced.

---

## 2. General Framework

### 2.1 Risk-neutral pricing principle

The platform prices derivatives under the risk-neutral measure $\mathbb{Q}$. Under standard assumptions of an arbitrage-free, frictionless, complete market with a constant risk-free rate $r$, the no-arbitrage price at time $t$ of a contingent claim paying $H(S_T)$ at maturity $T$ is:

$$
V(S_t, t) = e^{-r(T-t)} \, \mathbb{E}^{\mathbb{Q}}\!\left[ H(S_T) \,\middle|\, \mathcal{F}_t \right]
$$

where $S_T$ is the underlying asset value at maturity and $\mathcal{F}_t$ is the filtration available at time $t$. Under the risk-neutral measure, the underlying is assumed to follow a geometric Brownian motion:

$$
dS_t = (r - q) \, S_t \, dt + \sigma \, S_t \, dW_t^{\mathbb{Q}}
$$

where $\sigma$ is the constant volatility, $q$ is the continuous dividend yield (defaulting to zero unless stated), and $W_t^{\mathbb{Q}}$ is a standard Brownian motion under $\mathbb{Q}$.

This is the foundational assumption underlying both the classical benchmarks (Black–Scholes, Kemna–Vorst) and the quantum implementations described in this document. Departures from this assumption — for example, the introduction of stochastic volatility or jump processes — are out of scope for the current version and would require a major version increment.

### 2.2 Notation conventions

For consistency throughout the document:

| Symbol | Meaning |
|---|---|
| $S_t$ | Underlying asset price at time $t$ |
| $S_0$ | Spot price at valuation |
| $K$ | Strike price |
| $T$ | Maturity (in years) |
| $\tau$ | Time to maturity, $\tau = T - t$ |
| $r$ | Risk-free rate (continuously compounded, annualised) |
| $q$ | Continuous dividend yield (default: 0) |
| $\sigma$ | Volatility (annualised) |
| $N(\cdot)$ | Cumulative distribution function of the standard normal |
| $\mathbb{E}^{\mathbb{Q}}[\cdot]$ | Expectation under the risk-neutral measure $\mathbb{Q}$ |

Quantum-specific notation:

| Symbol | Meaning |
|---|---|
| $n$ | Number of qubits used to discretise the underlying distribution |
| $m$ | Number of qubits used in the amplitude estimation register |
| $\|\psi\rangle$ | Quantum state representing the loaded distribution |
| $\mathcal{A}$ | Operator preparing the initial quantum state |
| $\mathcal{Q}$ | Grover-like iterate used in amplitude estimation |

### 2.3 Reproducibility standards

Every result produced by the platform — quantum or classical, in any context — must be reproducible bit-for-bit from its published configuration. This requires the following to be recorded alongside each result:

- **Random seeds**: explicit, recorded, and stored in the result metadata.
- **Library versions**: pinned in `pyproject.toml` and recorded in the result metadata.
- **Environment**: Python version and operating system recorded.
- **Configuration**: the full input parameter set serialised with the result.
- **Hardware or simulator**: backend identifier and any device-targeting parameters recorded explicitly.

A result that cannot be regenerated bit-for-bit from its recorded configuration is considered invalid and must not be cited in any benchmark, report, or methodology revision.

### 2.4 Quality bar

The platform commits to the following standards for any pricing result it publishes:

- **Honest classical baselines.** Classical methods are implemented and tuned with the same care as quantum methods. We do not weaken classical implementations to make quantum approaches appear more favourable.
- **Appropriate uncertainty quantification.** Every result is reported with the uncertainty characteristic of its method. Stochastic estimators (Monte Carlo, quantum amplitude estimation) are reported with confidence intervals derived from sample variance and the number of trials. Analytical methods (Black–Scholes, Kemna–Vorst) are reported as exact values for their specified model, with the underlying assumptions and any input sensitivities (e.g., to volatility) stated explicitly. The principle is honesty about uncertainty, not uniform statistical reporting; sampling error and model risk are distinct quantities and are treated as such.
- **Regime transparency.** Every benchmark identifies the parameter regime in which the result holds. We explicitly identify regimes where quantum approaches do *not* outperform classical, and we present these alongside favourable regimes.
- **Failure documentation.** Known failure modes, edge cases, and convergence issues are documented as part of the methodology, not hidden from the user.

These standards reflect the broader principle that the methodology is the credential. Documentation of what can go wrong is as important as documentation of what works.

---

## 3. Product scope 1: European options

### 3.1 Product definition

A European option grants the holder the right, but not the obligation, to buy (call) or sell (put) a single specified underlying asset at a fixed strike price $K$ on a single specified maturity date $T$. Exercise is permitted only at $T$, not before.

The terminal payoff functions are:

$$
H_{\text{call}}(S_T) = \max(S_T - K, 0)
$$

$$
H_{\text{put}}(S_T) = \max(K - S_T, 0)
$$

Settlement is assumed to be cash settlement, denominated in the same currency as $K$ and the underlying. Physical settlement is treated as economically equivalent and is not modelled separately at this version.

Put–call parity is taken as a consistency relation and used as a structural sanity check on any pricing implementation:

$$
C(S_0, K, T) - P(S_0, K, T) = S_0 e^{-qT} - K e^{-rT}
$$

A deviation of any priced call–put pair from this identity beyond floating-point tolerance is treated as a bug.

### 3.2 Underlying model

The underlying $S_t$ is modelled as a geometric Brownian motion under the risk-neutral measure $\mathbb{Q}$, as specified in section 2.1. The resulting distribution of $S_T$ conditional on $S_0$ is log-normal:

$$
\ln S_T \;\sim\; \mathcal{N}\!\left( \ln S_0 + \left(r - q - \tfrac{1}{2}\sigma^2\right) T, \; \sigma^2 T \right)
$$

This log-normal terminal distribution is the object that both the analytical benchmark and the quantum approach operate on — the former in closed form, the latter via discretisation and quantum state preparation.

### 3.3 Classical benchmark: Black–Scholes–Merton

The Black–Scholes–Merton formula provides a closed-form price for vanilla European options under the GBM assumption. For a call option:

$$
C(S_0, K, T) = S_0 e^{-qT} N(d_1) - K e^{-rT} N(d_2)
$$

For a put option:

$$
P(S_0, K, T) = K e^{-rT} N(-d_2) - S_0 e^{-qT} N(-d_1)
$$

where:

$$
d_1 = \frac{\ln(S_0/K) + (r - q + \tfrac{1}{2}\sigma^2) T}{\sigma \sqrt{T}}, \qquad d_2 = d_1 - \sigma \sqrt{T}
$$

and $N(\cdot)$ is the cumulative distribution function of the standard normal.

**Role in the methodology.** Black–Scholes is the analytical *ground truth* under the stated model. All other implementations — including the quantum approach described below — are validated by comparison against Black–Scholes for problem instances within its scope of applicability.

This is ground truth for *the model*, not for *the market*. Market prices show systematic deviations from Black–Scholes (volatility smile, term structure of implied volatility, fat tails in realised distributions, etc.) that reflect model limitations rather than implementation errors. When market data is introduced (see 3.5), discrepancies between Black–Scholes and market prices are expected and are model risk, not bugs.

**Numerical considerations.** The computation of $N(\cdot)$ is performed via `scipy.stats.norm.cdf`, which uses the complementary error function. Floating-point precision is double-precision IEEE 754. Numerical accuracy is far below the precision relevant to this methodology and is not a limiting factor.

### 3.4 Quantum approach: Quantum Amplitude Estimation with distribution loading

The quantum approach follows the framework of Stamatopoulos et al. (2020), which adapts the Quantum Amplitude Estimation algorithm of Brassard et al. (2002) to the option pricing problem.

The structure has four stages:

1. **Distribution loading.** The risk-neutral terminal distribution of $S_T$ is discretised into $2^n$ points using $n$ qubits. A quantum circuit prepares the state

   $$
   |\psi\rangle = \sum_{i=0}^{2^n - 1} \sqrt{p_i} \, |i\rangle
   $$

   where $p_i$ is the probability mass assigned to grid point $S_i$ under the discretised log-normal distribution.

2. **Payoff encoding.** A controlled rotation on an ancilla qubit is applied such that, conditional on the loaded state, the probability of measuring the ancilla in state $|1\rangle$ is proportional to $\mathbb{E}^{\mathbb{Q}}[H(S_T)]$. We use the linear approximation of Woerner & Egger (2019), in which the payoff is mapped to a small rotation angle. This introduces a controlled, quantifiable approximation error.

3. **Amplitude estimation.** The probability of measuring the ancilla in $|1\rangle$ is estimated using Iterative Quantum Amplitude Estimation (IQAE; Grinko et al. 2021). IQAE is selected over canonical QAE (Brassard et al. 2002) because it does not require the Quantum Fourier Transform, produces shallower circuits, and is better suited to noisy hardware. Canonical QAE remains available as a comparison method in the validation section.

4. **Decoding.** The estimated probability is rescaled to recover the undiscounted expected payoff, then multiplied by the discount factor $e^{-rT}$ to produce the option price.

**Theoretical complexity.** Under noiseless conditions, QAE estimates the amplitude with accuracy $\varepsilon$ using $\mathcal{O}(1/\varepsilon)$ applications of the state-preparation operator, compared with $\mathcal{O}(1/\varepsilon^2)$ samples required by classical Monte Carlo. This is the quadratic speedup commonly cited in the literature.

This speedup is asymptotic and is realised only when distribution loading and payoff encoding can be implemented with circuit depth that does not dominate the algorithm. In practice, efficient general-purpose distribution loading remains an open problem (see 3.6), and the practical advantage of QAE over Monte Carlo on near-term hardware is not yet established for finance problems at scale. The benchmarks in this platform measure this gap directly rather than assume it.

**Specified parameters.** The implementation exposes:

| Parameter | Description |
|---|---|
| $n$ | Number of qubits discretising $S_T$ |
| Payoff approximation order | Order of the linear approximation in payoff encoding |
| $\varepsilon$ | Target precision (IQAE termination criterion) |
| $\alpha$ | Confidence level for the IQAE estimate |
| Shot budget | Maximum number of circuit evaluations |
| Simulator backend | `qiskit-aer` statevector or sampling backend |

Default parameter values for benchmark runs are specified in the test procedure document.

### 3.5 Sensitivities (Greeks)

The platform computes the standard first- and second-order Greeks alongside option prices. These sensitivities are essential to hedging, risk management, and P&L attribution in practice, and any methodology intended for serious use must specify how they are computed and validated.

**Analytical Greeks from Black–Scholes.** The closed-form Greeks under the BSM model are computed directly and serve as the analytical ground truth, on the same basis as the price itself.

Delta:

$$
\Delta_{\text{call}} = e^{-qT} N(d_1), \qquad \Delta_{\text{put}} = -e^{-qT} N(-d_1)
$$

Gamma (identical for calls and puts):

$$
\Gamma = \frac{e^{-qT} \, \varphi(d_1)}{S_0 \, \sigma \, \sqrt{T}}
$$

where $\varphi(\cdot)$ is the standard normal probability density.

Vega (identical for calls and puts):

$$
\mathcal{V} = S_0 \, e^{-qT} \, \sqrt{T} \, \varphi(d_1)
$$

Theta (call):

$$
\Theta_{\text{call}} = -\frac{S_0 \, \varphi(d_1) \, \sigma \, e^{-qT}}{2\sqrt{T}} - r K e^{-rT} N(d_2) + q S_0 e^{-qT} N(d_1)
$$

Rho (call):

$$
\rho_{\text{call}} = K T e^{-rT} N(d_2)
$$

Put versions of Theta and Rho follow by put–call parity. By market convention, Theta is reported per calendar day (divided by 365) and Rho is reported per 1% absolute rate change (divided by 100); the continuous-time definitions above are the underlying expressions.

**Quantum Greeks via finite differences.** Greeks for the QAE pricer are estimated via finite differences on the pricing operator. For a parameter $x$ and step size $h$:

For first-order Greeks (Delta, Vega, Rho, Theta), central differences are used:

$$
\frac{\partial V}{\partial x} \approx \frac{V(x + h) - V(x - h)}{2h}, \qquad \text{truncation error } \mathcal{O}(h^2)
$$

For the second-order Greek (Gamma), the three-point central difference is used:

$$
\frac{\partial^2 V}{\partial x^2} \approx \frac{V(x + h) - 2 V(x) + V(x - h)}{h^2}, \qquad \text{truncation error } \mathcal{O}(h^2)
$$

Each first-order Greek requires two additional QAE pricing runs. Gamma reuses the $V(x \pm h)$ evaluations from Delta, adding only the cost of $V(x)$ if not already computed.

**Step size selection.** Finite-difference Greeks face a trade-off between truncation error (which grows with $h$) and statistical noise from QAE (which dominates when $h$ is small, because the differences become comparable to the QAE precision $\varepsilon$). The platform selects $h$ adaptively based on the QAE precision parameter and the local magnitude of the price; the protocol is specified in the test procedure document.

**Out of scope at this version.** Second-order cross Greeks (Vanna, Volga, Charm), third-order Greeks (Speed, Color, Zomma), and quantum gradient methods that avoid finite differences (Jordan's algorithm, parameter-shift rules, automatic differentiation of quantum circuits) are out of scope at this version. They may be addressed in future revisions.

### 3.6 Market data source

*To be specified. This section will define:*

- *Source(s) of market data used for real-data validation*
- *Date range and contract universe*
- *Licensing and redistribution constraints*
- *Procedure for data refresh and versioning*

### 3.7 Known limitations and out-of-scope

The following limitations apply to the current methodology and implementation, presented in approximate order of likely impact on results:

- **Distribution loading complexity.** Efficient state preparation for arbitrary log-normal distributions is not solved in the general case. Naive amplitude encoding scales exponentially in $n$ in the worst case. Practical implementations rely on approximate loading methods (Grover–Rudolph, quantum GANs, low-depth approximations) with their own error and resource trade-offs. The achievable practical speedup of QAE over Monte Carlo depends critically on this stage and is benchmarked explicitly rather than assumed.
- **Discretisation error.** Finite $n$ introduces a quantisation error in the loaded distribution. The error scales with the grid spacing relative to the standard deviation of $S_T$. For deep out-of-the-money options or long maturities, modest $n$ may be inadequate, and the error is reported alongside the estimate.
- **Payoff encoding approximation.** The linear approximation in payoff encoding introduces a controllable error term that scales with the approximation order. Higher-order approximations reduce the error at the cost of additional circuit depth.
- **Single-underlying restriction.** Multi-asset payoffs would require $n$ qubits per asset and joint distribution loading, with attendant scaling consequences. Out of scope at this version.
- **Constant model parameters.** Volatility $\sigma$, risk-free rate $r$, and dividend yield $q$ are treated as constants. No volatility smile, term structure of implied volatility, or stochastic models are accommodated at this version.
- **Hardware execution.** This version is implemented and validated on classical simulators only. Execution on real quantum hardware introduces noise, decoherence, and gate-error effects not captured here. Hardware execution is planned as a v2 extension with its own methodology pages covering noise characterisation, error mitigation, and confidence reporting under hardware noise. It will be offered as a paid feature, separate from the core simulator-based methodology.

The test procedure document quantifies the impact of these limitations on results within the supported scope.

## 4. Product scope 2: Asian options with geometric average

### 4.1 Product definition

An Asian option is a path-dependent contingent claim whose payoff depends on an average of the underlying asset price over a specified set of observation dates, rather than on a single terminal value. At this version, the platform supports **fixed-strike Asian options with discrete geometric averaging**.

The geometric average over $n$ equally-spaced observation dates $t_i = iT/n$ for $i = 1, \ldots, n$ is defined as:

$$
G = \left( \prod_{i=1}^{n} S_{t_i} \right)^{1/n} = \exp\!\left( \frac{1}{n} \sum_{i=1}^{n} \ln S_{t_i} \right)
$$

The terminal payoff functions are:

$$
H_{\text{call}}(G) = \max(G - K, 0), \qquad H_{\text{put}}(G) = \max(K - G, 0)
$$

The number of observations $n$ is a parameter of the contract. The time-zero spot $S_0$ is not included in the average; observations begin at $t_1 = T/n$.

**Why geometric, not arithmetic.** The arithmetic-average Asian is the more commonly traded form in practice. We restrict v0.1 to the geometric case because it admits a closed-form analytical solution (Kemna and Vorst, 1990) that serves as ground truth for the methodology. Arithmetic-average Asians have no general closed form and are out of scope at this version; they are a natural extension once the geometric framework is validated.

### 4.2 Underlying model

The underlying $S_t$ is modelled as a geometric Brownian motion under the risk-neutral measure $\mathbb{Q}$, as specified in section 2.1. No assumptions beyond §2.1 are introduced here.

The defining property that makes the geometric Asian tractable is that the geometric average of jointly log-normal random variables is itself log-normal. Specifically, under GBM, $\ln G$ is normally distributed:

$$
\ln G \;\sim\; \mathcal{N}\!\left( \ln S_0 + \mu_G T, \; \sigma_G^2 T \right)
$$

with parameters:

$$
\mu_G = \left( r - q - \tfrac{1}{2}\sigma^2 \right) \frac{n+1}{2n}
$$

$$
\sigma_G^2 = \sigma^2 \, \frac{(n+1)(2n+1)}{6 n^2}
$$

These are derived from the GBM dynamics of $S_t$ at the observation times and the covariance structure $\mathrm{Cov}(\ln S_{t_i}, \ln S_{t_j}) = \sigma^2 \min(t_i, t_j)$. As $n \to \infty$, the discrete parameters converge to the continuous-averaging limits $\mu_G \to (r - q - \sigma^2/2)/2$ and $\sigma_G^2 \to \sigma^2/3$.

### 4.3 Classical benchmark: Kemna–Vorst closed-form

Since $G$ is log-normal under the risk-neutral measure with parameters $(\mu_G T, \sigma_G^2 T)$, the price of a fixed-strike geometric Asian call is given by Black's formula on the forward price of $G$:

$$
C_{\text{geo}}(S_0, K, T) = e^{-rT} \left[ F_G \, N(d_1) - K \, N(d_2) \right]
$$

where the forward price of the geometric average is:

$$
F_G = S_0 \, e^{(\mu_G + \sigma_G^2 / 2) T}
$$

and:

$$
d_1 = \frac{\ln(F_G / K) + \tfrac{1}{2} \sigma_G^2 T}{\sigma_G \sqrt{T}}, \qquad d_2 = d_1 - \sigma_G \sqrt{T}
$$

The put price follows by put–call parity for forward-based pricing:

$$
P_{\text{geo}}(S_0, K, T) = C_{\text{geo}}(S_0, K, T) - e^{-rT} (F_G - K)
$$

**Role in the methodology.** Kemna–Vorst is the analytical ground truth for fixed-strike geometric Asian options under the BSM model, on the same basis as Black–Scholes is the ground truth for European options. All other implementations are validated against this formula within its scope.

The same model-risk caveat applies: this is exact under GBM with constant parameters; market prices of average-rate products show deviations driven by realised volatility dynamics that are model limitations, not implementation errors.

### 4.4 Competing classical method: Monte Carlo with variance reduction

Even though closed-form pricing is available for the geometric Asian, Monte Carlo is what banks actually run in production for path-dependent products generally, because most cases of practical interest (arithmetic Asian, lookbacks, barriers) have no closed form. Including MC here serves two purposes: it provides a realistic performance comparator for the quantum approach, and it exercises the broader framework on path-simulation problems that will be needed when scope expands.

**Standard estimator.** Generate $N$ independent paths $\{S_{t_i}^{(k)}\}_{i=1, k=1}^{n, N}$ under risk-neutral GBM dynamics. For each path $k$, compute the geometric average $G^{(k)}$ and the discounted payoff. The MC price estimator is:

$$
\hat{C}_{\text{MC}} = \frac{e^{-rT}}{N} \sum_{k=1}^{N} H(G^{(k)})
$$

with standard error $\hat{\sigma} / \sqrt{N}$, where $\hat{\sigma}$ is the sample standard deviation of the discounted payoffs. The estimator converges at the canonical $\mathcal{O}(1/\sqrt{N})$ Monte Carlo rate.

**Antithetic variates.** For each Brownian path $W$ generated, the platform also generates the antithetic path $-W$ and averages the payoffs across the pair. For payoffs that are monotone in $W$ (which Asian payoffs effectively are), antithetic pairing reduces estimator variance at modest computational overhead. The empirical variance reduction is reported alongside each benchmark result rather than assumed.

**Control variates.** The platform supports a control variate using the underlying terminal price $S_T$, whose risk-neutral expectation is known analytically: $\mathbb{E}^{\mathbb{Q}}[S_T] = S_0 e^{(r - q)T}$. The control variate estimator is:

$$
\hat{C}_{\text{CV}} = \hat{C}_{\text{MC}} - \beta \left( \frac{1}{N} \sum_{k=1}^{N} S_T^{(k)} - S_0 e^{(r-q)T} \right)
$$

with $\beta$ estimated from the same sample as the ratio of sample covariance to sample variance. The European call on $S_T$ is also available as an alternative control with stronger correlation to the Asian payoff and a known Black–Scholes reference price.

**Specified parameters.** The MC implementation exposes the path count $N$, the number of observations $n$, the choice of variance-reduction techniques, and the simulation scheme. Exact GBM simulation at observation times is used by default, since $S_{t_i}$ has a known closed-form distribution under GBM and Euler discretisation is unnecessary at this scope.

### 4.5 Quantum approach: QAE on the geometric average distribution

The geometric Asian admits a particularly clean quantum treatment because the marginal distribution of $G$ is known in closed form. Rather than simulating the full path inside the quantum circuit, the implementation loads the marginal log-normal distribution of $G$ directly, using the parameters derived in §4.2, and applies the same payoff-encoding and amplitude-estimation framework as the European case.

The four stages are:

1. **Distribution loading.** The log-normal distribution of $G$ with parameters $(\mu_G T, \sigma_G^2 T)$ is discretised into $2^n$ points using $n$ qubits, and the resulting probability vector is loaded into the amplitude register $|\psi\rangle$.
2. **Payoff encoding.** Identical to the European case in §3.4: a controlled rotation maps the payoff $\max(G - K, 0)$ to an ancilla rotation angle using the linear approximation of Woerner & Egger (2019).
3. **Amplitude estimation.** Iterative Quantum Amplitude Estimation (IQAE) is applied to the prepared state, on the same protocol as §3.4.
4. **Decoding.** The estimated amplitude is rescaled to the expected payoff and multiplied by $e^{-rT}$.

In effect, this reduces the geometric Asian to "European pricing on a transformed underlying." The reduction is exact because of the log-normality of $G$. For payoffs where the path-functional distribution is *not* tractable in closed form (notably the arithmetic average), this shortcut does not apply and a full quantum path simulation is required. That case is out of scope at v0.1.

**Theoretical complexity.** Inherits the same $\mathcal{O}(1/\varepsilon)$ scaling as the European case, subject to the same caveats on distribution loading. Because $G$ has lower volatility than $S_T$ (for $n > 1$, $\sigma_G^2 < \sigma^2$), the loaded distribution is narrower than the European analogue, which may affect the optimal choice of discretisation parameters.

**Specified parameters.** Same parameter surface as §3.4 (qubits, target precision, confidence level, shot budget, backend), with the addition of $n$ (number of averaging observations) which affects $\mu_G$ and $\sigma_G$ but not the quantum circuit structure.

### 4.6 Sensitivities (Greeks)

Greeks for the geometric Asian are computed on the same dual basis as in §3.5:

- **Analytical Greeks from Kemna–Vorst.** Because the closed-form price is essentially Black's formula on the forward price of $G$, the analytical Greeks follow from the Black-76 expressions evaluated at the KV-adjusted parameters $(F_G, \sigma_G)$. The platform computes Delta, Gamma, Vega, Theta, and Rho on this basis.
- **Quantum Greeks via finite differences.** Identical protocol to §3.5: central differences for first-order Greeks, three-point central differences for Gamma, adaptive step-size selection driven by QAE precision.

**A subtlety specific to the Asian case.** Vega is sensitivity to the underlying volatility $\sigma$, but the Kemna–Vorst price depends on the derived quantity $\sigma_G$. The chain rule connecting them,

$$
\frac{\partial \sigma_G}{\partial \sigma} = \sqrt{\frac{(n+1)(2n+1)}{6n^2}},
$$

must be applied consistently in both the analytical and finite-difference implementations. The platform exposes the underlying-vol Vega ($\partial V / \partial \sigma$) as the user-facing quantity, with $\partial V / \partial \sigma_G$ available as a diagnostic. The same care applies to Rho with respect to the underlying $r$, which affects both $F_G$ (through $\mu_G$) and the discount factor.

### 4.7 Market data source

*To be specified, on the same template as §3.6.*

### 4.8 Known limitations and out-of-scope

The limitations stated in §3.7 (distribution loading complexity, discretisation error, payoff encoding approximation, single-underlying restriction, constant model parameters, hardware execution) apply unchanged to this product. The following are specific to Asian options:

- **Geometric averaging only.** Arithmetic-average Asians, the more commonly traded form, are not supported at v0.1. The arithmetic case requires either an approximation method (Turnbull–Wakeman, Curran, Levy, etc.) on the classical side, or full quantum path simulation on the quantum side. Both are natural v2 extensions.
- **Fixed strike only.** Average-strike Asians (where the average replaces the strike, not the underlying) are out of scope at v0.1.
- **Equally-spaced observations only.** Custom observation schedules require generalisation of the moment formulae in §4.2 and are out of scope at v0.1.
- **Discrete averaging.** Continuous-averaging Asians are not separately implemented; the discrete case with large $n$ approximates the continuous limit and is reported as such.

## 5. Validation principles

This section states the principles under which results produced by the platform are validated. Concrete acceptance criteria, statistical protocols, and regime-sweep parameters are specified in the separate **Test Procedure** document, which is versioned alongside this methodology.

### 5.1 Validation philosophy

Every implementation in the platform — classical benchmark, competing classical method, or quantum approach — is validated on three independent axes:

- **Correctness against analytical ground truth.** Where a closed-form solution exists (Black–Scholes for Europeans, Kemna–Vorst for geometric Asians), implementations are validated against it as the primary check. This isolates implementation errors from model and methodology questions.
- **Statistical and regime behaviour.** Implementations are exercised across a parameter regime (strike position, maturity, volatility, problem size) to characterise where they perform well, where they degrade, and where the crossover between competing methods sits. Single-point benchmarks are not sufficient.
- **Reproducibility.** Every published result must regenerate bit-for-bit from its recorded configuration, as stated in §2.3. A result that cannot be reproduced is not a result.

### 5.2 Validation surfaces by method type

**Analytical methods** (Black–Scholes, Kemna–Vorst, analytical Greeks) are validated against:

- Floating-point precision of the implementation (numerical sanity).
- Put–call parity and other structural identities.
- Reference implementations from established libraries (`scipy`, `QuantLib`) where available.

These are exact within their model, so the validation question is implementation correctness, not statistical accuracy.

**Stochastic methods** (Monte Carlo with variance reduction, QAE) are validated against:

- Analytical ground truth on the same problem instances.
- Self-consistency: the stated standard error must match empirical variation across independent runs.
- Convergence properties: error scaling must match theoretical expectation ($\mathcal{O}(N^{-1/2})$ for Monte Carlo, $\mathcal{O}(\varepsilon^{-1})$ for QAE) as resources scale.

### 5.3 Regime analysis

Every benchmark identifies the parameter regime in which its result holds, and presents results across the regime grid rather than at single points. Regime axes typically include:

- Moneyness ($S_0 / K$ ratio: deep ITM, ATM, deep OTM)
- Maturity ($T$: short, medium, long-dated)
- Volatility ($\sigma$: low, moderate, high)
- Implementation parameters (qubit count $n$, path count $N$, target precision $\varepsilon$)

For comparisons between methods — notably quantum versus competing classical — the **crossover regime**, where the methods break even on accuracy at equal resource budget, is reported explicitly. Regimes where the quantum approach does *not* outperform the classical are reported on the same basis as those where it does.

### 5.4 Audit trail and methodology version-pinning

Every published result records:

- The methodology version under which it was produced (e.g., `v0.1.2`).
- The implementation version (Git commit hash).
- The configuration that produced the result, in full.
- The environment (Python version, key library versions, operating system, simulator backend).

When the methodology document is revised, prior results remain valid under their stated version. A change that invalidates prior results is a major version increment (per §1.4) and the affected results are explicitly retired in the changelog.

### 5.5 Forward reference

The test procedure document specifies:

- Acceptance criteria (RMSE thresholds against ground truth) for each implementation.
- The full statistical battery (trial counts, confidence interval methods, robustness checks).
- The regime-sweep parameter grids.
- Failure-mode tests and the errors they should produce.
- The adaptive step-size protocol for finite-difference Greeks.
- The regression policy for code changes.

The methodology document and the test procedure document together define the validation contract under which results may be published.

## 6. Bibliography

**Foundational textbooks (prerequisites and reference)**

- Hull, J. C. (2021). *Options, Futures, and Other Derivatives* (11th ed.). Pearson. The standard reference covering vanilla and exotic options, Greeks, Monte Carlo methods, and variance reduction techniques.
- Shreve, S. E. (2004). *Stochastic Calculus for Finance II: Continuous-Time Models.* Springer. Rigorous treatment of risk-neutral pricing, geometric Brownian motion, and the Black–Scholes framework.
- Nielsen, M. A., & Chuang, I. L. (2010). *Quantum Computation and Quantum Information* (10th anniversary ed.). Cambridge University Press. The canonical textbook for quantum computing fundamentals, including qubits, circuits, and the Quantum Fourier Transform.

**Classical finance foundations**

- Black, F., & Scholes, M. (1973). *The pricing of options and corporate liabilities.* Journal of Political Economy, 81(3), 637–654.
- Kemna, A. G. Z., & Vorst, A. C. F. (1990). *A pricing method for options based on average asset values.* Journal of Banking and Finance, 14(1), 113–129.
- Glasserman, P. (2003). *Monte Carlo Methods in Financial Engineering.* Springer. (Canonical reference for Monte Carlo variance reduction techniques.)

**Quantum algorithms**

- Brassard, G., Høyer, P., Mosca, M., & Tapp, A. (2002). *Quantum amplitude amplification and estimation.* Contemporary Mathematics, 305, 53–74.
- Grinko, D., Gacon, J., Zoufal, C., & Woerner, S. (2021). *Iterative quantum amplitude estimation.* npj Quantum Information, 7(1), 52.

**Quantum applications to finance**

- Stamatopoulos, N., Egger, D. J., Sun, Y., Zoufal, C., Iten, R., Shen, N., & Woerner, S. (2020). *Option pricing using quantum computers.* Quantum, 4, 291.
- Woerner, S., & Egger, D. J. (2019). *Quantum risk analysis.* npj Quantum Information, 5(1), 15.
- Egger, D. J., Gutiérrez, R. G., Mestre, J. C., & Woerner, S. (2020). *Credit risk analysis using quantum computers.* IEEE Transactions on Computers, 70(12), 2136–2145.
