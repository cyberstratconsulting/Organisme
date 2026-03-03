#!/usr/bin/env python3
"""
MCP Server — Organismes de Formation non certifiés Qualiopi
Données source : data.gouv.fr / Mon Activité Formation
"""

import csv
import io
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CSV_URL = (
    "https://www.monactiviteformation.emploi.gouv.fr"
    "/mon-activite-formation/public/listePubliqueOF?format=csv"
)
TABULAR_API = (
    "https://tabular-api.data.gouv.fr/api/resources"
    "/ac59a0f5-fa83-4b82-bf12-3c5806d4f19f/data/"
)
DATA_DIR = Path(__file__).parent / "data"
CACHE_FILE = DATA_DIR / "organismes.json"
META_FILE = DATA_DIR / "meta.json"

CERT_COLS = [
    "certifications.actionsDeFormation",
    "certifications.bilansDeCompetences",
    "certifications.VAE",
    "certifications.actionsDeFormationParApprentissage",
]

REGION_NAMES: dict[str, str] = {
    "01": "Guadeloupe", "02": "Martinique", "03": "Guyane",
    "04": "La Réunion", "06": "Mayotte",
    "11": "Île-de-France", "24": "Centre-Val de Loire",
    "27": "Bourgogne-Franche-Comté", "28": "Normandie",
    "32": "Hauts-de-France", "44": "Grand Est",
    "52": "Pays de la Loire", "53": "Bretagne",
    "75": "Nouvelle-Aquitaine", "76": "Occitanie",
    "84": "Auvergne-Rhône-Alpes", "93": "Provence-Alpes-Côte d'Azur",
    "94": "Corse",
}

# ---------------------------------------------------------------------------
# Data store (in-memory)
# ---------------------------------------------------------------------------

_store: dict[str, Any] = {
    "all": [],           # all organisations
    "non_qualiopi": [],  # only non-Qualiopi
    "loaded_at": None,
}


def _is_qualiopi(row: dict) -> bool:
    """Return True if the organism holds at least one Qualiopi certification."""
    return any(row.get(c, "").strip().lower() == "true" for c in CERT_COLS)


def _parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    return list(reader)


def _load_cache() -> bool:
    """Load from local cache if it exists and is < 24h old."""
    if not CACHE_FILE.exists() or not META_FILE.exists():
        return False
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    age = time.time() - meta.get("downloaded_at", 0)
    if age > 86400:
        return False
    data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    _store["all"] = data
    _store["non_qualiopi"] = [r for r in data if not _is_qualiopi(r)]
    _store["loaded_at"] = meta.get("downloaded_at_iso")
    return True


def _save_cache(rows: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    META_FILE.write_text(json.dumps({
        "downloaded_at": time.time(),
        "downloaded_at_iso": datetime.now().isoformat(),
        "total_rows": len(rows),
    }), encoding="utf-8")


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "organismes-formation",
    instructions=(
        "Serveur MCP pour explorer les organismes de formation français. "
        "Permet de télécharger la liste officielle depuis data.gouv.fr, "
        "filtrer les organismes non certifiés Qualiopi, rechercher par nom, "
        "SIRET, région, département, et exporter les résultats."
    ),
)


@mcp.tool()
async def telecharger_donnees(force: bool = False) -> str:
    """Télécharge la liste publique des organismes de formation depuis data.gouv.fr.

    Args:
        force: Si True, re-télécharge même si un cache < 24h existe.
    """
    if not force and _load_cache():
        return (
            f"Données chargées depuis le cache local.\n"
            f"- Total organismes : {len(_store['all']):,}\n"
            f"- Non certifiés Qualiopi : {len(_store['non_qualiopi']):,}\n"
            f"- Dernière mise à jour : {_store['loaded_at']}"
        )

    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            resp = await client.get(CSV_URL)
            resp.raise_for_status()
    except httpx.HTTPError as e:
        return f"Erreur lors du téléchargement : {e}"

    rows = _parse_csv(resp.text)
    _store["all"] = rows
    _store["non_qualiopi"] = [r for r in rows if not _is_qualiopi(r)]
    _store["loaded_at"] = datetime.now().isoformat()
    _save_cache(rows)

    return (
        f"Téléchargement terminé.\n"
        f"- Total organismes : {len(rows):,}\n"
        f"- Non certifiés Qualiopi : {len(_store['non_qualiopi']):,}\n"
        f"- Données mises en cache dans {CACHE_FILE}"
    )


@mcp.tool()
async def rechercher(
    nom: str = "",
    siren: str = "",
    siret: str = "",
    code_postal: str = "",
    ville: str = "",
    code_region: str = "",
    departement: str = "",
    specialite: str = "",
    qualiopi: str = "non",
    limite: int = 20,
    page: int = 1,
) -> str:
    """Recherche parmi les organismes de formation avec filtres multiples.

    Args:
        nom: Recherche dans le nom de l'organisme (insensible à la casse).
        siren: Filtrer par numéro SIREN.
        siret: Filtrer par numéro SIRET.
        code_postal: Filtrer par code postal (ou début de code postal).
        ville: Filtrer par nom de ville (insensible à la casse).
        code_region: Filtrer par code région (ex: 11 = Île-de-France).
        departement: Filtrer par département (2 premiers chiffres du code postal).
        specialite: Recherche dans les libellés de spécialité.
        qualiopi: "non" = non certifiés seulement, "oui" = certifiés seulement, "tous" = tous.
        limite: Nombre max de résultats par page (défaut 20, max 100).
        page: Numéro de page (commence à 1).
    """
    if not _store["all"]:
        return "Aucune donnée chargée. Appelez d'abord `telecharger_donnees`."

    limite = min(max(1, limite), 100)
    page = max(1, page)

    if qualiopi == "non":
        source = _store["non_qualiopi"]
    elif qualiopi == "oui":
        source = [r for r in _store["all"] if _is_qualiopi(r)]
    else:
        source = _store["all"]

    results = source

    if nom:
        nom_l = nom.lower()
        results = [r for r in results if nom_l in r.get("denomination", "").lower()]

    if siren:
        results = [r for r in results if r.get("siren", "").startswith(siren)]

    if siret:
        results = [
            r for r in results
            if r.get("siretEtablissementDeclarant", "").startswith(siret)
        ]

    if code_postal:
        results = [
            r for r in results
            if r.get("adressePhysiqueOrganismeFormation.codePostal", "").startswith(code_postal)
        ]

    if ville:
        ville_l = ville.lower()
        results = [
            r for r in results
            if ville_l in r.get("adressePhysiqueOrganismeFormation.ville", "").lower()
        ]

    if code_region:
        results = [
            r for r in results
            if r.get("adressePhysiqueOrganismeFormation.codeRegion", "") == code_region
        ]

    if departement:
        results = [
            r for r in results
            if r.get("adressePhysiqueOrganismeFormation.codePostal", "").startswith(departement)
        ]

    if specialite:
        spec_l = specialite.lower()
        def _match_specialite(row: dict) -> bool:
            for i in range(1, 4):
                val = row.get(
                    f"informationsDeclarees.specialitesDeFormation.libelleSpecialite{i}", ""
                )
                if spec_l in val.lower():
                    return True
            return False
        results = [r for r in results if _match_specialite(r)]

    total = len(results)
    start = (page - 1) * limite
    page_results = results[start : start + limite]
    total_pages = (total + limite - 1) // limite

    if not page_results:
        return f"Aucun résultat trouvé (total filtré : {total})."

    lines = [f"## Résultats ({total:,} trouvés — page {page}/{total_pages})\n"]
    for r in page_results:
        qualiopi_status = "Oui" if _is_qualiopi(r) else "Non"
        specs = []
        for i in range(1, 4):
            s = r.get(f"informationsDeclarees.specialitesDeFormation.libelleSpecialite{i}", "")
            if s:
                specs.append(s)
        lines.append(
            f"### {r.get('denomination', 'N/A')}\n"
            f"- **NDA** : {r.get('numeroDeclarationActivite', '')}\n"
            f"- **SIREN** : {r.get('siren', '')} | "
            f"**SIRET** : {r.get('siretEtablissementDeclarant', '')}\n"
            f"- **Adresse** : {r.get('adressePhysiqueOrganismeFormation.voie', '')}, "
            f"{r.get('adressePhysiqueOrganismeFormation.codePostal', '')} "
            f"{r.get('adressePhysiqueOrganismeFormation.ville', '')}\n"
            f"- **Région** : {REGION_NAMES.get(r.get('adressePhysiqueOrganismeFormation.codeRegion', ''), 'Inconnue')}\n"
            f"- **Qualiopi** : {qualiopi_status}\n"
            f"- **Stagiaires** : {r.get('informationsDeclarees.nbStagiaires', 'N/A')} | "
            f"**Formateurs** : {r.get('informationsDeclarees.effectifFormateurs', 'N/A')}\n"
            f"- **Spécialités** : {', '.join(specs) if specs else 'N/A'}\n"
        )

    return "\n".join(lines)


@mcp.tool()
async def statistiques(code_region: str = "", departement: str = "") -> str:
    """Affiche des statistiques sur les organismes de formation.

    Args:
        code_region: Filtrer les stats par code région (optionnel).
        departement: Filtrer les stats par département (optionnel).
    """
    if not _store["all"]:
        return "Aucune donnée chargée. Appelez d'abord `telecharger_donnees`."

    source = _store["all"]

    if code_region:
        source = [
            r for r in source
            if r.get("adressePhysiqueOrganismeFormation.codeRegion", "") == code_region
        ]

    if departement:
        source = [
            r for r in source
            if r.get("adressePhysiqueOrganismeFormation.codePostal", "").startswith(departement)
        ]

    total = len(source)
    qualiopi_oui = sum(1 for r in source if _is_qualiopi(r))
    qualiopi_non = total - qualiopi_oui

    # Répartition par certification
    cert_actions = sum(1 for r in source if r.get(CERT_COLS[0], "").strip().lower() == "true")
    cert_bilans = sum(1 for r in source if r.get(CERT_COLS[1], "").strip().lower() == "true")
    cert_vae = sum(1 for r in source if r.get(CERT_COLS[2], "").strip().lower() == "true")
    cert_apprentissage = sum(1 for r in source if r.get(CERT_COLS[3], "").strip().lower() == "true")

    # Top 10 régions (non-Qualiopi)
    region_counts: dict[str, int] = {}
    for r in source:
        if not _is_qualiopi(r):
            code = r.get("adressePhysiqueOrganismeFormation.codeRegion", "??")
            name = REGION_NAMES.get(code, code)
            region_counts[name] = region_counts.get(name, 0) + 1

    top_regions = sorted(region_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Top spécialités (non-Qualiopi)
    spec_counts: dict[str, int] = {}
    for r in source:
        if not _is_qualiopi(r):
            for i in range(1, 4):
                s = r.get(
                    f"informationsDeclarees.specialitesDeFormation.libelleSpecialite{i}", ""
                ).strip()
                if s:
                    spec_counts[s] = spec_counts.get(s, 0) + 1

    top_specs = sorted(spec_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    scope = ""
    if code_region:
        scope = f" (région {REGION_NAMES.get(code_region, code_region)})"
    elif departement:
        scope = f" (département {departement})"

    lines = [
        f"## Statistiques des organismes de formation{scope}\n",
        f"| Indicateur | Valeur |",
        f"|---|---|",
        f"| Total organismes | {total:,} |",
        f"| Certifiés Qualiopi | {qualiopi_oui:,} ({qualiopi_oui*100//max(total,1)}%) |",
        f"| **Non certifiés Qualiopi** | **{qualiopi_non:,} ({qualiopi_non*100//max(total,1)}%)** |",
        f"| Qualiopi — Actions de formation | {cert_actions:,} |",
        f"| Qualiopi — Bilans de compétences | {cert_bilans:,} |",
        f"| Qualiopi — VAE | {cert_vae:,} |",
        f"| Qualiopi — Apprentissage | {cert_apprentissage:,} |",
        f"\n### Top 10 régions (non certifiés Qualiopi)\n",
        "| Région | Nombre |",
        "|---|---|",
    ]
    for name, count in top_regions:
        lines.append(f"| {name} | {count:,} |")

    lines.extend([
        f"\n### Top 10 spécialités (non certifiés Qualiopi)\n",
        "| Spécialité | Nombre |",
        "|---|---|",
    ])
    for name, count in top_specs:
        lines.append(f"| {name} | {count:,} |")

    lines.append(f"\n*Données chargées le {_store['loaded_at']}*")

    return "\n".join(lines)


@mcp.tool()
async def details_organisme(
    nda: str = "",
    siren: str = "",
    siret: str = "",
) -> str:
    """Récupère les détails complets d'un organisme de formation.

    Args:
        nda: Numéro de déclaration d'activité.
        siren: Numéro SIREN.
        siret: Numéro SIRET.
    """
    if not _store["all"]:
        return "Aucune donnée chargée. Appelez d'abord `telecharger_donnees`."

    if not any([nda, siren, siret]):
        return "Veuillez fournir au moins un critère : nda, siren ou siret."

    match = None
    for r in _store["all"]:
        if nda and r.get("numeroDeclarationActivite", "").strip('"') == nda.strip('"'):
            match = r
            break
        if siren and r.get("siren", "") == siren:
            match = r
            break
        if siret and r.get("siretEtablissementDeclarant", "") == siret:
            match = r
            break

    if not match:
        return "Aucun organisme trouvé avec ces critères."

    qualiopi_status = "Oui" if _is_qualiopi(match) else "Non"

    certs = []
    labels = {
        CERT_COLS[0]: "Actions de formation",
        CERT_COLS[1]: "Bilans de compétences",
        CERT_COLS[2]: "VAE",
        CERT_COLS[3]: "Apprentissage",
    }
    for col, label in labels.items():
        val = match.get(col, "").strip().lower()
        if val == "true":
            certs.append(f"  - {label} : ✓")
        elif val == "false":
            certs.append(f"  - {label} : ✗")

    specs = []
    for i in range(1, 4):
        code = match.get(f"informationsDeclarees.specialitesDeFormation.codeSpecialite{i}", "")
        label = match.get(f"informationsDeclarees.specialitesDeFormation.libelleSpecialite{i}", "")
        if code or label:
            specs.append(f"  - [{code}] {label}")

    region_code = match.get("adressePhysiqueOrganismeFormation.codeRegion", "")
    region_name = REGION_NAMES.get(region_code, region_code)

    lines = [
        f"## {match.get('denomination', 'N/A')}\n",
        f"**Identifiants**",
        f"- NDA : {match.get('numeroDeclarationActivite', '')}",
        f"- NDA précédents : {match.get('numerosDeclarationActivitePrecedent', '')}",
        f"- SIREN : {match.get('siren', '')}",
        f"- SIRET : {match.get('siretEtablissementDeclarant', '')}\n",
        f"**Adresse**",
        f"- {match.get('adressePhysiqueOrganismeFormation.voie', '')}",
        f"- {match.get('adressePhysiqueOrganismeFormation.codePostal', '')} "
        f"{match.get('adressePhysiqueOrganismeFormation.ville', '')}",
        f"- Région : {region_name} ({region_code})\n",
        f"**Certification Qualiopi : {qualiopi_status}**",
    ]
    if certs:
        lines.extend(certs)

    lines.extend([
        f"\n**Informations déclarées**",
        f"- Dernière déclaration : {match.get('informationsDeclarees.dateDerniereDeclaration', '')}",
        f"- Exercice : {match.get('informationsDeclarees.debutExercice', '')} → "
        f"{match.get('informationsDeclarees.finExercice', '')}",
        f"- Stagiaires : {match.get('informationsDeclarees.nbStagiaires', 'N/A')}",
        f"- Stagiaires confiés par un autre OF : "
        f"{match.get('informationsDeclarees.nbStagiairesConfiesParUnAutreOF', 'N/A')}",
        f"- Formateurs : {match.get('informationsDeclarees.effectifFormateurs', 'N/A')}",
    ])

    if specs:
        lines.append("\n**Spécialités**")
        lines.extend(specs)

    foreign = match.get("organismeEtrangerRepresente.denomination", "").strip().strip('"')
    if foreign:
        lines.extend([
            f"\n**Organisme étranger représenté**",
            f"- {foreign}",
            f"- {match.get('organismeEtrangerRepresente.voie', '')}",
            f"- {match.get('organismeEtrangerRepresente.codePostal', '')} "
            f"{match.get('organismeEtrangerRepresente.ville', '')}",
            f"- Pays : {match.get('organismeEtrangerRepresente.pays', '')}",
        ])

    return "\n".join(lines)


@mcp.tool()
async def exporter(
    format: str = "csv",
    qualiopi: str = "non",
    nom: str = "",
    code_region: str = "",
    departement: str = "",
    specialite: str = "",
    limite: int = 0,
    fichier: str = "",
) -> str:
    """Exporte les résultats filtrés dans un fichier CSV ou JSON.

    Args:
        format: Format d'export : "csv" ou "json".
        qualiopi: "non" = non certifiés, "oui" = certifiés, "tous" = tous.
        nom: Filtrer par nom (insensible à la casse).
        code_region: Filtrer par code région.
        departement: Filtrer par département.
        specialite: Filtrer par spécialité.
        limite: Nombre max de résultats (0 = tous).
        fichier: Chemin du fichier de sortie (optionnel, un nom par défaut est généré).
    """
    if not _store["all"]:
        return "Aucune donnée chargée. Appelez d'abord `telecharger_donnees`."

    if qualiopi == "non":
        source = _store["non_qualiopi"]
    elif qualiopi == "oui":
        source = [r for r in _store["all"] if _is_qualiopi(r)]
    else:
        source = _store["all"]

    results = source

    if nom:
        nom_l = nom.lower()
        results = [r for r in results if nom_l in r.get("denomination", "").lower()]

    if code_region:
        results = [
            r for r in results
            if r.get("adressePhysiqueOrganismeFormation.codeRegion", "") == code_region
        ]

    if departement:
        results = [
            r for r in results
            if r.get("adressePhysiqueOrganismeFormation.codePostal", "").startswith(departement)
        ]

    if specialite:
        spec_l = specialite.lower()
        def _match(row: dict) -> bool:
            for i in range(1, 4):
                val = row.get(
                    f"informationsDeclarees.specialitesDeFormation.libelleSpecialite{i}", ""
                )
                if spec_l in val.lower():
                    return True
            return False
        results = [r for r in results if _match(r)]

    if limite > 0:
        results = results[:limite]

    if not results:
        return "Aucun résultat à exporter."

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if not fichier:
        fichier = str(DATA_DIR / f"export_{qualiopi}_{timestamp}.{format}")

    out_path = Path(fichier)

    if format == "json":
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        output = io.StringIO()
        if results:
            writer = csv.DictWriter(output, fieldnames=results[0].keys(), delimiter=";")
            writer.writeheader()
            writer.writerows(results)
        out_path.write_text(output.getvalue(), encoding="utf-8")

    return (
        f"Export terminé.\n"
        f"- Fichier : {out_path.absolute()}\n"
        f"- Format : {format.upper()}\n"
        f"- Nombre d'enregistrements : {len(results):,}"
    )


@mcp.tool()
async def lister_regions() -> str:
    """Affiche la liste des codes régions et leurs noms pour faciliter les filtres."""
    lines = ["## Codes régions\n", "| Code | Région |", "|---|---|"]
    for code, name in sorted(REGION_NAMES.items()):
        lines.append(f"| {code} | {name} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
