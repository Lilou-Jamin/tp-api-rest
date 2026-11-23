
import os
import requests


NETBOX_URL = os.environ["NETBOX_URL"].rstrip("/")
NETBOX_TOKEN = os.environ["NETBOX_TOKEN"]
TIMEOUT = 10

session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {NETBOX_TOKEN}",
    "Accept": "application/json"
})


def requete_netbox(methode, chemin, **options):
    """Effectue une requête vers NetBox."""
    reponse = session.request(
        methode,
        f"{NETBOX_URL}{chemin}",
        timeout=TIMEOUT,
        **options
    )
    reponse.raise_for_status()

    if reponse.status_code == 204:
        return None

    return reponse.json()


def trouver_cluster():
    """Retrouve l'identifiant du cluster docker-local."""
    donnees = requete_netbox(
        "GET",
        "/api/virtualization/clusters/",
        params={"name": "docker-local"}
    )

    for cluster in donnees.get("results", []):
        if cluster["name"] == "docker-local":
            return cluster["id"]

    raise RuntimeError("Cluster docker-local introuvable dans NetBox")


def trouver_vm(nom):
    """Recherche une VM par nom dans le cluster Docker."""
    cluster_id = trouver_cluster()

    donnees = requete_netbox(
        "GET",
        "/api/virtualization/virtual-machines/",
        params={"name": nom, "cluster_id": cluster_id}
    )

    for vm in donnees.get("results", []):
        if vm["name"] == nom and vm.get("cluster", {}).get("id") == cluster_id:
            return vm

    return None


def creer_vm(nom):
    """Crée la VM NetBox associée au conteneur."""
    existante = trouver_vm(nom)

    if existante:
        # Si la VM existe déjà, on actualise son statut
        return modifier_statut_vm(nom, "active")

    return requete_netbox(
        "POST",
        "/api/virtualization/virtual-machines/",
        json={
            "name": nom,
            "cluster": trouver_cluster(),
            "status": "active"
        }
    )


def modifier_statut_vm(nom, statut):
    """Met à jour l'état de la VM dans NetBox."""
    vm = trouver_vm(nom)

    if vm is None:
        raise RuntimeError(f"VM {nom} introuvable dans NetBox")

    return requete_netbox(
        "PATCH",
        f"/api/virtualization/virtual-machines/{vm['id']}/",
        json={"status": statut}
    )


def supprimer_vm(nom):
    """Supprime la VM associée au conteneur."""
    vm = trouver_vm(nom)

    if vm is None:
        return

    requete_netbox(
        "DELETE",
        f"/api/virtualization/virtual-machines/{vm['id']}/"
    )
