
import os
import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


# Les deux tokens sont obligatoires, sans valeur par défaut
TOKEN_ADMIN = os.environ["API_TOKEN_ADMIN"]
TOKEN_LECTEUR = os.environ["API_TOKEN_READER"]

if not TOKEN_ADMIN or not TOKEN_LECTEUR:
    raise RuntimeError("Les tokens API ne doivent pas être vides")

if secrets.compare_digest(TOKEN_ADMIN, TOKEN_LECTEUR):
    raise RuntimeError("Les tokens admin et lecteur doivent être différents")


# Récupérer le token envoyé dans Authorization: Bearer ...
authentification = HTTPBearer(auto_error=False)


def verifier_token(
    identifiants: HTTPAuthorizationCredentials = Depends(authentification)
):
    # Aucun token fourni
    if identifiants is None:
        raise HTTPException(
            status_code=401,
            detail="Token manquant",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token_recu = identifiants.credentials

    # Vérifier le token administrateur
    if secrets.compare_digest(token_recu, TOKEN_ADMIN):
        return "admin"

    # Vérifier le token lecteur
    if secrets.compare_digest(token_recu, TOKEN_LECTEUR):
        return "lecteur"

    # Token inconnu
    raise HTTPException(
        status_code=401,
        detail="Token invalide",
        headers={"WWW-Authenticate": "Bearer"}
    )


def verifier_admin(role: str = Depends(verifier_token)):
    # Seul l'administrateur peut modifier les conteneurs
    if role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Accès réservé à l'administrateur"
        )

    return role
