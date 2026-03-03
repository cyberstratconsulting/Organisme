# MCP Organismes de Formation — Non certifiés Qualiopi

Outil pour explorer et exporter la liste des organismes de formation français **non certifiés Qualiopi**, à partir des données officielles de [data.gouv.fr](https://www.data.gouv.fr/fr/datasets/liste-publique-des-organismes-de-formation-l-6351-7-1-du-code-du-travail/).

---

## Prérequis

- **Python 3.10+** installé sur votre ordinateur
  - Windows : [Télécharger Python](https://www.python.org/downloads/) (cocher "Add Python to PATH")
  - Mac : `brew install python3`
  - Linux : `sudo apt install python3 python3-pip`

---

## Installation (2 minutes)

### Étape 1 : Installer les dépendances

**Windows** : double-cliquez sur `install.bat`

**Mac/Linux** : ouvrez un terminal dans ce dossier et tapez :
```bash
./install.sh
```

### Étape 2 : Configurer Claude

#### Option A — Claude Code (CLI)

Ajoutez à votre fichier `~/.claude/claude_desktop_config.json` :

```json
{
  "mcpServers": {
    "organismes-formation": {
      "command": "python3",
      "args": ["/CHEMIN/VERS/mcp-organismes-formation/server.py"],
      "env": {}
    }
  }
}
```

Remplacez `/CHEMIN/VERS/` par le vrai chemin du dossier.

#### Option B — Claude Desktop

Ouvrez les paramètres Claude Desktop → Developer → Edit Config, et ajoutez la même configuration ci-dessus.

#### Option C — VS Code + Extension Claude

1. Ouvrez VS Code
2. `Ctrl+Shift+P` → "Claude: Edit MCP Settings"
3. Ajoutez :

```json
{
  "organismes-formation": {
    "command": "python3",
    "args": ["/CHEMIN/VERS/mcp-organismes-formation/server.py"]
  }
}
```

---

## Utilisation

Une fois configuré, parlez simplement à Claude. Voici des exemples :

### Télécharger les données
> "Télécharge la liste des organismes de formation"

### Rechercher des organismes non Qualiopi
> "Cherche les organismes de formation non Qualiopi à Paris"
> "Trouve les organismes non certifiés en Île-de-France"
> "Recherche les OF non Qualiopi spécialisés en informatique"

### Voir les statistiques
> "Donne-moi les statistiques des organismes non Qualiopi"
> "Stats par région pour les organismes sans Qualiopi"

### Obtenir les détails d'un organisme
> "Donne-moi les détails de l'organisme SIREN 335060307"

### Exporter les résultats
> "Exporte en CSV tous les organismes non Qualiopi du département 75"
> "Exporte en JSON les OF non certifiés de Bretagne"

### Lister les codes régions
> "Quels sont les codes régions ?"

---

## Outils MCP disponibles

| Outil | Description |
|---|---|
| `telecharger_donnees` | Télécharge/met à jour les données depuis data.gouv.fr |
| `rechercher` | Recherche multi-critères (nom, SIRET, ville, région, spécialité...) |
| `statistiques` | Statistiques globales ou par région/département |
| `details_organisme` | Fiche complète d'un organisme (par NDA, SIREN ou SIRET) |
| `exporter` | Export CSV ou JSON avec filtres |
| `lister_regions` | Liste des codes régions |

---

## Source des données

- **Origine** : Ministère du Travail — Mon Activité Formation
- **Fréquence** : Mise à jour quotidienne
- **Licence** : Open Licence / Etalab 2.0 (réutilisation libre)
- **Lien** : [data.gouv.fr](https://www.data.gouv.fr/fr/datasets/liste-publique-des-organismes-de-formation-l-6351-7-1-du-code-du-travail/)
