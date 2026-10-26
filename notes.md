Commandes TP1 : 

# 1. Lisez la version, listez tous les conteneurs, puis seulement ceux qui portent le label, lisez le détail de web1 :
http://127.0.0.1:2375 == api docker

```bash
curl -s "http://127.0.0.1:2375/version" # version
curl -s "http://127.0.0.1:2375/containers/json?all=true" # tous les conteneurs
curl -s --get "http://127.0.0.1:2375/containers/json" \
  --data-urlencode 'all=true' \
  --data-urlencode 'filters={"label":["adminapi.managed=true"]}' # que ceux avec le label managed true
curl -s "http://127.0.0.1:2375/containers/web1/json" # détail d'un conteneur
```

# 3. Arrêtez web1 par l'API, deux fois de suite. Demandez un conteneur qui n'existe pas. Notez les trois codes de statut.
Premier arrêt : code HTTP 304
Second arrêt : code HTTP 304

Test avec un conteneur inexistant : code HTTP 404

# 4. Dans NetBox : ouvrez l'interface et la documentation Swagger, obtenez un token par l'API, rangez-le dans .env.
```bash
curl -v -X POST http://127.0.0.1:8080/api/users/tokens/provision/ -H "Content-Type: application/json" -H "Accept: application/json" -d "{\"username\":\"admin\",\"password\":\"admin\"}"
```

