"""Kalman-filter (time-varying) betas with random-walk betas and a constant alpha.

Specification: ``docs/specs/kalman-betas.md`` (KB0-KB8).

Model (KB1.1): ``y_t = x_t' theta_t + e_t`` with ``x_t = (1, f_t')'``,
``theta_t = theta_{t-1} + eta_t`` and ``eta_t ~ N(0, Q)``, ``Q = blockdiag(0, lambda R M)``, ``M``
the inverse sample covariance of the five factors. The first state is the OLS fit of the first
``b = 21`` rows (KB3, an exact diffuse start). The one hyperparameter ``lambda`` is chosen by
concentrated maximum likelihood on a grid (KB2.1-KB2.2) and re-estimated every 252 rows
(KB2.4): vintage ``j`` uses rows ``1 .. m_j`` with ``m_j = 504 + 252 j``, re-runs the filter from
row 1 and supplies the outputs stamped ``m_j .. m_{j+1} - 1``. Every output stamped ``t``
therefore uses rows ``<= t`` only (M0.2, CODING_STANDARDS section 2). Only the forward filter
exists here: there is no smoother (KB4.1; the retrospective view is not built in v1).

Implementation: the recursion runs in "scale form" (``R = 1``, so ``Q = blockdiag(0, lambda M)``)
and is batched in numpy with the batch on the last axis. The grid pass runs every (vintage, grid
value) pair in one loop over rows (a vintage leaves the batch after its last estimation row);
the output pass runs one filter per vintage. The covariance update ``P - s s'`` with
``s = P x / sqrt(F)`` keeps ``P`` exactly symmetric, so no symmetrisation step is needed.

Pure: no I/O, no clock, no randomness. Inputs are not mutated. The test oracles (statsmodels
``MLEModel`` and ``RecursiveLS``) live in the tests only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal

import numpy as np
from numpy.typing import NDArray

from factordesk.analytics.regression import Z_975

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]

BURN_IN_ROWS: Final = 21
"""``b``: rows of the initial OLS fit (KB3)."""
TRAINING_ROWS: Final = 504
"""``B0``: rows of the first hyperparameter estimate and the first stamp (KB2.3)."""
REESTIMATE_EVERY: Final = 252
"""``h``: rows between vintages (KB2.4)."""
LAMBDA_GRID: Final[FloatArray] = np.concatenate([[0.0], 10.0 ** (-9.0 + np.arange(57) / 8.0)])
"""``{0} U {10^-9, 10^-8.875, ..., 10^-2}``: 58 values (KB2.2). Index 0 is exactly 0."""
GRID_STEP_LOG10: Final = 0.125
STUDENT_NU: Final = 5.0
"""Degrees of freedom of the Student-t weighted update (KB6.1); fixed, not estimated."""
MAX_CONDITION: Final = 1e12
"""Largest condition number of the equilibrated burn-in design (KB8.1)."""
WARNING_UPPER_BOUND: Final = "kalman_lambda_at_upper_bound"
STATE_SIZE: Final = 6
N_FACTORS: Final = 5

ErrorModel = Literal["gaussian", "student_t5"]
LambdaBound = Literal["zero", "upper", "none"]
KalmanStatus = Literal["ok", "insufficient_data", "failed"]


@dataclass(frozen=True)
class VintageFit:
    """Hyperparameters of one vintage (KB2.4). Row numbers are 1-based positions in the sample."""

    index: int
    rows: int
    """``m_j``: the vintage is estimated on rows ``1 .. m_j``; its first stamp is row ``m_j``."""
    lam: float
    lam_at_bound: LambdaBound
    resid_var: float
    """``R_hat``: residual variance at ``lam``, decimal^2 per day."""
    w_eq: float | None
    """Equivalent rolling window ``2 / sqrt(lam)`` in rows; ``None`` when ``lam == 0`` (KB2.5)."""
    valid_from: int
    valid_to: int
    """First and last row (1-based) stamped by this vintage."""


@dataclass(frozen=True)
class KalmanResult:
    """Output of ``kalman_betas``. Arrays have one entry per sample row; warm-up rows are NaN
    (and ``vintage_index`` is -1 there). Filtered values: row ``t`` uses rows ``<= t`` only."""

    status: KalmanStatus
    reason: str | None
    n: int
    error_model: ErrorModel
    alpha: FloatArray
    betas: FloatArray
    band_low: FloatArray
    band_high: FloatArray
    ex_ante: FloatArray
    """Predicted betas ``a_{t|t-1}`` (rows ``<= t-1``); NaN at the first stamp (KB0.3)."""
    vintage_index: IntArray
    vintages: tuple[VintageFit, ...]
    latest_sd: FloatArray
    """Model standard deviation of the five betas at the last row (``sqrt(R_hat P_jj)``)."""
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class FilterPath:
    """One filter run at a fixed ``lam`` (scale form: ``R = 1``). Row ``i`` (0-based) holds the
    state after absorbing row ``i``; rows before ``burn_in - 1`` are NaN."""

    states: FloatArray
    """Filtered state ``a_{t|t}``, shape ``(n, 6)``: alpha then the five betas."""
    cov_scale: FloatArray
    """Filtered covariance in scale units (multiply by ``R_hat`` for decimal^2), ``(n, 6, 6)``."""
    innovations: FloatArray
    """``v_t`` (NaN for the burn-in rows), shape ``(n,)``."""
    variances: FloatArray
    """``F_t`` (scale form; includes the t-weight when one is used), shape ``(n,)``."""
    r_hat: float
    loglik: float
    """Conditional concentrated log-likelihood ``logL_c`` over rows ``burn_in + 1 .. n`` (KB2.1)."""


# ---------------------------------------------------------------------------- pure helpers
def vintage_rows(n: int) -> tuple[int, ...]:
    """``m_j = 504 + 252 j`` while ``m_j <= n`` (KB2.4). Empty when ``n < 504``."""
    return tuple(range(TRAINING_ROWS, n + 1, REESTIMATE_EVERY))


def equivalent_window(lam: float) -> float | None:
    """``2 / sqrt(lam)`` rows (KB2.5); ``None`` for ``lam == 0`` (no drift: all data so far)."""
    return None if lam <= 0.0 else 2.0 / math.sqrt(lam)


def t_weight(z_squared: FloatArray, nu: float) -> FloatArray:
    """Observation-variance weight ``max(1, (nu + z^2) / (nu + 1))`` of the t update (KB6.1)."""
    return np.maximum(1.0, (nu + z_squared) / (nu + 1.0))


def refine_lambda(grid: FloatArray, loglik: FloatArray) -> tuple[float, LambdaBound]:
    """Grid maximiser of ``loglik``, refined by one parabolic step (KB2.2).

    The grid maximiser is kept exactly when it is 0 (reported ``zero``), the first positive value
    (no log-spaced left neighbour) or the largest value (reported ``upper``). An interior
    positive maximiser moves by one parabolic step in ``log10 lambda`` through the three
    neighbouring grid points, clipped to one grid step.
    """
    best = int(np.argmax(loglik))
    last = len(grid) - 1
    if best == 0:
        return 0.0, "zero"
    if best == last:
        return float(grid[last]), "upper"
    if best == 1:
        return float(grid[1]), "none"
    lo, mid, hi = (float(v) for v in loglik[best - 1 : best + 2])
    curvature = lo - 2.0 * mid + hi
    if not (curvature < 0.0) or not math.isfinite(curvature):
        return float(grid[best]), "none"
    step = float(np.log10(grid[best + 1]) - np.log10(grid[best]))
    shift = min(max(0.5 * (lo - hi) / curvature, -1.0), 1.0) * step
    return float(10.0 ** (np.log10(grid[best]) + shift)), "none"


def _burn_in(y: FloatArray, x: FloatArray, rows: int) -> tuple[FloatArray, FloatArray] | None:
    """OLS on the first ``rows`` rows: ``(a, P)`` with ``P = (X'X)^-1`` (scale form), or ``None``
    when the equilibrated design is singular (condition above ``MAX_CONDITION``)."""
    xb = x[:rows]
    norms = np.sqrt(np.einsum("ij,ij->j", xb, xb))
    if not np.all(np.isfinite(norms)) or np.any(norms == 0.0):
        return None
    scaled = xb / norms
    if not np.linalg.cond(scaled.T @ scaled) < MAX_CONDITION:
        return None
    gram_inv = np.linalg.inv(xb.T @ xb)
    gram_inv = 0.5 * (gram_inv + gram_inv.T)
    return gram_inv @ (xb.T @ y[:rows]), gram_inv


def _drift_shape(f: FloatArray, rows: int) -> FloatArray | None:
    """``M = Sigma_f^-1`` from the first ``rows`` factor rows (``ddof = 1``), or ``None`` when
    the covariance is singular."""
    cov = np.atleast_2d(np.cov(f[:rows], rowvar=False, ddof=1))
    scale = np.sqrt(np.diag(cov))
    if not np.all(np.isfinite(scale)) or np.any(scale <= 0.0):
        return None
    corr = cov / np.outer(scale, scale)
    if not np.linalg.cond(corr) < MAX_CONDITION:
        return None
    inv = np.linalg.inv(cov)
    return 0.5 * (inv + inv.T)


# ---------------------------------------------------------------------------- batched filters
def _fresh(a0: FloatArray, p0: FloatArray, size: int) -> tuple[FloatArray, FloatArray]:
    """State ``(6, B)`` and covariance ``(6, 6, B)`` of ``size`` copies of the burn-in fit.

    The batch is the LAST axis, so every elementwise operation runs over contiguous memory.
    """
    a = np.repeat(a0[:, None], size, axis=1)
    p = np.repeat(p0[:, :, None], size, axis=2)
    return a, p


def _grid_pass(
    y: FloatArray,
    x: FloatArray,
    m_inv: FloatArray,
    ms: tuple[int, ...],
    start: tuple[FloatArray, FloatArray],
    burn_in: int,
    grid: FloatArray = LAMBDA_GRID,
) -> tuple[FloatArray, FloatArray]:
    """Sums of ``v^2 / F`` and ``ln F`` for every (vintage, ``grid`` value) pair, shape ``(V, G)``.

    Vintage ``j`` contributes rows ``burn_in + 1 .. m_j`` (1-based). Batch elements are ordered by
    descending vintage, so the elements still active at row ``i`` are a prefix; whenever a vintage
    drops out the arrays are compacted to the prefix (32 copies in a 33-year history).
    """
    a0, p0 = start
    v_count, g_count = len(ms), len(grid)
    size = v_count * g_count
    # element e = (V - 1 - j) * G + g
    drift_full = (
        (grid[None, :, None, None] * m_inv[::-1][:, None, :, :])
        .reshape(size, N_FACTORS, N_FACTORS)
        .transpose(1, 2, 0)
    )
    a, p = _fresh(a0, p0, size)
    drift = np.ascontiguousarray(drift_full)
    tmp = np.empty_like(p)
    ssq = np.zeros(size)
    slog = np.zeros(size)
    last = ms[-1]
    active = (v_count - np.searchsorted(np.asarray(ms), np.arange(last), side="right")) * g_count
    current = size
    for i in range(burn_in, last):
        k = int(active[i])
        if k != current:
            current = k
            a = np.ascontiguousarray(a[:, :k])
            p = np.ascontiguousarray(p[:, :, :k])
            drift = np.ascontiguousarray(drift[:, :, :k])
            tmp = np.empty_like(p)
        p[1:, 1:] += drift
        xi = x[i]
        px = (xi @ p.reshape(STATE_SIZE, -1)).reshape(STATE_SIZE, k)
        var = xi @ px
        var += 1.0
        innov = y[i] - xi @ a
        ssq[:k] += innov * innov / var
        root = np.sqrt(var)
        slog[:k] += np.log(var)
        s = px / root
        a += s * (innov / root)
        np.multiply(s[:, None, :], s[None, :, :], out=tmp)
        p -= tmp
    return ssq.reshape(v_count, g_count)[::-1], slog.reshape(v_count, g_count)[::-1]


@dataclass(frozen=True)
class _Pass:
    """What ``_output_pass`` records: the picked state and covariance diagonal per row, and the
    residual-variance numerator at the snapshot rows."""

    states: FloatArray
    diag: FloatArray
    ssq_at: FloatArray


def _output_pass(
    y: FloatArray,
    x: FloatArray,
    lam: FloatArray,
    m_inv: FloatArray,
    last_row: IntArray,
    pick: IntArray,
    snapshot_row: IntArray,
    start: tuple[FloatArray, FloatArray],
    burn_in: int,
    *,
    nu: float | None = None,
    r_hat: FloatArray | None = None,
) -> _Pass:
    """One filter per batch element (its own ``lam`` and ``M``), all rows in one loop.

    ``last_row[e]`` is the last 0-based row element ``e`` must process; elements are ordered by
    descending ``last_row``. ``pick[i]`` is the element whose state is recorded at row ``i``
    (-1: none; the element must still be active at ``i``). ``snapshot_row[e]`` is the row after
    which ``sum v^2 / F`` of element ``e`` is stored (-1: never). With ``nu`` the update uses the
    t weight (KB6.1) with ``r_hat`` per element.
    """
    a0, p0 = start
    size = len(lam)
    n = len(y)
    a, p = _fresh(a0, p0, size)
    drift = np.ascontiguousarray((lam[:, None, None] * m_inv).transpose(1, 2, 0))
    rhat = None if r_hat is None else np.asarray(r_hat, dtype=np.float64)
    tmp = np.empty_like(p)
    ssq = np.zeros(size)
    snap = np.full(size, np.nan)
    states = np.full((n, STATE_SIZE), np.nan)
    diag = np.full((n, STATE_SIZE), np.nan)
    at_row: dict[int, list[int]] = {}
    for e, row in enumerate(snapshot_row.tolist()):
        if row >= 0:
            at_row.setdefault(row, []).append(e)
    idx = np.arange(STATE_SIZE)
    if pick[burn_in - 1] >= 0:
        e = int(pick[burn_in - 1])
        states[burn_in - 1] = a[:, e]
        diag[burn_in - 1] = p[idx, idx, e]
    end = int(last_row.max()) + 1
    active = np.searchsorted(-last_row, -np.arange(end), side="right")
    current = size
    for i in range(burn_in, end):
        k = int(active[i])
        if k != current:
            current = k
            a = np.ascontiguousarray(a[:, :k])
            p = np.ascontiguousarray(p[:, :, :k])
            drift = np.ascontiguousarray(drift[:, :, :k])
            tmp = np.empty_like(p)
        p[1:, 1:] += drift
        xi = x[i]
        px = (xi @ p.reshape(STATE_SIZE, -1)).reshape(STATE_SIZE, k)
        quad = xi @ px
        var0 = quad + 1.0
        innov = y[i] - xi @ a
        ssq[:k] += innov * innov / var0
        if nu is None or rhat is None:
            var = var0
        else:
            var = quad + t_weight(innov * innov / (rhat[:k] * var0), nu)
        root = np.sqrt(var)
        s = px / root
        a += s * (innov / root)
        np.multiply(s[:, None, :], s[None, :, :], out=tmp)
        p -= tmp
        for e in at_row.get(i, ()):
            snap[e] = ssq[e]
        e = int(pick[i])
        if e >= 0:
            states[i] = a[:, e]
            diag[i] = p[idx, idx, e]
    return _Pass(states, diag, snap)


# ---------------------------------------------------------------------------- public entry points
def filter_path(
    y: FloatArray,
    f: FloatArray,
    lam: float,
    *,
    drift_shape: FloatArray | None = None,
    burn_in: int = BURN_IN_ROWS,
    nu: float | None = None,
    r_hat: float | None = None,
) -> FilterPath:
    """Run the filter once at a fixed ``lam`` over all rows (scale form, ``R = 1``).

    ``drift_shape`` is ``M`` (default: ``Sigma_f^-1`` of all rows, ``ddof = 1``). With ``nu`` the
    Student-t weighted update of KB6.1 is used; its ``z^2`` needs ``r_hat`` (the Gaussian ML
    value of the vintage). Raises ``ValueError`` when the burn-in design or ``M`` is singular.
    """
    yv, fv = _check_inputs(y, f)
    x = np.column_stack([np.ones(len(yv)), fv])
    n = len(yv)
    start = _burn_in(yv, x, burn_in)
    if start is None:
        raise ValueError("singular burn-in design")
    m = _drift_shape(fv, n) if drift_shape is None else np.asarray(drift_shape, dtype=np.float64)
    if m is None:
        raise ValueError("singular factor covariance")
    return _single_path(
        yv,
        x,
        float(lam),
        m,
        start,
        burn_in,
        nu=nu,
        r_hat=None if r_hat is None else float(r_hat),
    )


def _single_path(
    y: FloatArray,
    x: FloatArray,
    lam: float,
    m_inv: FloatArray,
    start: tuple[FloatArray, FloatArray],
    burn_in: int,
    *,
    nu: float | None,
    r_hat: float | None,
) -> FilterPath:
    """Single run that keeps the whole path (tests, diagnostics: TKB01-TKB05, TKB12)."""
    a0, p0 = start
    n = len(y)
    drift = lam * m_inv
    a = a0.copy()
    p = p0.copy()
    states = np.full((n, STATE_SIZE), np.nan)
    cov = np.full((n, STATE_SIZE, STATE_SIZE), np.nan)
    innov_out = np.full(n, np.nan)
    var_out = np.full(n, np.nan)
    states[burn_in - 1] = a
    cov[burn_in - 1] = p
    ssq = 0.0
    slog = 0.0
    for i in range(burn_in, n):
        p[1:, 1:] += drift
        xi = x[i]
        px = p @ xi
        var0 = float(px @ xi) + 1.0
        innov = float(y[i] - a @ xi)
        ssq += innov * innov / var0
        if nu is None or r_hat is None:
            var = var0
        else:
            z2 = innov * innov / (r_hat * var0)
            var = float(px @ xi) + float(t_weight(np.array([z2]), nu)[0])
        slog += math.log(var0 if nu is None else var)
        root = math.sqrt(var)
        s = px / root
        a = a + s * (innov / root)
        p = p - np.outer(s, s)
        states[i] = a
        cov[i] = p
        innov_out[i] = innov
        var_out[i] = var
    rows = n - burn_in
    rhat = ssq / rows
    loglik = (
        -0.5 * rows * (math.log(2.0 * math.pi) + math.log(rhat) + 1.0) - 0.5 * slog
        if rhat > 0.0
        else -math.inf
    )
    return FilterPath(states, cov, innov_out, var_out, rhat, loglik)


def kalman_betas(
    y: FloatArray, f: FloatArray, *, error_model: ErrorModel = "gaussian"
) -> KalmanResult:
    """Filtered Kalman betas of excess returns ``y`` on factors ``f`` (shape ``(n, 5)``).

    Statuses (KB8.3): ``insufficient_data`` when ``n < 504`` (reason ``kalman_needs_504_rows``);
    ``failed`` with reason ``singular_burn_in`` when the first 21 rows do not identify the six
    state elements, or ``singular_factor_covariance`` when a vintage's factor covariance is
    singular; otherwise ``ok``, with warning ``kalman_lambda_at_upper_bound`` when a vintage's
    maximiser is the largest grid value.
    """
    yv, fv = _check_inputs(y, f)
    n = len(yv)
    empty_f = np.full((n, N_FACTORS), np.nan)
    empty = KalmanResult(
        status="ok",
        reason=None,
        n=n,
        error_model=error_model,
        alpha=np.full(n, np.nan),
        betas=empty_f,
        band_low=empty_f,
        band_high=empty_f,
        ex_ante=empty_f,
        vintage_index=np.full(n, -1, dtype=np.int64),
        vintages=(),
        latest_sd=np.full(N_FACTORS, np.nan),
        warnings=(),
    )
    ms = vintage_rows(n)
    if not ms:
        return _with(empty, status="insufficient_data", reason=f"kalman_needs_{TRAINING_ROWS}_rows")
    x = np.column_stack([np.ones(n), fv])
    start = _burn_in(yv, x, BURN_IN_ROWS)
    if start is None:
        return _with(empty, status="failed", reason="singular_burn_in")
    shapes = [_drift_shape(fv, m) for m in ms]
    if any(s is None for s in shapes):
        return _with(empty, status="failed", reason="singular_factor_covariance")
    m_inv = np.stack([s for s in shapes if s is not None])

    # 1. hyperparameters: concentrated likelihood on the grid, per vintage
    ssq, slog = _grid_pass(yv, x, m_inv, ms, start, BURN_IN_ROWS)
    rows_used = np.asarray(ms, dtype=np.float64) - BURN_IN_ROWS
    r_grid = ssq / rows_used[:, None]
    with np.errstate(divide="ignore"):
        loglik = np.where(
            r_grid > 0.0,
            -0.5 * rows_used[:, None] * (math.log(2.0 * math.pi) + np.log(r_grid) + 1.0)
            - 0.5 * slog,
            -np.inf,
        )
    chosen = [refine_lambda(LAMBDA_GRID, loglik[j]) for j in range(len(ms))]
    lam = np.array([c[0] for c in chosen])

    # 2. outputs: one filter per vintage, from row 1, over the rows that vintage stamps
    v_count = len(ms)
    ends = [ms[j + 1] - 1 if j + 1 < v_count else n for j in range(v_count)]  # last stamp (1-based)
    order = np.arange(v_count)[::-1]  # descending vintage = descending last row
    pick = np.full(n, -1, dtype=np.int64)
    for pos, j in enumerate(order):
        pick[ms[j] - 1 : ends[j]] = pos
    last_row = np.array([ends[j] - 1 for j in order], dtype=np.int64)
    snapshot = np.array([ms[j] - 1 for j in order], dtype=np.int64)
    first = _output_pass(
        yv, x, lam[order], m_inv[order], last_row, pick, snapshot, start, BURN_IN_ROWS
    )
    r_hat = first.ssq_at[np.argsort(order)] / rows_used
    paths = first
    if error_model == "student_t5":
        paths = _output_pass(
            yv,
            x,
            lam[order],
            m_inv[order],
            last_row,
            pick,
            np.full(v_count, -1, dtype=np.int64),
            start,
            BURN_IN_ROWS,
            nu=STUDENT_NU,
            r_hat=r_hat[order],
        )
    return _assemble(n, ms, ends, lam, chosen, r_hat, paths, error_model)


def _assemble(
    n: int,
    ms: tuple[int, ...],
    ends: list[int],
    lam: FloatArray,
    chosen: list[tuple[float, LambdaBound]],
    r_hat: FloatArray,
    paths: _Pass,
    error_model: ErrorModel,
) -> KalmanResult:
    vintage_index = np.full(n, -1, dtype=np.int64)
    scale = np.full(n, np.nan)
    for j, m in enumerate(ms):
        vintage_index[m - 1 : ends[j]] = j
        scale[m - 1 : ends[j]] = r_hat[j]
    stamped = vintage_index >= 0
    alpha = paths.states[:, 0].copy()
    betas = paths.states[:, 1:].copy()
    sd = np.sqrt(scale[:, None] * paths.diag[:, 1:])
    band_low = betas - Z_975 * sd
    band_high = betas + Z_975 * sd
    ex_ante = np.full_like(betas, np.nan)
    # Random walk: the prediction for row t is the filtered state of row t-1, which already comes
    # from the vintage valid at t-1 (KB2.4). No vintage is valid at row B0 - 1, so the first
    # stamp has no ex-ante value.
    first_stamp = ms[0] - 1
    ex_ante[first_stamp + 1 :] = betas[first_stamp:-1]
    ex_ante[~stamped] = np.nan
    vintages = tuple(
        VintageFit(
            index=j,
            rows=m,
            lam=float(lam[j]),
            lam_at_bound=chosen[j][1],
            resid_var=float(r_hat[j]),
            w_eq=equivalent_window(float(lam[j])),
            valid_from=m,
            valid_to=ends[j],
        )
        for j, m in enumerate(ms)
    )
    warnings = (WARNING_UPPER_BOUND,) if any(v.lam_at_bound == "upper" for v in vintages) else ()
    return KalmanResult(
        status="ok",
        reason=None,
        n=n,
        error_model=error_model,
        alpha=alpha,
        betas=betas,
        band_low=band_low,
        band_high=band_high,
        ex_ante=ex_ante,
        vintage_index=vintage_index,
        vintages=vintages,
        latest_sd=sd[-1],
        warnings=warnings,
    )


def _with(base: KalmanResult, *, status: KalmanStatus, reason: str) -> KalmanResult:
    return KalmanResult(
        status=status,
        reason=reason,
        n=base.n,
        error_model=base.error_model,
        alpha=base.alpha,
        betas=base.betas,
        band_low=base.band_low,
        band_high=base.band_high,
        ex_ante=base.ex_ante,
        vintage_index=base.vintage_index,
        vintages=(),
        latest_sd=base.latest_sd,
        warnings=(),
    )


def _check_inputs(y: FloatArray, f: FloatArray) -> tuple[FloatArray, FloatArray]:
    yv = np.asarray(y, dtype=np.float64)
    fv = np.asarray(f, dtype=np.float64)
    if yv.ndim != 1 or fv.ndim != 2 or fv.shape != (len(yv), N_FACTORS):
        raise ValueError(f"expected y of shape (n,) and f of shape (n, {N_FACTORS})")
    if not (np.all(np.isfinite(yv)) and np.all(np.isfinite(fv))):
        raise ValueError("returns and factors must be finite")
    return yv, fv
