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
    python main.py histogram --seed 42 --gen 0 [--style video]
    python main.py population --seed 2 --gen 200    # vue population, tri animé (§7.1)
    python main.py population --seed 2 --gen 200 --export out/phase5b
    python main.py replay --seed 2 --gen 200 --rank 1   # rejoue une créature dans la jungle (§5, §8)
    python main.py replay --seed 2 --gen 200 --rank 1 --export out/phase4
    python main.py replay --seed 2 --gen 200 --rank 1 --fps-report   # vérifie les 60 fps en fenêtre
    python main.py replay --seed 2 --gen 0 --creature 1 --title-card "Le commencement" --speed 4
    python main.py analyze --seed 2 --gen 200 --rank 1 [--slow]   # zoom biomécanique + % (§7.4)
    python main.py analyze --seed 2 --gen 200 --rank 1 --export out/phase5c
    python main.py compare --seed 2 --gens 0 23 100 200 [--export out/phase5c]   # fantômes (§7.5)
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
    hist.add_argument("--style", default="calibration", choices=["calibration", "video"],
                      help="calibration (phase 3b, encart de stats) ou video (images 26 à 28)")

    popv = sub.add_parser("population", help="vue population : miniatures en poses finales et tri animé (§7.1)")
    popv.add_argument("--seed", type=int, default=2, help="graine du run (défaut : 2, run de référence)")
    popv.add_argument("--run-dir", default=None, help="dossier du run (défaut : runs/<seed>)")
    popv.add_argument("--gen", type=int, default=None, help="génération (défaut : la dernière sauvegardée)")
    popv.add_argument("--export", metavar="DIR", help="sans écran : vue avant / pendant / après le tri, histogramme, comparaisons")

    replay = sub.add_parser("replay", help="rejoue une créature sauvegardée dans le décor jungle (§5, §8)")
    replay.add_argument("--seed", type=int, default=2, help="graine du run (défaut : 2, run de référence)")
    replay.add_argument("--run-dir", default=None, help="dossier du run (défaut : runs/<seed>)")
    replay.add_argument("--gen", type=int, default=None, help="génération (défaut : la dernière sauvegardée)")
    replay.add_argument("--rank", type=int, default=1, help="rang au classement (1 = meilleure)")
    replay.add_argument("--creature", type=int, default=None, metavar="I",
                        help="rejoue la créature n°I de la génération (1 = première, HUD « Créature: I ») au lieu d'un rang")
    replay.add_argument("--speed", type=float, default=1.0, help="vitesse du replay (> 1 : accéléré, icône ⏩)")
    replay.add_argument("--title-card", default=None, metavar="TEXTE", help="sous-titre du carton de génération")
    replay.add_argument("--export", metavar="DIR", help="sans écran : PNG à t = 0, 2, …, 10 s, planche, comparaisons")
    replay.add_argument("--no-cache", action="store_true", help="régénère le décor au lieu de relire le cache")
    replay.add_argument("--fps-report", action="store_true",
                        help="joue le replay une fois à vitesse normale puis affiche le fps moyen et minimum")

    analyze = sub.add_parser("analyze", help="mode analyse biomécanique : zoom, muscles + os, % (§7.4)")
    analyze.add_argument("--seed", type=int, default=2, help="graine du run (défaut : 2, run de référence)")
    analyze.add_argument("--run-dir", default=None, help="dossier du run (défaut : runs/<seed>)")
    analyze.add_argument("--gen", type=int, default=None, help="génération (défaut : la dernière sauvegardée)")
    analyze.add_argument("--rank", type=int, default=1, help="rang au classement (1 = meilleure)")
    analyze.add_argument("--slow", action="store_true", help="démarre au ralenti ×0.25 (touche S)")
    analyze.add_argument("--export", metavar="DIR", help="sans écran : PNG aux instants clés, comparaisons, temps")
    analyze.add_argument("--no-cache", action="store_true", help="régénère le décor au lieu de relire le cache")
    analyze.add_argument("--fps-report", action="store_true", help="joue une fois puis affiche le fps")

    comp = sub.add_parser("compare", help="champions de plusieurs générations en fantômes (§7.5)")
    comp.add_argument("--seed", type=int, default=2, help="graine du run (défaut : 2, run de référence)")
    comp.add_argument("--run-dir", default=None, help="dossier du run (défaut : runs/<seed>)")
    comp.add_argument("--gens", type=int, nargs="+", default=None, help="générations (défaut : COMPARE_GENS)")
    comp.add_argument("--export", metavar="DIR", help="sans écran : PNG à quelques instants, comparaison, temps")
    comp.add_argument("--no-cache", action="store_true", help="régénère le décor au lieu de relire le cache")
    comp.add_argument("--fps-report", action="store_true", help="joue une fois puis affiche le fps")

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
        style = args.style if args.command == "histogram" else "calibration"
        for path in charts.export_run(run_dir, args.out, gens=gens, curves=args.command == "graphs", style=style):
            print(path)
    elif args.command == "population":
        import sys
        from evo import evolution, population
        run_dir = args.run_dir or evolution.run_dir_for(args.seed)
        generation = population.Generation(run_dir, gen=args.gen)
        if args.export:
            paths, _ = population.export(generation, args.export)
            for path in paths:
                print(path)
        else:
            population.run_interactive(generation)
        if not generation.ok:
            print("ALERTE : les hauteurs batchées diffèrent des hauteurs stockées")
            sys.exit(1)
    elif args.command == "replay":
        import sys
        from evo import evolution, replay as rp
        run_dir = args.run_dir or evolution.run_dir_for(args.seed)
        index = None if args.creature is None else args.creature - 1
        r = rp.Replay(run_dir, gen=args.gen, rank=args.rank, index=index)
        if args.export:
            paths, _ = rp.export(r, args.export, use_cache=not args.no_cache, subtitle=args.title_card)
            for path in paths:
                print(path)
        else:
            rp.run_interactive(r, use_cache=not args.no_cache, fps_report=args.fps_report, speed=args.speed,
                               subtitle=args.title_card)
        if not r.ok:
            print("ALERTE : la hauteur rejouée diffère de la hauteur stockée")
            sys.exit(1)
    elif args.command == "analyze":
        import sys
        from evo import analysis, evolution, replay as rp
        run_dir = args.run_dir or evolution.run_dir_for(args.seed)
        r = rp.Replay(run_dir, gen=args.gen, rank=args.rank)
        if args.export:
            paths, _ = analysis.export(r, args.export, use_cache=not args.no_cache)
            for path in paths:
                print(path)
        else:
            rp.run_interactive(r, fps_report=args.fps_report, slow=args.slow,
                               make_view=lambda: analysis.AnalysisView(r, use_cache=not args.no_cache, log=print))
        if not r.ok:
            print("ALERTE : la hauteur rejouée diffère de la hauteur stockée")
            sys.exit(1)
    elif args.command == "compare":
        import sys
        import config
        from evo import compare, evolution, replay as rp
        run_dir = args.run_dir or evolution.run_dir_for(args.seed)
        replays = compare.load_champions(run_dir, args.gens or list(config.COMPARE_GENS))
        if args.export:
            paths, _ = compare.export(replays, args.export, use_cache=not args.no_cache)
            for path in paths:
                print(path)
        else:
            rp.run_interactive(max(replays, key=lambda r: r.gen), fps_report=args.fps_report,
                               make_view=lambda: compare.CompareView(replays, use_cache=not args.no_cache, log=print))
        if not all(r.ok for r in replays):
            print("ALERTE : une hauteur rejouée diffère de la hauteur stockée")
            sys.exit(1)
    elif args.command == "debug-creature":
        from evo import debug_creature
        if args.export:
            debug_creature.export(args.export, seed=args.seed)
        else:
            debug_creature.run_interactive(args.mode, args.seed)


if __name__ == "__main__":
    main()
