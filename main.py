"""Point d'entrée : reproduction de « J'ai codé l'évolution de créatures qui grimpent » (Code BH).

    python main.py debug-physics                 # bancs d'essai du moteur (§10, phase 1)
    python main.py debug-physics --bench 8       # démarre sur le pendule humain
    python main.py debug-physics --export out/phase1
    python main.py debug-physics --calibrate      # tableau stabilisation / pendule / vitesse
    python main.py debug-creature                 # créature, vue debug (§7.6, phase 2)
    python main.py debug-creature --export out/phase2
"""
import argparse


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
    elif args.command == "debug-creature":
        from evo import debug_creature
        if args.export:
            debug_creature.export(args.export, seed=args.seed)
        else:
            debug_creature.run_interactive(args.mode, args.seed)


if __name__ == "__main__":
    main()
