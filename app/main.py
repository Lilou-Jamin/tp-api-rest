import os
import requests
from fastapi import FastAPI, HTTPException, Response
from typing import Literal
from pydantic import BaseModel, Field

app = FastAPI(title="API d'administration de conteneurs")

DOCKER_API_URL = os.environ.get("DOCKER_API_URL", "http://127.0.0.1:2375").rstrip("/")
ETIQUETTE = "adminapi.managed"

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/containers")
def lister_containers():
    try:
        res = requests.get(f"{DOCKER_API_URL}/containers/json?all=true", timeout=5)
        res.raise_for_status()
        containers = res.json()
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Erreur de connexion à l'API Docker")

    resultat = []
    for c in containers:
        labels = c.get("Labels") or {}
        # Ne garder que les conteneurs avec le label adminapi.managed=true
        if labels.get(ETIQUETTE) == "true":
            nom = c["Names"][0].lstrip("/") if c.get("Names") else c["Id"][:12]
            resultat.append({
                "id": c["Id"],
                "name": nom,
                "image": c.get("Image", ""),
                "state": c.get("State", "")
            })
    return resultat

@app.get("/containers/{id}")
def detail_container(id: str):
    try:
        res = requests.get(f"{DOCKER_API_URL}/containers/{id}/json", timeout=5)
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Erreur de connexion à l'API Docker")

    if res.status_code == 404:
        raise HTTPException(status_code=404, detail="Conteneur inconnu")

    detail = res.json()
    labels = detail.get("Config", {}).get("Labels") or {}

    # Si le conteneur n'a pas le label, le contrat exige 404 (traité comme inexistant)
    if labels.get(ETIQUETTE) != "true":
        raise HTTPException(status_code=404, detail="Conteneur non géré par l'API")

    return {
        "id": detail["Id"],
        "name": detail.get("Name", "").lstrip("/"),
        "image": detail.get("Config", {}).get("Image", ""),
        "state": detail.get("State", {}).get("Status", "")
    }

"""

== lecture : 7/7 ==
  [ok] GET /health répond 200 et {"status": "ok"}
  [ok] GET /containers répond 200 avec une liste JSON
  [ok] la liste contient le conteneur étiqueté, avec id, name, image et state
  [ok] la liste ne montre pas les conteneurs sans label
  [ok] GET /containers/{id} répond 200 avec le bon conteneur
  [ok] GET /containers/{id} répond 404 pour un identifiant inconnu
  [ok] GET /containers/{id} répond 404 pour un conteneur sans label

Total : 7/7 vérifications passées.
"""

class ContainerCreate(BaseModel):
    name: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9-]*$",
        min_length=1,
        max_length=63
    )

    image: Literal[
        "nginx:alpine",
        "redis:7-alpine",
        "busybox:latest"
    ]

# Créer un conteneur
@app.post("/containers", status_code=201)
def creer_conteneur(donnees: ContainerCreate):

    # Vérifier si le nom est déjà utilisé
    try:
        verification = requests.get(
            f"{DOCKER_API_URL}/containers/{donnees.name}/json",
            timeout=5
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=502,
            detail="Docker inaccessible"
        )

    if verification.status_code == 200:
        raise HTTPException(
            status_code=409,
            detail="Ce nom est déjà utilisé"
        )

    if verification.status_code != 404:
        raise HTTPException(
            status_code=502,
            detail="Erreur lors de la vérification du nom"
        )

    # Préparer les informations du conteneur
    configuration = {
        "Image": donnees.image,
        "Labels": {
            ETIQUETTE: "true"
        }
    }

    try:
        # Créer le conteneur Docker
        creation = requests.post(
            f"{DOCKER_API_URL}/containers/create",
            params={"name": donnees.name},
            json=configuration,
            timeout=10
        )

        if creation.status_code == 409:
            raise HTTPException(
                status_code=409,
                detail="Nom déjà utilisé"
            )

        if not creation.ok:
            raise HTTPException(
                status_code=502,
                detail="Échec de la création Docker"
            )

        nouvel_id = creation.json()["Id"]

        # Démarrer le conteneur
        demarrage = requests.post(
            f"{DOCKER_API_URL}/containers/{nouvel_id}/start",
            timeout=10
        )

        if not demarrage.ok:
            raise HTTPException(
                status_code=502,
                detail="Conteneur créé mais démarrage impossible"
            )

    except requests.RequestException:
        raise HTTPException(
            status_code=502,
            detail="Erreur de communication avec Docker"
        )

    infos = recuperer_conteneur(nouvel_id)
    return formater_conteneur(infos)

def recuperer_conteneur(id: str):
    try:
        reponse = requests.get(
            f"{DOCKER_API_URL}/containers/{id}/json",
            timeout=5
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=502,
            detail="Impossible de contacter Docker"
        )

    if reponse.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Conteneur introuvable"
        )

    if not reponse.ok:
        raise HTTPException(
            status_code=502,
            detail="Erreur Docker"
        )

    infos = reponse.json()
    labels = infos.get("Config", {}).get("Labels") or {}

    if labels.get(ETIQUETTE) != "true":
        raise HTTPException(
            status_code=404,
            detail="Conteneur non géré"
        )

    return infos


def formater_conteneur(infos):
    return {
        "id": infos["Id"],
        "name": infos.get("Name", "").lstrip("/"),
        "image": infos.get("Config", {}).get("Image", ""),
        "state": infos.get("State", {}).get("Status", "")
    }

# Arrêt d'un conteneur
@app.post("/containers/{id}/stop") 
def arreter_conteneur(id: str):
    infos = recuperer_conteneur(id)

    if not infos.get("State", {}).get("Running", False):
        raise HTTPException(
            status_code=409,
            detail="Conteneur déjà arrêté"
        )

    try:
        reponse = requests.post(
            f"{DOCKER_API_URL}/containers/{id}/stop",
            timeout=15
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=502,
            detail="Erreur Docker"
        )

    if reponse.status_code == 404:
        raise HTTPException(status_code=404, detail="Conteneur introuvable")

    if reponse.status_code == 304:
        raise HTTPException(status_code=409, detail="Conteneur déjà arrêté")

    if not reponse.ok:
        raise HTTPException(status_code=502, detail="Arrêt impossible")

    infos = recuperer_conteneur(id)
    return formater_conteneur(infos)

# Démarrage d'un conteneur
@app.post("/containers/{id}/start")
def demarrer_conteneur(id: str):
    infos = recuperer_conteneur(id)

    if infos.get("State", {}).get("Running", False):
        raise HTTPException(
            status_code=409,
            detail="Conteneur déjà démarré"
        )

    try:
        reponse = requests.post(
            f"{DOCKER_API_URL}/containers/{id}/start",
            timeout=10
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=502,
            detail="Erreur Docker"
        )

    if reponse.status_code == 404:
        raise HTTPException(status_code=404, detail="Conteneur introuvable")

    if reponse.status_code == 304:
        raise HTTPException(status_code=409, detail="Conteneur déjà démarré")

    if not reponse.ok:
        raise HTTPException(status_code=502, detail="Démarrage impossible")

    infos = recuperer_conteneur(id)
    return formater_conteneur(infos)


# Suppression d'un conteneur
@app.delete("/containers/{id}", status_code=204)
def supprimer_conteneur(id: str):
    recuperer_conteneur(id)

    try:
        reponse = requests.delete(
            f"{DOCKER_API_URL}/containers/{id}",
            params={"force": "true"},
            timeout=10
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=502,
            detail="Erreur Docker"
        )

    if reponse.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Conteneur introuvable"
        )

    if not reponse.ok:
        raise HTTPException(
            status_code=502,
            detail="Suppression impossible"
        )

    return Response(status_code=204)
