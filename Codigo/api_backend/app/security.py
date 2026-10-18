"""Hashing de palavras-passe.

Usa bcrypt,  as palavras-passe nunca são guardadas em
texto simples, e cada uma recebe um salt aleatório único, gerado e embutido
automaticamente pelo bcrypt no próprio hash - não é preciso geri-lo à parte.
"""
import bcrypt


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # password_hash corrompido/inválido - trata como não coincidente,
        # em vez de deixar rebentar o pedido de login.
        return False
