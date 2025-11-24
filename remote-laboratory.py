import argparse
import os
import subprocess
import sys
import time
from typing import List, Tuple

Command = List[str]
ProcessInfo = Tuple[subprocess.Popen, str]


def start_process(cmd: Command, name: str) -> ProcessInfo:
    print(f"Iniciando {name}: {' '.join(cmd)}")
    return subprocess.Popen(cmd), name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Helper para subir serviços. "
            "Por padrão inicia apenas o Flask (lab-manager/main.py). "
            "Use flags para também iniciar o coletor ou o chatbot de terminal."
        )
    )
    parser.add_argument(
        "--collector",
        action="store_true",
        help="Também inicia collecting_profinet.py (interativo, usa stdin).",
    )
    parser.add_argument(
        "--terminal-chatbot",
        action="store_true",
        help="Inicia o chatbot de terminal (usa stdin, conflita com o coletor).",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.terminal_chatbot and args.collector:
        print("Aviso: coletor e chatbot de terminal compartilham o stdin; evite rodar os dois juntos.")

    openai_key = os.environ.get("OPENAI_API_KEY")
    if args.terminal_chatbot and not openai_key:
        print("Aviso: defina OPENAI_API_KEY antes de rodar o chatbot de terminal.")

    commands: List[Tuple[Command, str]] = []

    if args.collector:
        commands.append((["python", "collecting_profinet.py"], "collecting_profinet"))

    # Flask sempre sobe
    commands.append((["python", "lab-manager/main.py"], "lab-manager"))

    if args.terminal_chatbot:
        commands.append((["python", "-m", "chatbot.main"], "chatbot"))

    if not commands:
        print("Nada para rodar. Use --collector ou --terminal-chatbot se quiser incluir processos.")
        sys.exit(0)

    processes: List[ProcessInfo] = []
    try:
        for cmd, name in commands:
            processes.append(start_process(cmd, name))

        print("Processos iniciados. Use Ctrl+C para encerrar.")
        while any(proc.poll() is None for proc, _ in processes):
            for proc, name in processes:
                ret = proc.poll()
                if ret is not None:
                    print(f"{name} terminou com código {ret}.")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nEncerrando processos...")
    finally:
        for proc, name in processes:
            if proc.poll() is None:
                print(f"Matando {name} (pid {proc.pid})")
                proc.terminate()
        for proc, _ in processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
