import os
import requests
from fastapi import FastAPI, HTTPException

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