"""python -m gillevoz [--testar-wav ARQ [--colar] [--atraso N]] [--baixar-modelo]"""
import argparse
import sys


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="gillevoz", description="GilleVoz — ditado por voz local")
    p.add_argument("--testar-wav", metavar="ARQ", help="transcreve um WAV, loga os tempos e salva no histórico")
    p.add_argument("--colar", action="store_true", help="com --testar-wav: cola o texto na janela em foco")
    p.add_argument("--atraso", type=float, default=3.0, help="segundos antes de colar (padrão 3)")
    p.add_argument("--baixar-modelo", action="store_true", help="baixa/carrega o modelo e sai")
    a = p.parse_args(argv)

    from . import app

    if a.baixar_modelo:
        return app.baixar_modelo()
    if a.testar_wav:
        return app.testar_wav(a.testar_wav, colar=a.colar, atraso=a.atraso)
    return app.App().run()


if __name__ == "__main__":
    sys.exit(main())
