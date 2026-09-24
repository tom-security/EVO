"""Sélection naturelle (§3) : population, mutations, sélection, runs sauvegardés.

- Génération 0 : POP_SIZE créatures aléatoires (§2.5), évaluées 10 s (evo/batch.py).
- Génération g+1 : tri par score (§3.2), les SURVIVOR_FRACTION meilleures survivent avec
  leurs résultats (le moteur est déterministe : pas de réévaluation), chacune a 1 enfant
  muté (§3.3) ; seuls les enfants sont évalués.
- Graine par génération : default_rng([seed, g]) ; la reprise d'un run redonne donc
  exactement les mêmes générations.
- runs/<seed>/gen_XXXX.npz (génomes, résultats, lignée, stats), stats.csv, config.json,
  audit.csv (audit d'énergie du champion toutes les AUDIT_EVERY générations).
"""
import csv
import json
import math
import os
import time
from dataclasses import dataclass

import numpy as np

import config
from evo import batch
from evo import creature as cr

RESULT_KEYS = ("score", "height", "energy", "muscle_mass", "fallen")


# ---------------------------------------------------------------------------
# Population
# ---------------------------------------------------------------------------
@dataclass
class Population:
    lengths: np.ndarray    # (N, 7)
    strengths: np.ndarray  # (N, 2, 4, 2)
    period: np.ndarray     # (N,)
    targets: np.ndarray    # (N, K, 8)
    holds: np.ndarray      # (N, K, 4) bool

    FIELDS = ("lengths", "strengths", "period", "targets", "holds")

    def __len__(self):
        return len(self.period)

    def genome(self, i):
        return cr.Genome(self.lengths[i].copy(), self.strengths[i].copy(), float(self.period[i]),
                         self.targets[i].copy(), self.holds[i].copy())

    def to_genomes(self):
        return [self.genome(i) for i in range(len(self))]

    @classmethod
    def from_genomes(cls, genomes):
        return cls(np.stack([g.lengths for g in genomes]), np.stack([g.strengths for g in genomes]),
                   np.array([g.period for g in genomes], dtype=np.float64),
                   np.stack([g.targets for g in genomes]), np.stack([g.holds for g in genomes]).astype(bool))

    def take(self, idx):
        return Population(*(getattr(self, f)[idx].copy() for f in self.FIELDS))

    @classmethod
    def concat(cls, a, b):
        return cls(*(np.concatenate([getattr(a, f), getattr(b, f)]) for f in cls.FIELDS))

    def muscle_mass(self):
        return self.strengths.reshape(len(self), -1).sum(axis=1)


def random_population(rng, n):
    return Population.from_genomes([cr.random_genome(rng) for _ in range(n)])


def evaluate(pop):
    """Résultats de chaque créature (hauteur, énergie, masse musculaire, score, chute)."""
    res = batch.evaluate(pop.to_genomes(), duration=config.SIM_DURATION)
    return {k: res[k] for k in RESULT_KEYS}


# ---------------------------------------------------------------------------
# Mutations (§3.3)
# ---------------------------------------------------------------------------
def _mutate_values(values, sigma, low, high, rng):
    """Chaque gène muté avec P_MUT : bruit gaussien σ, ×BIG_FACTOR avec P_BIG, puis clamp."""
    mask = rng.random(values.shape) < config.P_MUT
    big = rng.random(values.shape) < config.P_BIG
    noise = rng.normal(0.0, 1.0, values.shape) * sigma * np.where(big, config.BIG_FACTOR, 1.0)
    return np.clip(values + np.where(mask, noise, 0.0), low, high)


def mutate(parents, rng):
    """Un enfant par parent : copie + mutations. Même suite de tirages → même résultat."""
    frac = config.MUT_SIGMA_FRAC
    lo, hi = config.LENGTH_FACTOR_RANGE
    ref = cr.reference_lengths()
    lengths = _mutate_values(parents.lengths, frac * ref * (hi - lo), ref * lo, ref * hi, rng)

    if config.SYMMETRIC_MORPHOLOGY:  # une seule moitié mutée, recopiée de l'autre côté
        half = _mutate_values(parents.strengths[:, 0], frac * config.S_MAX, 0.0, config.S_MAX, rng)
        strengths = np.stack([half, half], axis=1)
    else:
        strengths = _mutate_values(parents.strengths, frac * config.S_MAX, 0.0, config.S_MAX, rng)

    p_lo, p_hi = config.PERIOD_BOUNDS
    if config.PERIOD_MUTATION == "log":
        log_p = _mutate_values(np.log(parents.period), config.PERIOD_LOG_SIGMA,
                               math.log(p_lo), math.log(p_hi), rng)
        period = np.clip(np.exp(log_p), p_lo, p_hi)
    else:
        i_lo, i_hi = config.PERIOD_INIT
        period = _mutate_values(parents.period, frac * (i_hi - i_lo), p_lo, p_hi, rng)

    span = math.radians(config.TARGET_RANGE_DEG)
    targets = _mutate_values(parents.targets, frac * 2 * span, -span, span, rng)

    flips = rng.random(parents.holds.shape) < config.P_FLIP
    holds = parents.holds ^ flips
    return Population(lengths, strengths, period, targets, holds)


# ---------------------------------------------------------------------------
# Sélection (§3.1)
# ---------------------------------------------------------------------------
def ranking(scores):
    """Indices du meilleur au pire (tri stable ; un score NaN compte comme −∞)."""
    s = np.where(np.isfinite(scores), scores, -np.inf)
    return np.argsort(-s, kind="stable")


def next_generation(pop, results, rng, n_survivors=None):
    """Les n_survivors meilleures survivent (résultats conservés) + 1 enfant muté chacune."""
    n_survivors = int(round(len(pop) * config.SURVIVOR_FRACTION)) if n_survivors is None else n_survivors
    order = ranking(results["score"])[:n_survivors]
    parents = pop.take(order)
    children = mutate(parents, rng)
    child_results = evaluate(children)
    new_pop = Population.concat(parents, children)
    new_results = {k: np.concatenate([results[k][order], child_results[k]]) for k in RESULT_KEYS}
    lineage = {"parent": np.concatenate([order, order]),  # indice dans la génération précédente
               "is_child": np.concatenate([np.zeros(n_survivors, bool), np.ones(n_survivors, bool)])}
    return new_pop, new_results, lineage


# ---------------------------------------------------------------------------
# Statistiques
# ---------------------------------------------------------------------------
HIST_EDGES = np.arange(config.HIST_RANGE[0], config.HIST_RANGE[1] + 1, 1.0)
HIST_COLUMNS = [f"h{int(e):+d}" for e in HIST_EDGES[:-1]]
STAT_COLUMNS = ["gen", "n", "height_mean", "height_median", "height_min", "height_max",
                "period_mean", "muscle_mean", "energy_mean", "energy_median", "energy_max", "score_mean", "score_max",
                "fallen", "best_index", "best_height", "best_period", "best_energy", "best_muscle",
                "eval_seconds"] + HIST_COLUMNS


def histogram(heights):
    """Histogramme 1 m de −10 à 40 m ; les valeurs hors plage vont dans la première / dernière barre."""
    clipped = np.clip(heights, HIST_EDGES[0], HIST_EDGES[-1] - 1e-9)
    return np.histogram(clipped, bins=HIST_EDGES)[0]


def generation_stats(gen, pop, results, eval_seconds=0.0):
    h = results["height"]
    best = int(ranking(results["score"])[0])
    row = {"gen": gen, "n": len(pop),
           "height_mean": float(h.mean()), "height_median": float(np.median(h)),
           "height_min": float(h.min()), "height_max": float(h.max()),
           "period_mean": float(pop.period.mean()), "muscle_mean": float(results["muscle_mass"].mean()),
           "energy_mean": float(results["energy"].mean()), "energy_median": float(np.median(results["energy"])),
           "energy_max": float(results["energy"].max()),
           "score_mean": float(results["score"].mean()), "score_max": float(results["score"][best]),
           "fallen": int(results["fallen"].sum()), "best_index": best,
           "best_height": float(h[best]), "best_period": float(pop.period[best]),
           "best_energy": float(results["energy"][best]), "best_muscle": float(results["muscle_mass"][best]),
           "eval_seconds": float(eval_seconds)}
    row.update(zip(HIST_COLUMNS, (int(v) for v in histogram(h))))
    return row


# ---------------------------------------------------------------------------
# Sauvegarde, reprise
# ---------------------------------------------------------------------------
def run_dir_for(seed, root=None):
    return os.path.join(config.RUNS_DIR if root is None else root, str(seed))


def gen_path(run_dir, gen):
    return os.path.join(run_dir, f"gen_{gen:04d}.npz")


def save_generation(run_dir, gen, pop, results, lineage, stats):
    arrays = {f: getattr(pop, f) for f in Population.FIELDS}
    arrays.update(results)
    arrays.update(lineage)
    np.savez(gen_path(run_dir, gen), gen=gen, stats=json.dumps(stats), **arrays)


def load_generation(run_dir, gen):
    """(population, résultats, lignée, stats) d'une génération sauvegardée."""
    with np.load(gen_path(run_dir, gen)) as data:
        pop = Population(*(data[f].copy() for f in Population.FIELDS))
        results = {k: data[k].copy() for k in RESULT_KEYS}
        lineage = {k: data[k].copy() for k in ("parent", "is_child")}
        stats = json.loads(str(data["stats"]))
    return pop, results, lineage, stats


def saved_generations(run_dir):
    if not os.path.isdir(run_dir):
        return []
    return sorted(int(f[4:8]) for f in os.listdir(run_dir) if f.startswith("gen_") and f.endswith(".npz"))


def config_snapshot():
    snap = {}
    for key in dir(config):
        if key.isupper():
            value = getattr(config, key)
            if isinstance(value, (int, float, str, bool, tuple, list, dict)):
                snap[key] = list(value) if isinstance(value, tuple) else value
    return snap


def apply_config(values, strict=True):
    """Applique des valeurs de config (instantané d'un run ou --set) ; renvoie les clés modifiées.

    strict=False (reprise d'un run) : un paramètre qui n'existe plus dans config.py est ignoré.
    """
    changed = []
    for key, value in values.items():
        if not hasattr(config, key):
            if strict:
                raise KeyError(f"paramètre inconnu dans config.py : {key}")
            continue
        current = getattr(config, key)
        if isinstance(current, tuple) and isinstance(value, list):
            value = tuple(value)
        if current != value:
            changed.append((key, current, value))
            setattr(config, key, value)
    return changed


def read_stats(run_dir):
    with open(os.path.join(run_dir, "stats.csv")) as f:
        return [{k: float(v) for k, v in row.items()} for row in csv.DictReader(f)]


def _write_stats(run_dir, rows):
    with open(os.path.join(run_dir, "stats.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=STAT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (f"{v:.6g}" if isinstance(v, float) else v) for k, v in row.items()})


# ---------------------------------------------------------------------------
# Audit du champion
# ---------------------------------------------------------------------------
AUDIT_COLUMNS = ["gen", "index", "height", "height_replay", "created_J", "created_height_m", "max_speed",
                 "max_torso_speed", "max_length_error", "max_tail_error", "max_height", "alerts"]


def audit_champion(run_dir, gen, pop, results, log=print):
    from evo import audit  # import tardif : le module rejoue avec le moteur scalaire

    best = int(ranking(results["score"])[0])
    c, ledger = audit.audit(pop.genome(best), duration=config.SIM_DURATION)
    weight = float(c.world.mass.sum() * config.G)
    created_height = ledger["hors_muscles+"] / weight  # équivalent hauteur de l'énergie créée
    alerts = []
    if abs(c.height() - results["height"][best]) > 1e-9:
        alerts.append("hauteur rejouée ≠ hauteur stockée")
    if created_height > config.AUDIT_MAX_CREATED_HEIGHT:
        alerts.append(f"{ledger['hors_muscles+']:.3f} J créés hors muscles (≈ {created_height * 100:.1f} cm)")
    if ledger["max_speed"] > config.AUDIT_MAX_SPEED:
        alerts.append(f"vitesse {ledger['max_speed']:.1f} m/s")
    if ledger["max_torso_speed"] > config.AUDIT_MAX_TORSO_SPEED:
        alerts.append(f"vitesse du torse {ledger['max_torso_speed']:.1f} m/s")
    if ledger["max_height"] > config.AUDIT_MAX_HEIGHT:
        alerts.append(f"hauteur {ledger['max_height']:.1f} m")
    if ledger["max_length_error"] > 0.01:
        alerts.append(f"erreur de longueur des os {ledger['max_length_error'] * 100:.2f} %")
    if ledger["max_tail_error"] > config.AUDIT_MAX_TAIL_ERROR:
        alerts.append(f"erreur de longueur de la queue {ledger['max_tail_error'] * 100:.2f} %")
    row = {"gen": gen, "index": best, "height": f"{results['height'][best]:.6f}",
           "height_replay": f"{c.height():.6f}", "created_J": f"{ledger['hors_muscles+']:.6f}",
           "created_height_m": f"{created_height:.5f}", "max_speed": f"{ledger['max_speed']:.2f}",
           "max_torso_speed": f"{ledger['max_torso_speed']:.2f}",
           "max_length_error": f"{ledger['max_length_error']:.5f}",
           "max_tail_error": f"{ledger['max_tail_error']:.5f}", "max_height": f"{ledger['max_height']:.3f}",
           "alerts": " ; ".join(alerts)}
    path = os.path.join(run_dir, "audit.csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=AUDIT_COLUMNS)
        if new:
            writer.writeheader()
        writer.writerow(row)
    status = "ALERTE : " + " ; ".join(alerts) if alerts else "ok"
    log(f"    audit gén. {gen} (champion n°{best}) : créé hors muscles {ledger['hors_muscles+']:.4f} J "
        f"(≈ {created_height * 1000:.1f} mm), "
        f"vitesse max {ledger['max_speed']:.1f} m/s, torse {ledger['max_torso_speed']:.1f} m/s → {status}")
    return row


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def train(seed, generations=None, pop_size=None, run_dir=None, overrides=None, audit_every=None, log=print):
    """Lance (ou reprend) un run jusqu'à la génération `generations` incluse."""
    generations = config.GENERATIONS if generations is None else generations
    run_dir = run_dir_for(seed) if run_dir is None else run_dir
    audit_every = config.AUDIT_EVERY if audit_every is None else audit_every
    done = saved_generations(run_dir)
    snapshot_path = os.path.join(run_dir, "config.json")

    if done:  # reprise : on réapplique la config du run
        with open(snapshot_path) as f:
            saved = json.load(f)
        if overrides:
            clash = {k: v for k, v in overrides.items() if saved.get(k) != (list(v) if isinstance(v, tuple) else v)}
            if clash:
                raise ValueError(f"reprise : --set incompatible avec la config du run {sorted(clash)}")
        for key in sorted(set(saved) - set(config_snapshot())):
            log(f"  reprise : {key} n'existe plus dans config.py, ignoré")
        for key, old, new in apply_config(saved, strict=False):
            log(f"  reprise : {key} = {new!r} (config du run ; config.py a {old!r})")
        start = done[-1]
        pop, results, _, _ = load_generation(run_dir, start)
        rows = read_stats(run_dir)[:start + 1]  # réécrites à l'identique (même format %.6g)
        log(f"reprise du run {run_dir} à la génération {start}")
    else:
        os.makedirs(run_dir, exist_ok=True)
        if overrides:
            apply_config(overrides)
        with open(snapshot_path, "w") as f:
            json.dump(config_snapshot(), f, indent=1, sort_keys=True)
        n = config.POP_SIZE if pop_size is None else pop_size
        t0 = time.perf_counter()
        pop = random_population(np.random.default_rng([seed, 0]), n)
        results = evaluate(pop)
        lineage = {"parent": np.full(n, -1), "is_child": np.zeros(n, bool)}
        stats = generation_stats(0, pop, results, time.perf_counter() - t0)
        save_generation(run_dir, 0, pop, results, lineage, stats)
        rows = [stats]
        _write_stats(run_dir, rows)
        _log_row(stats, log)
        if audit_every:
            audit_champion(run_dir, 0, pop, results, log)
        start = 0

    for gen in range(start + 1, generations + 1):
        t0 = time.perf_counter()
        pop, results, lineage = next_generation(pop, results, np.random.default_rng([seed, gen]))
        stats = generation_stats(gen, pop, results, time.perf_counter() - t0)
        save_generation(run_dir, gen, pop, results, lineage, stats)
        rows.append(stats)
        _write_stats(run_dir, rows)
        _log_row(stats, log)
        if audit_every and gen % audit_every == 0:
            audit_champion(run_dir, gen, pop, results, log)
    return run_dir


def _log_row(s, log):
    log(f"gén. {s['gen']:4d} | hauteur moy {s['height_mean']:+6.2f} max {s['height_max']:+6.2f} | "
        f"période {s['period_mean']:.2f} s | muscle {s['muscle_mean']:5.2f} | énergie {s['energy_mean']:5.1f} | "
        f"au sol {s['fallen']:4d} | meilleure {s['best_height']:+6.2f} m ({s['eval_seconds']:.1f} s)")
