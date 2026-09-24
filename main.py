"""Point d'entrée : reproduction de « J'ai codé l'évolution de créatures qui grimpent » (Code BH).

    python main.py debug-physics                 # bancs d'essai du moteur (§10, phase 1)
    python main.py debug-physics --bench 8       # démarre sur le pendule humain
    python main.py debug-physics --export out/phase1
"""
import argparse


def main(argv=None):
    parser = argparse.ArgumentParser(prog="main.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    debug = sub.add_parser("debug-physics", help="bancs d'essai du moteur physique")
    debug.add_argument("--bench", type=int, default=1, help="banc affiché au démarrage (1–8)")
    debug.add_argument("--export", metavar="DIR", help="rendu sans écran : écrit les PNG des 8 bancs dans DIR")

    args = parser.parse_args(argv)
    if args.command == "debug-physics":
        from evo import debug_physics
        if args.export:
            debug_physics.export(args.export)
        else:
            debug_physics.run_interactive(args.bench)


if __name__ == "__main__":
    main()
