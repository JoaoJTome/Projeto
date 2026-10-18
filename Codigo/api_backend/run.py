"""Arranca a API backend (FastAPI + Uvicorn) do projeto Análise de Cesto de Compras.

Uso (a partir de qualquer pasta):
    python run.py            arranca a API em http://localhost:8000
    python run.py install    reinstala/atualiza as dependências e arranca a API
    python run.py test       corre os testes automáticos (pytest)

Na primeira execução cria o ambiente virtual .venv nesta pasta e instala as
dependências do requirements.txt. Nas seguintes, arranca logo a API.
Funciona em Windows, Linux e macOS.
"""
import os
import socket
import subprocess
import sys
import venv
from pathlib import Path

PASTA = Path(__file__).resolve().parent
VENV = PASTA / ".venv"
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
CSV = PASTA.parent / "dataSort.csv"
HOST, PORTA = "127.0.0.1", 8000


def correr(*args):
    """Executa um comando com o Python do ambiente virtual, nesta pasta."""
    return subprocess.call([str(PY), *args], cwd=PASTA)


def criar_ambiente():
    print("[1/3] A criar o ambiente virtual .venv ...")
    venv.EnvBuilder(with_pip=True).create(VENV)


def instalar_dependencias():
    print("[2/3] A instalar as dependências do requirements.txt ...")
    correr("-m", "pip", "install", "--upgrade", "pip")
    # --prefer-binary: escolhe versões já compiladas (wheels) em vez de
    # compilar a partir do código-fonte, o que no Windows exigiria o
    # Microsoft C++ Build Tools (caso do greenlet, usado pelo SQLAlchemy).
    if correr("-m", "pip", "install", "--prefer-binary", "-r", "requirements.txt") != 0 \
            or not dependencias_ok():
        sys.exit("ERRO: falhou a instalação das dependências.\n"
                 "Se o erro referir o Microsoft Visual C++, experimente:\n"
                 "  python run.py install\n"
                 "depois de atualizar o pip, ou instale o Python 3.11/3.12.")


def dependencias_ok():
    """Confirma que as bibliotecas principais estão instaladas no .venv."""
    teste = "import fastapi, uvicorn, sqlalchemy, bcrypt, pydantic, pandas, mlxtend"
    return subprocess.call([str(PY), "-c", teste], cwd=PASTA,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def porta_ocupada(host, porta):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, porta)) == 0


def main():
    opcao = sys.argv[1].lower() if len(sys.argv) > 1 else ""

    instalar = opcao == "install"
    if not PY.exists():
        criar_ambiente()
        instalar = True
    elif not dependencias_ok():
        # O .venv existe mas está incompleto (por exemplo, uma instalação
        # anterior que falhou a meio): volta a instalar as dependências.
        print("O ambiente .venv existe, mas faltam dependências.")
        instalar = True
    if instalar:
        instalar_dependencias()

    if opcao == "test":
        print("A instalar o pytest e o httpx, se necessário ...")
        correr("-m", "pip", "install", "-q", "pytest", "httpx")
        sys.exit(correr("-m", "pytest", "-v"))

    if not CSV.exists():
        print(f"\nAVISO: não foi encontrado o ficheiro {CSV}")
        print("O motor de recomendação precisa dele na pasta Codigo.\n")

    # Uma versão antiga da API ainda aberta noutro terminal ocupa a porta e
    # faz com que a aplicação fale com código desatualizado.
    if porta_ocupada(HOST, PORTA):
        print(f"\nAVISO: a porta {PORTA} já está a ser usada por outro processo")
        print("(provavelmente uma API antiga ainda aberta).")
        if os.name == "nt":
            print("Para ver qual é:   netstat -ano | findstr :8000")
            print("Para o fechar:     taskkill /PID <número> /F")
        else:
            print("Para o fechar:     kill $(lsof -t -i :8000)")
        sys.exit("Feche esse processo e volte a executar python run.py.")

    print(f"[3/3] A arrancar a API em http://localhost:{PORTA}")
    print(f"      Documentação interativa: http://localhost:{PORTA}/docs")
    print("      Para parar: Ctrl+C\n")
    try:
        correr("-m", "uvicorn", "app.main:app", "--reload",
               "--host", HOST, "--port", str(PORTA))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
