"""Point d'entrée : reproduction de « J'ai codé l'évolution de créatures qui grimpent » (Code BH).

    python main.py debug-physics                 # bancs d'essai du moteur (§10, phase 1)
    python main.py debug-physics --bench 8       # démarre sur le pendule humain
    python main.py debug-physics --export out/phase1
    python main.py debug-physics --calibrate      # tableau stabilisation / pendule / vitesse
    python main.py debug-creature                 # créature, vue debug (§7.6, phase 2)
    python main.py debug-creature --export out/phase2
    python main.py benchmark --pop 1000           # temps d'évaluation d'une génération (phase 3a)
    python main.py train --generations 200 --pop 1000 --seed 42 [--set TORQUE_SCALE=0.3 …]
    python main.py graphs --seed 42               # courbes + histogrammes du run en PNG
    python main.py histogram --seed 42 --gen 0
"""
import argparse

import numpy as np


def main(argv=None):
    parser = argparse.ArgumentParser(prog="main.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    debug = sub.add_parser("debug-physics", help="bancs d'essai du moteur physique")
    debug.add_argument("--bench", type=int, default=1, help="banc affiché au démarrage (1–9)")
    debug.add_argument("--export", metavar="DIR", help="rendu sans écran : écrit les PNG des bancs dans DIR")
    debug.add_argument("--calibrate", action="store_true",
                       help="affiche les mesures de calibrage (stabilisation, pendule simple, vitesse)")

    creature = sub.add_parser("debug-creature", help="créature dans la vue debug (poses à la main, aléatoire…)")
    creature.add_argument("--mode", default="diagonale",
                          choices=["diagonale", "diagonale-simple", "inerte", "aleatoire"])
    creature.add_argument("--seed", type=int, default=0, help="graine du mode aléatoire")
    creature.add_argument("--export", metavar="DIR", help="rendu sans écran : écrit les PNG de tous les modes dans DIR")

    bench = sub.add_parser("benchmark", help="temps d'évaluation batchée d'une génération")
    bench.add_argument("--pop", type=int, default=1000)
    bench.add_argument("--seed", type=int, default=0)

    train = sub.add_parser("train", help="évolution (§3) ; reprend un run existant")
    train.add_argument("--generations", type=int, default=None, help="dernière génération (défaut : GENERATIONS)")
    train.add_argument("--pop", type=int, default=None, help="taille de population (défaut : POP_SIZE)")
    train.add_argument("--seed", type=int, default=42)
    train.add_argument("--run-dir", default=None, help="dossier du run (défaut : runs/<seed>)")
    train.add_argument("--set", action="append", default=[], metavar="CLE=VALEUR",
                       help="surcharge un paramètre de config.py pour ce run (enregistré dans config.json)")
    train.add_argument("--no-audit", action="store_true", help="pas d'audit du champion")

    graphs = sub.add_parser("graphs", help="courbes d'évolution et histogrammes d'un run (PNG)")
    graphs.add_argument("--seed", type=int, default=42)
    graphs.add_argument("--run-dir", default=None)
    graphs.add_argument("--out", default=None, help="dossier de sortie (défaut : <run>/graphes)")

    hist = sub.add_parser("histogram", help="histogramme des hauteurs d'une génération (PNG)")
    hist.add_argument("--seed", type=int, default=42)
    hist.add_argument("--run-dir", default=None)
    hist.add_argument("--gen", type=int, default=0)
    hist.add_argument("--out", default=None)

    args = parser.parse_args(argv)
    if args.command == "debug-physics":
        if args.calibrate:
            from evo import calibration
            print("\n".join(calibration.report()))
            return
        from evo import debug_physics
        if args.export:
            debug_physics.export(args.export)
        else:
            debug_physics.run_interactive(args.bench)
    elif args.command == "benchmark":
        from evo import batch
        b = batch.benchmark(args.pop, args.seed)
        r = b["result"]
        print(f"{b['n']} créatures × 10 s sur {b['threads']} cœur(s) : {b['total_s']:.2f} s "
              f"(préparation {b['pack_s']:.2f} s + simulation {b['simulate_s']:.2f} s)")
        print(f"au sol : {int(r['fallen'].sum())}   hauteur : médiane {float(np.median(r['height'])):+.2f} m, "
              f"max {float(r['height'].max()):+.2f} m")
    elif args.command == "train":
        import ast
        from evo import evolution
        overrides = {}
        for item in args.set:
            key, _, value = item.partition("=")
            try:
                overrides[key.strip()] = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                overrides[key.strip()] = value
        evolution.train(args.seed, args.generations, args.pop, args.run_dir, overrides,
                        audit_every=0 if args.no_audit else None)
    elif args.command in ("graphs", "histogram"):
        from evo import charts, evolution
        run_dir = args.run_dir or evolution.run_dir_for(args.seed)
        gens = [args.gen] if args.command == "histogram" else None
        for path in charts.export_run(run_dir, args.out, gens=gens if args.command == "histogram" else None):
            print(path)
    elif args.command == "debug-creature":
        from evo import debug_creature
        if args.export:
            debug_creature.export(args.export, seed=args.seed)
        else:
            debug_creature.run_interactive(args.mode, args.seed)


if __name__ == "__main__":
    main()
