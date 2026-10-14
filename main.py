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
    python main.py graphs --seed 2 --compare runs/legacy_no_limits/2   # avec / sans butées superposés (chantier B2)
    python main.py histogram --seed 42 --gen 0 [--style video]
    python main.py population --seed 2 --gen 200    # vue population, tri animé (§7.1)
    python main.py population --seed 2 --gen 200 --export out/phase5b
    python main.py population --seed 2 --gen 0 --cycle [--export DIR]   # apparition, tri, élimination, enfants
    python main.py replay --seed 2 --gen 200 --rank 1   # rejoue une créature dans la jungle (§5, §8)
    python main.py replay --seed 2 --gen 200 --rank 1 --export out/phase4
    python main.py replay --seed 2 --gen 200 --rank 1 --fps-report   # vérifie les 60 fps en fenêtre
    python main.py replay --seed 2 --gen 0 --creature 1 --title-card "Le commencement" --speed 4
    python main.py analyze --seed 2 --gen 200 --rank 1 [--slow]   # zoom biomécanique + % (§7.4)
    python main.py analyze --seed 2 --gen 200 --rank 1 --export out/phase5c
    python main.py compare --seed 2 --gens 0 23 100 200 [--export out/phase5c]   # fantômes (§7.5)
    python main.py replay --seed 2 --gen 200 --rank 1 --export-video out/phase6/replay.mp4   # MP4 (phase 6)
    python main.py analyze --seed 2 --gen 200 --slow --export-video out/phase6/analyse.mp4
    (replay, analyze, compare : --speed X et --slow ; population : --export-video aussi)
    python main.py decor --seed 2 --export out/chantierA/decor   # décor au-dessus de 23 m (image 08, 20 → 50 m)
    python main.py joints --seed 2 --gen 200 [--top 50] [--sample 50] [--export DIR]   # angles contre butées (chantier B)
    python main.py joints --seed 2 --gen 200 --top 50 --sample 50 --crossings   # croisements entre membres (chantier C)
    python main.py joints --seed 2 --gen 200 --top 50 --sample 50 --tail --run-dir runs/butees_corps/2   # queue (C2)
    python main.py joints --seed 2 --gen 0 --fallen --run-dir runs/butees_corps/2   # créatures tombées (C2)
    python main.py morpho --seed 2 --run-dir runs/butees_corps/2 --compare runs/2   # longueurs d'os par génération
    python main.py planche A.png B.png --labels "B2" "C2" --out planche.png   # images côte à côte
    python main.py trace --seed 2 --gen 0 --creature 868 --export out/diag   # rejeu pas à pas audité (diagnostic)
    python main.py trace --seed 1 --gen 200 --creature 0 --variante dissipatif   # idem, avec une variante du chantier D
    python main.py diag-projection --seed 2 --gen 0 --tombees --export out/d   # candidats du chantier D (lecture seule)
    python main.py genome --schema | --exemple | --verifier genome.json --manche 2   # génome JSON du duel (v2)
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
    graphs.add_argument("--compare", metavar="RUN_DIR", default=None,
                        help="superpose ce run de référence (pointillés) aux courbes du run (chantier B2)")
    graphs.add_argument("--labels", nargs=2, metavar=("REF", "RUN"), default=("sans butées", "avec butées"),
                        help="légendes de --compare : run de référence, puis run (défaut : sans / avec butées)")

    morpho = sub.add_parser("morpho", help="facteur moyen de longueur de chaque os au fil des générations (chantier C2)")
    morpho.add_argument("--seed", type=int, default=2)
    morpho.add_argument("--run-dir", default=None, help="dossier du run (défaut : runs/<seed>)")
    morpho.add_argument("--compare", metavar="RUN_DIR", default=None, help="second run superposé (pointillés)")
    morpho.add_argument("--gens", type=int, nargs="+", default=None,
                        help="générations (défaut : 0 10 25 50 100 150 200)")
    morpho.add_argument("--out", default=None, help="dossier de sortie (défaut : <run>/graphes)")

    tr = sub.add_parser("trace", help="rejeu pas à pas d'une créature avec l'audit d'énergie à chaque sous-pas (diagnostic)")
    tr.add_argument("--seed", type=int, default=2)
    tr.add_argument("--run-dir", default=None, help="dossier du run (défaut : runs/<seed>)")
    tr.add_argument("--gen", type=int, required=True)
    tr.add_argument("--creature", type=int, required=True, help="indice de la créature dans la génération (npz)")
    tr.add_argument("--export", metavar="DIR", default=None, help="écrit le CSV par sous-pas dans DIR")
    tr.add_argument("--variante", default="tel_quel",
                    help="variante de diagnostic du chantier D, « projection[:queue] » (projection : tel_quel, "
                         "vitesse_proj, dissipatif, passes120 ; queue : cone, courbure5, courbure1), substituée le temps "
                         "du rejeu (moteur non modifié)")

    dp = sub.add_parser("diag-projection",
                        help="diagnostic du chantier D : moteur tel quel contre les variantes vitesse_proj, dissipatif "
                             "et passes120 (lecture seule, le moteur n'est pas modifié)")
    dp.add_argument("--seed", type=int, default=2)
    dp.add_argument("--run-dir", default=None, help="dossier du run (défaut : runs/<seed>)")
    dp.add_argument("--gen", type=int, required=True)
    dp.add_argument("--creature", type=int, default=None, help="indice de la créature dans la génération (npz)")
    dp.add_argument("--tombees", action="store_true", help="toutes les créatures tombées de la génération")
    dp.add_argument("--meilleures", type=int, default=None, metavar="N", help="les N meilleures de la génération")
    dp.add_argument("--inerte", action="store_true",
                    help="la créature inerte, sur la config du run, contre les seuils de tests/test_creature.py")
    dp.add_argument("--benchmark", action="store_true", help="coût relatif de chaque variante (moteur scalaire)")
    dp.add_argument("--benchmark-batch", action="store_true",
                    help="coût relatif de chaque jeu de butées de queue dans l'évaluateur batché (entraînement)")
    dp.add_argument("--variantes", nargs="+", default=None,
                    help="variantes « projection[:queue] » (défaut : tel_quel vitesse_proj dissipatif passes120), ou "
                         "« D<angle> » : le moteur du chantier D avec un cône de queue de ±angle (ex. D10 D15 D30)")
    dp.add_argument("--export", metavar="DIR", default=None, help="écrit les mesures en JSON dans DIR")

    planche = sub.add_parser("planche", help="assemble des images côte à côte, légendées (chantier C2)")
    planche.add_argument("images", nargs="+")
    planche.add_argument("--labels", nargs="+", default=None, help="une légende par image (défaut : nom du fichier)")
    planche.add_argument("--height", type=int, default=None, help="hauteur commune (défaut : la plus petite)")
    planche.add_argument("--crop", type=float, nargs=4, metavar=("X0", "Y0", "X1", "Y1"), default=None,
                         help="recadrage de chaque image, en fractions (0 à 1)")
    planche.add_argument("--out", required=True)

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
    popv.add_argument("--export-video", metavar="MP4", help="sans écran : tri animé puis histogramme en MP4 (ffmpeg)")
    popv.add_argument("--cycle", action="store_true",
                      help="cycle complet (§7.1) : apparition des colonnes, tri, histogramme, élimination des perdantes, "
                           "enfants (génération N+1 sauvegardée)")

    replay = sub.add_parser("replay", help="rejoue une créature sauvegardée dans le décor jungle (§5, §8)")
    replay.add_argument("--seed", type=int, default=2, help="graine du run (défaut : 2, run de référence)")
    replay.add_argument("--run-dir", default=None, help="dossier du run (défaut : runs/<seed>)")
    replay.add_argument("--gen", type=int, default=None, help="génération (défaut : la dernière sauvegardée)")
    replay.add_argument("--rank", type=int, default=1, help="rang au classement (1 = meilleure)")
    replay.add_argument("--creature", type=int, default=None, metavar="I",
                        help="rejoue la créature n°I de la génération (1 = première, HUD « Créature: I ») au lieu d'un rang")
    replay.add_argument("--speed", type=float, default=1.0, help="vitesse du replay (> 1 : accéléré, icône ⏩)")
    replay.add_argument("--slow", action="store_true", help="ralenti ×0.25 (touche S)")
    replay.add_argument("--title-card", default=None, metavar="TEXTE", help="sous-titre du carton de génération")
    replay.add_argument("--export", metavar="DIR", help="sans écran : PNG à t = 0, 2, …, 10 s, planche, comparaisons")
    replay.add_argument("--export-video", metavar="MP4", help="sans écran : tout le replay en MP4 (ffmpeg), carton et HUD compris")
    replay.add_argument("--no-cache", action="store_true", help="régénère le décor au lieu de relire le cache")
    replay.add_argument("--fps-report", action="store_true",
                        help="joue le replay une fois à vitesse normale puis affiche le fps moyen et minimum")

    analyze = sub.add_parser("analyze", help="mode analyse biomécanique : zoom, muscles + os, % (§7.4)")
    analyze.add_argument("--seed", type=int, default=2, help="graine du run (défaut : 2, run de référence)")
    analyze.add_argument("--run-dir", default=None, help="dossier du run (défaut : runs/<seed>)")
    analyze.add_argument("--gen", type=int, default=None, help="génération (défaut : la dernière sauvegardée)")
    analyze.add_argument("--rank", type=int, default=1, help="rang au classement (1 = meilleure)")
    analyze.add_argument("--speed", type=float, default=1.0, help="vitesse de lecture")
    analyze.add_argument("--slow", action="store_true", help="ralenti ×0.25 (touche S)")
    analyze.add_argument("--export", metavar="DIR", help="sans écran : PNG aux instants clés, comparaisons, temps")
    analyze.add_argument("--export-video", metavar="MP4", help="sans écran : toute l'analyse en MP4 (ffmpeg)")
    analyze.add_argument("--no-cache", action="store_true", help="régénère le décor au lieu de relire le cache")
    analyze.add_argument("--fps-report", action="store_true", help="joue une fois puis affiche le fps")

    comp = sub.add_parser("compare", help="champions de plusieurs générations en fantômes (§7.5)")
    comp.add_argument("--seed", type=int, default=2, help="graine du run (défaut : 2, run de référence)")
    comp.add_argument("--run-dir", default=None, help="dossier du run (défaut : runs/<seed>)")
    comp.add_argument("--gens", type=int, nargs="+", default=None, help="générations (défaut : COMPARE_GENS)")
    comp.add_argument("--speed", type=float, default=1.0, help="vitesse de lecture")
    comp.add_argument("--slow", action="store_true", help="ralenti ×0.25 (touche S)")
    comp.add_argument("--export", metavar="DIR", help="sans écran : PNG à quelques instants, comparaison, temps")
    comp.add_argument("--export-video", metavar="MP4", help="sans écran : toute la comparaison en MP4 (ffmpeg)")
    comp.add_argument("--no-cache", action="store_true", help="régénère le décor au lieu de relire le cache")
    comp.add_argument("--fps-report", action="store_true", help="joue une fois puis affiche le fps")

    decor = sub.add_parser("decor", help="décor au-dessus de 23 m : image 08 (30 m) et cohérence de 20 à 50 m (§5.6)")
    decor.add_argument("--seed", type=int, default=2, help="graine du run (défaut : 2, run de référence)")
    decor.add_argument("--run-dir", default=None, help="dossier du run (défaut : runs/<seed>)")
    decor.add_argument("--gen", type=int, default=None, help="génération (défaut : la dernière sauvegardée)")
    decor.add_argument("--rank", type=int, default=1, help="rang de la créature qui passe +30 m (1 = meilleure)")
    decor.add_argument("--export", metavar="DIR", required=True, help="dossier des images et des mesures")
    decor.add_argument("--no-cache", action="store_true", help="régénère le décor au lieu de relire le cache")

    joints = sub.add_parser("joints", help="angles articulaires réels contre les butées JOINT_LIMITS_DEG (chantier B)")
    joints.add_argument("--seed", type=int, default=2, help="graine du run (défaut : 2, run de référence)")
    joints.add_argument("--run-dir", default=None, help="dossier du run (défaut : runs/<seed>)")
    joints.add_argument("--gen", type=int, default=None, help="génération (défaut : la dernière sauvegardée)")
    joints.add_argument("--top", type=int, default=1, help="meilleures créatures rejouées (défaut : 1, le champion)")
    joints.add_argument("--sample", type=int, default=0, help="en plus, N créatures tirées au hasard dans la génération")
    joints.add_argument("--export", metavar="DIR", help="écrit les mesures en JSON dans DIR")
    joints.add_argument("--energy", action="store_true",
                        help="audit d'énergie de chaque créature en plus : sauts au moment où une butée s'engage")
    joints.add_argument("--crossings", action="store_true",
                        help="croisements entre membres : côté de l'axe du corps, paires de segments, cône de queue (chantier C)")
    joints.add_argument("--tail", action="store_true",
                        help="queue et butées du corps à chaque sous-pas, verdict du critère de repli (chantier C2)")
    joints.add_argument("--fallen", action="store_true",
                        help="toutes les créatures tombées de la génération : énergie créée hors muscles et queue, "
                             "contre les seuils d'audit (chantier C2)")

    gen = sub.add_parser("genome", help="génome JSON du duel (v2) : format, bornes, exemple, vérification d'un fichier")
    what = gen.add_mutually_exclusive_group(required=True)
    what.add_argument("--schema", action="store_true", help="affiche le format, les bornes et les conventions")
    what.add_argument("--exemple", action="store_true", help="affiche un génome complet valide")
    what.add_argument("--verifier", metavar="FICHIER", help="vérifie un génome JSON (toutes les erreurs d'un coup)")
    gen.add_argument("--manche", type=int, choices=(1, 2), default=2,
                     help="manche 1 : corps imposé, sans os_m ; manche 2 : génome complet (défaut)")

    args = parser.parse_args(argv)
    if args.command == "genome":
        import sys
        from evo import genome_json as gj
        if args.schema:
            print(gj.schema_texte())
        elif args.exemple:
            print(gj.texte_json(gj.exemple(args.manche)), end="")
        else:
            try:
                genome, _, _ = gj.charger(args.verifier, args.manche)
            except (gj.GenomeInvalide, OSError) as exc:
                print(exc)
                sys.exit(1)
            print(f"génome valide (manche {args.manche}) : période {genome.period:g} s, "
                  f"masse musculaire {genome.muscle_mass():g}")
        return
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
        if args.command == "graphs" and args.compare:
            print(charts.export_comparison(args.compare, run_dir, args.out, labels=tuple(args.labels)))
        for path in charts.export_run(run_dir, args.out, gens=gens, curves=args.command == "graphs", style=style):
            print(path)
    elif args.command == "population":
        import sys
        from evo import evolution, population
        run_dir = args.run_dir or evolution.run_dir_for(args.seed)
        generation = population.Generation(run_dir, gen=args.gen)
        offspring = population.Offspring(generation) if args.cycle else None
        if args.export:
            if offspring is None:
                paths, _ = population.export(generation, args.export)
            else:
                paths, _ = population.export_cycle(generation, offspring, args.export)
            for path in paths:
                print(path)
        if args.export_video:
            from evo import video
            video.record_population(generation, args.export_video, offspring=offspring)
        if not (args.export or args.export_video):
            population.run_interactive(generation, offspring)
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
        if args.export_video:
            from evo import video
            video.record_view(lambda: rp.JungleView(r, use_cache=not args.no_cache, subtitle=args.title_card), r,
                              args.export_video, speed=args.speed, slow=args.slow)
        if not (args.export or args.export_video):
            rp.run_interactive(r, use_cache=not args.no_cache, fps_report=args.fps_report, speed=args.speed,
                               subtitle=args.title_card, slow=args.slow)
        if not r.ok:
            print("ALERTE : la hauteur rejouée diffère de la hauteur stockée")
            sys.exit(1)
    elif args.command == "analyze":
        import sys
        from evo import analysis, evolution, replay as rp
        run_dir = args.run_dir or evolution.run_dir_for(args.seed)
        r = rp.Replay(run_dir, gen=args.gen, rank=args.rank)
        make_view = lambda: analysis.AnalysisView(r, use_cache=not args.no_cache, log=print)  # noqa: E731
        if args.export:
            paths, _ = analysis.export(r, args.export, use_cache=not args.no_cache)
            for path in paths:
                print(path)
        if args.export_video:
            from evo import video
            video.record_view(make_view, r, args.export_video, speed=args.speed, slow=args.slow)
        if not (args.export or args.export_video):
            rp.run_interactive(r, fps_report=args.fps_report, speed=args.speed, slow=args.slow, make_view=make_view)
        if not r.ok:
            print("ALERTE : la hauteur rejouée diffère de la hauteur stockée")
            sys.exit(1)
    elif args.command == "compare":
        import sys
        import config
        from evo import compare, evolution, replay as rp
        run_dir = args.run_dir or evolution.run_dir_for(args.seed)
        replays = compare.load_champions(run_dir, args.gens or list(config.COMPARE_GENS))
        make_view = lambda: compare.CompareView(replays, use_cache=not args.no_cache, log=print)  # noqa: E731
        latest = max(replays, key=lambda r: r.gen)
        if args.export:
            paths, _ = compare.export(replays, args.export, use_cache=not args.no_cache)
            for path in paths:
                print(path)
        if args.export_video:
            from evo import video
            video.record_view(make_view, latest, args.export_video, speed=args.speed, slow=args.slow)
        if not (args.export or args.export_video):
            rp.run_interactive(latest, fps_report=args.fps_report, speed=args.speed, slow=args.slow, make_view=make_view)
        if not all(r.ok for r in replays):
            print("ALERTE : une hauteur rejouée diffère de la hauteur stockée")
            sys.exit(1)
    elif args.command == "decor":
        from evo import decor_check, evolution, replay as rp
        run_dir = args.run_dir or evolution.run_dir_for(args.seed)
        r = rp.Replay(run_dir, gen=args.gen, rank=args.rank)
        paths, _ = decor_check.export(r, args.export, use_cache=not args.no_cache)
        for path in paths:
            print(path)
    elif args.command == "joints":
        import sys
        from evo import evolution, joint_audit
        run_dir = args.run_dir or evolution.run_dir_for(args.seed)
        if args.fallen:
            from evo import tail_audit
            gen = args.gen if args.gen is not None else evolution.saved_generations(run_dir)[-1]
            result = tail_audit.fallen_audit(run_dir, gen)
            if args.export:
                import json
                import os
                os.makedirs(args.export, exist_ok=True)
                path = os.path.join(args.export, f"tombees_{os.path.basename(os.path.normpath(run_dir))}_g{gen}.json")
                with open(path, "w") as fh:
                    json.dump(result, fh, indent=1, ensure_ascii=False)
                print(path)
            if not result["identique"]:
                print("ALERTE : une hauteur rejouée diffère de la hauteur stockée")
                sys.exit(1)
            return
        result = joint_audit.audit(run_dir, gen=args.gen, top=args.top, sample=args.sample, energy=args.energy,
                                   crossings=args.crossings, tail=args.tail)
        if args.export:
            print(joint_audit.export(result, args.export))
        if not result["identique"]:
            print("ALERTE : une hauteur rejouée diffère de la hauteur stockée")
            sys.exit(1)
    elif args.command == "morpho":
        from evo import evolution, morphology
        run_dir = args.run_dir or evolution.run_dir_for(args.seed)
        gens = tuple(args.gens) if args.gens else morphology.GENERATIONS
        for path in morphology.export(run_dir, compare=args.compare, out_dir=args.out, gens=gens):
            print(path)
    elif args.command == "trace":
        import sys
        from evo import evolution, trace
        run_dir = args.run_dir or evolution.run_dir_for(args.seed)
        result = trace.trace(run_dir, args.gen, args.creature, out_dir=args.export, variante=args.variante)
        if result["variante"] == "tel_quel" and not result["identique"]:
            print("ALERTE : la hauteur rejouée diffère de la hauteur stockée")
            sys.exit(1)
    elif args.command == "diag-projection":
        import sys
        import json
        import os
        from evo import diag_projection, evolution
        run_dir = args.run_dir or evolution.run_dir_for(args.seed)
        variants = tuple(args.variantes) if args.variantes else diag_projection.VARIANTS
        seed = os.path.basename(os.path.normpath(run_dir))
        if args.benchmark_batch:
            result, tag = diag_projection.benchmark_batch(run_dir, args.gen), "benchmark_batch"
        elif args.benchmark:
            result, tag = diag_projection.benchmark(run_dir, args.gen, variants=variants), "benchmark"
        elif args.inerte:
            result, tag = diag_projection.inert(run_dir, variants=variants), "inerte"
        elif args.tombees or args.meilleures:
            group = "tombees" if args.tombees else "meilleures"
            result = diag_projection.population(run_dir, args.gen, group, variants=variants, top=args.meilleures or 50)
            tag = group
        elif args.creature is not None:
            result, tag = diag_projection.compare(run_dir, args.gen, args.creature, variants=variants), f"n{args.creature}"
        else:
            parser.error("diag-projection : --creature, --tombees, --meilleures ou --benchmark")
        if args.export:
            os.makedirs(args.export, exist_ok=True)
            path = os.path.join(args.export, f"diag_s{seed}_g{args.gen}_{tag}.json")
            with open(path, "w") as fh:     # default : scalaires numpy (compteurs, booléens) en types Python
                json.dump(result, fh, indent=1, ensure_ascii=False, default=lambda o: o.item())
            print(path)
        if result.get("identique") is False:
            print("ALERTE : la hauteur rejouée (moteur tel quel) diffère de la hauteur stockée")
            sys.exit(1)
    elif args.command == "planche":
        from evo import planches
        print(planches.export(args.images, args.out, labels=args.labels, height=args.height, crop=args.crop))
    elif args.command == "debug-creature":
        from evo import debug_creature
        if args.export:
            debug_creature.export(args.export, seed=args.seed)
        else:
            debug_creature.run_interactive(args.mode, args.seed)


if __name__ == "__main__":
    main()
