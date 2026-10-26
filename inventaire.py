
import os
import sys
import json
from datetime import datetime, timezone
import requests

url_docker = os.getenv("DOCKER_API_URL", "http://127.0.0.1:2375")
url_netbox = os.getenv("NETBOX_URL", "http://127.0.0.1:8080")

try :
    cle_api = os.environ["NETBOX_TOKEN"]
except KeyError:
    sys.exit("Erreur : NETBOX_TOKEN est absent des variables d'environnement.")

delai_max = 5


def main():
    connexion = requests.Session()
    print("-> Récupération des informations Docker...")
    try:
        # on récup les conteneurs actifs et ceux qui sont arrêtés
        reponse_docker = connexion.get(
            f"{url_docker}/containers/json?all=true",
            timeout=delai_max
        )
        reponse_docker.raise_for_status()
        liste_docker = reponse_docker.json()

    except requests.RequestException as erreur:
        sys.exit(f"Impossible de contacter Docker ({url_docker}) : {erreur}")

    liste_conteneurs = []

    for element in liste_docker:
        identifiant = element["Id"]
        nom_conteneur = (
            element["Names"][0].lstrip("/")
            if element.get("Names")
            else identifiant[:12]
        )
        nom_image = element.get("Image", "")
        statut = element.get("State", "")

        utilisation_cpu = 0.0
        utilisation_ram = 0.0

        # stats disponibles pour les conteneurs démarrés
        if statut == "running":
            try:
                reponse_stats = connexion.get(
                    f"{url_docker}/containers/{identifiant}/stats?stream=false",
                    timeout=delai_max
                )

                if reponse_stats.status_code == 200:
                    statistiques = reponse_stats.json()

                    # on checke la consommation CPU en %
                    cpu_actuel = statistiques.get("cpu_stats", {})
                    cpu_precedent = statistiques.get("precpu_stats", {})

                    difference_cpu = (
                        cpu_actuel.get("cpu_usage", {}).get("total_usage", 0)
                        - cpu_precedent.get("cpu_usage", {}).get("total_usage", 0)
                    )

                    difference_systeme = (
                        cpu_actuel.get("system_cpu_usage", 0)
                        - cpu_precedent.get("system_cpu_usage", 0)
                    )

                    nombre_cpu = cpu_actuel.get("online_cpus", 1)

                    if difference_systeme > 0:
                        utilisation_cpu = round(
                            (difference_cpu / difference_systeme)
                            * nombre_cpu * 100,
                            2
                        )

                    # on convertit la mémoire utilisée en MO
                    memoire_octets = statistiques.get(
                        "memory_stats", {}
                    ).get("usage", 0)

                    utilisation_ram = round(
                        memoire_octets / (1024 * 1024), 2
                    )

            except requests.RequestException:
                pass

        liste_conteneurs.append({
            "id": identifiant[:12],
            "nom": nom_conteneur,
            "image": nom_image,
            "etat": statut,
            "cpu_pourcent": utilisation_cpu,
            "memoire_mo": utilisation_ram
        })


    print("-> Récupération des informations NetBox...")

    entetes = {"Authorization": f"Bearer {cle_api}"}
    # on va checker la version du serveur NetBox
    try:
        reponse_statut = connexion.get(
            f"{url_netbox}/api/status/",
            headers=entetes,
            timeout=delai_max
        )
        reponse_statut.raise_for_status()

        version_netbox = reponse_statut.json().get(
            "netbox-version", "inconnue"
        )

    except requests.RequestException as erreur:
        sys.exit(f"Impossible de récupérer la version NetBox : {erreur}")

    # on parcourt toutes les pages pour compter les types d objets
    page_suivante = f"{url_netbox}/api/core/object-types/?limit=50"
    compteur_types = 0
    nombre_annonce = None

    try:
        while page_suivante:
            reponse_page = connexion.get(
                page_suivante,
                headers=entetes,
                timeout=delai_max
            )
            reponse_page.raise_for_status()
            contenu_page = reponse_page.json()

            if nombre_annonce is None:
                nombre_annonce = contenu_page.get("count", 0)

            compteur_types += len(contenu_page.get("results", []))
            page_suivante = contenu_page.get("next")

    except requests.RequestException as erreur:
        sys.exit(f"Erreur pendant la pagination NetBox : {erreur}")

    # inventaire
    resultat_inventaire = {
        "date": datetime.now(timezone.utc).isoformat(),
        "docker": {
            "total_conteneurs": len(liste_conteneurs),
            "conteneurs": liste_conteneurs
        },
        "netbox": {
            "version": version_netbox,
            "object_types_count": compteur_types
        }
    }

    with open("inventaire.json", "w", encoding="utf-8") as fichier_sortie:
        json.dump(resultat_inventaire, fichier_sortie,indent=2, ensure_ascii=False)

    print("\n=============== INVENTAIRE ===============")
    print(f"Date du relevé : {resultat_inventaire['date']}")
    print(f"NetBox version : {version_netbox}")
    print(f"Types d'objets : {compteur_types} (count API = {nombre_annonce})")
    print(f"Conteneurs Docker: {len(liste_conteneurs)}")

    for element in liste_conteneurs:
        print(
            f" - {element['nom']:<20} "
            f"[{element['etat']:<7}] "
            f"CPU: {element['cpu_pourcent']:>5}% "
            f"RAM: {element['memoire_mo']:>7} Mo "
            f"({element['image']})"
        )
    print("Fichier inventaire.json créé avec succès.\n")
    connexion.close()

if __name__ == "__main__":
    main()
