from werkzeug.security import generate_password_hash
from flask import Flask, render_template, request, jsonify, Response, redirect, url_for, session, flash
import sqlite3
import csv
from datetime import datetime
import io
import math
import requests
import unicodedata
import uuid
import json
import re
import html
from functools import wraps
from pathlib import Path
from math import radians, sin, cos, sqrt, atan2
from urllib.parse import unquote
from werkzeug.security import check_password_hash

session_http = requests.Session()

app = Flask(__name__)
app.secret_key = "CHANGE_MOI_PAR_UNE_CLE_SECRETE_LONGUE_ET_UNIQUE"

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = "/data/commerces_render.db"
AUTH_DB_FILE = Path("/data/auth.db")
CAMPAIGN_DB_FILE = "/data/campaigns.db"
LAST_RESULTS = []

DEFAULT_LAT = 46.6
DEFAULT_LON = 2.4

TYPE_LABELS = {
    "all": "Tous",
    "pharmacy": "Pharmacies",
    "restaurant": "Restaurants",
    "bar": "Bars",
    "bakery": "Boulangeries",
    "fast_food": "Snacks",
    "camping": "Campings",
    "tourism_office": "Offices de tourisme",
    "hotel": "Hôtels",
    "tobacco": "Tabacs / Presse",
    "hair_salon": "Salon de coiffure",
}

GENERIC_NAMES = {
    "",
    "commerce",
    "pharmacie",
    "restaurant",
    "bar",
    "boulangerie",
    "snack",
    "camping",
    "hotel",
    "hôtel",
    "coiffeur",
    "boutique",
    "magasin",
    "brut",
}

SUPPORT_LABELS = {
    "all": "Tous les supports",
    "sac_pharmacie": "Sacs pharmacie",
    "sac_pain": "Sacs à pain",
    "sac_galette": "Sacs galettes",
    "set_table": "Sets de table",
    "sous_bock": "Sous-bocks",
    "flyer": "Flyers",
    "affiche": "Affiches",
}

SUPPORTS_BY_TYPE = {
    "all": ["all"],
    "pharmacy": ["all", "sac_pharmacie"],
    "bakery": ["all", "sac_pain", "sac_galette", "affiche"],
    "bar": ["all", "sous_bock", "affiche"],
    "restaurant": ["all", "set_table", "sous_bock", "affiche"],
    "fast_food": ["all", "set_table", "sous_bock", "affiche"],
    "camping": ["all", "set_table", "flyer", "affiche", "sac_pain"],
    "tourism_office": ["all", "flyer", "affiche"],
    "hotel": ["all", "flyer", "affiche"],
    "tobacco": ["all", "flyer", "affiche"],
    "hair_salon": ["all", "flyer", "affiche"],
}

SUPPORTS_DISPLAY_BY_TYPE = {
    "pharmacy": ["Sacs pharmacie"],
    "bakery": ["Sacs à pain", "Sacs galettes", "Affiches"],
    "bar": ["Sous-bocks", "Affiches"],
    "restaurant": ["Sets de table", "Sous-bocks", "Affiches"],
    "fast_food": ["Sets de table", "Sous-bocks", "Affiches"],
    "camping": ["Sets de table", "Flyers", "Affiches", "Sacs à pain"],
    "tourism_office": ["Flyers", "Affiches"],
    "hotel": ["Flyers", "Affiches"],
    "tobacco": ["Flyers", "Affiches"],
    "hair_salon": ["Flyers", "Affiches"],
}

QUANTITE_PAR_SUPPORT = {
    "sac_pain": 1000,
    "set_table": 1000,
    "sous_bock": 250,
    "flyer": 50,
    "affiche": 1,
    "sac_pharmacie": 1000,
    "sac_galette": 1000,
}

def compute_item_potentiel_for_support(item, selected_support):
    supports = item.get("supports", [])

    if selected_support == "all":
        total = 0
        for support_key, support_label in SUPPORT_LABELS.items():
            if support_key == "all":
                continue
            if support_label in supports:
                total += QUANTITE_PAR_SUPPORT.get(support_key, 0)
        return total

    support_label = SUPPORT_LABELS.get(selected_support, selected_support)

    if support_label in supports:
        return QUANTITE_PAR_SUPPORT.get(selected_support, 0)

    return 0

DEPARTEMENTS = [
    ("01", "Ain"), ("02", "Aisne"), ("03", "Allier"), ("04", "Alpes-de-Haute-Provence"),
    ("05", "Hautes-Alpes"), ("06", "Alpes-Maritimes"), ("07", "Ardèche"), ("08", "Ardennes"),
    ("09", "Ariège"), ("10", "Aube"), ("11", "Aude"), ("12", "Aveyron"),
    ("13", "Bouches-du-Rhône"), ("14", "Calvados"), ("15", "Cantal"), ("16", "Charente"),
    ("17", "Charente-Maritime"), ("18", "Cher"), ("19", "Corrèze"), ("21", "Côte-d'Or"),
    ("22", "Côtes-d'Armor"), ("23", "Creuse"), ("24", "Dordogne"), ("25", "Doubs"),
    ("26", "Drôme"), ("27", "Eure"), ("28", "Eure-et-Loir"), ("29", "Finistère"),
    ("30", "Gard"), ("31", "Haute-Garonne"), ("32", "Gers"), ("33", "Gironde"),
    ("34", "Hérault"), ("35", "Ille-et-Vilaine"), ("36", "Indre"), ("37", "Indre-et-Loire"),
    ("38", "Isère"), ("39", "Jura"), ("40", "Landes"), ("41", "Loir-et-Cher"),
    ("42", "Loire"), ("43", "Haute-Loire"), ("44", "Loire-Atlantique"), ("45", "Loiret"),
    ("46", "Lot"), ("47", "Lot-et-Garonne"), ("48", "Lozère"), ("49", "Maine-et-Loire"),
    ("50", "Manche"), ("51", "Marne"), ("52", "Haute-Marne"), ("53", "Mayenne"),
    ("54", "Meurthe-et-Moselle"), ("55", "Meuse"), ("56", "Morbihan"), ("57", "Moselle"),
    ("58", "Nièvre"), ("59", "Nord"), ("60", "Oise"), ("61", "Orne"),
    ("62", "Pas-de-Calais"), ("63", "Puy-de-Dôme"), ("64", "Pyrénées-Atlantiques"),
    ("65", "Hautes-Pyrénées"), ("66", "Pyrénées-Orientales"), ("67", "Bas-Rhin"),
    ("68", "Haut-Rhin"), ("69", "Rhône"), ("70", "Haute-Saône"), ("71", "Saône-et-Loire"),
    ("72", "Sarthe"), ("73", "Savoie"), ("74", "Haute-Savoie"), ("75", "Paris"),
    ("76", "Seine-Maritime"), ("77", "Seine-et-Marne"), ("78", "Yvelines"),
    ("79", "Deux-Sèvres"), ("80", "Somme"), ("81", "Tarn"), ("82", "Tarn-et-Garonne"),
    ("83", "Var"), ("84", "Vaucluse"), ("85", "Vendée"), ("86", "Vienne"),
    ("87", "Haute-Vienne"), ("88", "Vosges"), ("89", "Yonne"), ("90", "Territoire de Belfort"),
    ("91", "Essonne"), ("92", "Hauts-de-Seine"), ("93", "Seine-Saint-Denis"),
    ("94", "Val-de-Marne"), ("95", "Val-d'Oise"),
]

ALL_TYPES = [
    "pharmacy", "restaurant", "bar", "bakery", "fast_food", "camping",
    "tourism_office", "hotel", "tobacco", "hair_salon",
]

RESTRICTED_HIDDEN_TYPES = {"pharmacy"}

RESTRICTED_HIDDEN_SUPPORTS = {
    "sac_pharmacie",
    "sac_pain",
    "sac_galette",
}

RESTRICTED_HIDDEN_SUPPORT_LABELS = {
    "Sacs pharmacie",
    "Sacs à pain",
    "Sacs galettes",
}


def is_restricted_user():
    return session.get("role") in ["manager", "user"]


def filter_types_for_current_user(types):
    if not is_restricted_user():
        return types

    filtered = [t for t in types if t not in RESTRICTED_HIDDEN_TYPES]

    if not filtered:
        return ["__blocked__"]

    return filtered


def filter_support_keys_for_current_user(support_keys):
    if not is_restricted_user():
        return support_keys

    return [
        key for key in support_keys
        if key not in RESTRICTED_HIDDEN_SUPPORTS
    ]


def normalize_support_for_current_user(support_key):
    if is_restricted_user() and support_key in RESTRICTED_HIDDEN_SUPPORTS:
        return "all"

    return support_key

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def get_auth_connection():
    conn = sqlite3.connect(AUTH_DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def get_campaign_connection():
    conn = sqlite3.connect(CAMPAIGN_DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_campaign_items_table():
    conn = get_campaign_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS campaign_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            name TEXT,
            type TEXT,
            ville TEXT,
            code_postal TEXT,
            adresse TEXT,
            telephone TEXT,
            lat REAL,
            lon REAL,
            priority INTEGER DEFAULT 0,
            updated_at TEXT
        )
    """)
    for column_sql in [
        "ALTER TABLE campaign_items ADD COLUMN updated_at TEXT",
        "ALTER TABLE campaign_items ADD COLUMN accepte TEXT DEFAULT ''",
        "ALTER TABLE campaign_items ADD COLUMN commentaire TEXT DEFAULT ''",
        "ALTER TABLE campaign_items ADD COLUMN quantite INTEGER DEFAULT 0"
        "ALTER TABLE campaign_items ADD COLUMN potentiel_support INTEGER DEFAULT 0",
    ]:
        try:
            cur.execute(column_sql)
        except Exception:
            pass

    conn.commit()
    conn.close()

def init_campaigns_extra_columns():
    conn = get_campaign_connection()
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE campaigns ADD COLUMN search_zones TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()


def normalize_name(value):
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def strip_accents(value):
    value = "" if value is None else str(value)
    return "".join(
        c for c in unicodedata.normalize("NFD", value)
        if unicodedata.category(c) != "Mn"
    )


def normalize_search_text(value):
    value = normalize_name(value)
    value = strip_accents(value).lower()
    value = value.replace("-", " ")
    value = value.replace("'", " ")
    value = value.replace("’", " ")
    value = value.replace(" de la ", " la ")
    return " ".join(value.split())


def is_generic_name(value):
    return normalize_name(value) in GENERIC_NAMES


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371
    dlat = radians(float(lat2) - float(lat1))
    dlon = radians(float(lon2) - float(lon1))
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(float(lat1)))
        * cos(radians(float(lat2)))
        * sin(dlon / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return r * c


def filtrer_homonymes_par_distance(data, centre_lat, centre_lon, rayon_km=20):
    resultats = []
    for item in data:
        item_lat = item.get("lat")
        item_lon = item.get("lon")
        if item_lat in (None, "") or item_lon in (None, ""):
            continue
        try:
            distance = haversine_km(float(centre_lat), float(centre_lon), float(item_lat), float(item_lon))
        except (TypeError, ValueError):
            continue
        if distance <= rayon_km:
            item["distance_km"] = round(distance, 2)
            resultats.append(item)
    return resultats


def get_coords_commune(valeur):
    valeur = (valeur or "").strip()
    if not valeur:
        return None, None
    try:
        if valeur.isdigit() and len(valeur) == 5:
            response = session_http.get(
                "https://geo.api.gouv.fr/communes",
                params={"codePostal": valeur, "fields": "centre", "format": "json", "geometry": "centre"},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                if data and data[0].get("centre"):
                    lon, lat = data[0]["centre"]["coordinates"]
                    return lat, lon

        response = session_http.get(
            "https://geo.api.gouv.fr/communes",
            params={"nom": valeur, "boost": "population", "limit": 1, "fields": "centre", "format": "json", "geometry": "centre"},
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            if data and data[0].get("centre"):
                lon, lat = data[0]["centre"]["coordinates"]
                return lat, lon
    except Exception:
        pass
    return None, None


def get_commune_info_by_name(ville):
    ville = (ville or "").strip()
    if not ville:
        return "", "", ""

    manual = normalize_search_text(ville)
    if manual in {"sainte marie de la mer", "sainte marie la mer"}:
        return "SAINTE-MARIE-LA-MER", "66470", "66"

    try:
        response = session_http.get(
            "https://geo.api.gouv.fr/communes",
            params={"nom": ville, "boost": "population", "limit": 1, "fields": "nom,codesPostaux,codeDepartement"},
            timeout=8,
        )
        if response.status_code == 200:
            data = response.json()
            if data:
                nom = (data[0].get("nom") or ville).upper()
                cps = data[0].get("codesPostaux") or []
                cp = cps[0] if cps else ""
                dep = data[0].get("codeDepartement") or (cp[:2] if cp else "")
                return nom, cp, dep
    except Exception:
        pass

    return ville.upper(), "", ""


def get_commune_info_by_coords(lat, lon):
    try:
        response = session_http.get(
            "https://geo.api.gouv.fr/communes",
            params={"lat": lat, "lon": lon, "fields": "nom,codesPostaux,codeDepartement", "format": "json"},
            timeout=8,
        )
        if response.status_code == 200:
            data = response.json()
            if data:
                nom = (data[0].get("nom") or "").upper()
                cps = data[0].get("codesPostaux") or []
                cp = cps[0] if cps else ""
                dep = data[0].get("codeDepartement") or (cp[:2] if cp else "")
                return nom, cp, dep
    except Exception:
        pass
    return "", "", ""


def normalize_added_city_and_postal(ville, code_postal, lat=None, lon=None):
    ville = (ville or "").strip().upper()
    code_postal = (code_postal or "").strip()

    if normalize_search_text(ville) in {"sainte marie de la mer", "sainte marie la mer"}:
        return "SAINTE-MARIE-LA-MER", "66470", "66"

    if code_postal:
        return ville, code_postal, code_postal[:2]

    api_ville, api_cp, api_dep = get_commune_info_by_name(ville)
    if api_cp:
        return api_ville, api_cp, api_dep

    if lat not in (None, "") and lon not in (None, ""):
        api_ville, api_cp, api_dep = get_commune_info_by_coords(lat, lon)
        if api_cp:
            return api_ville, api_cp, api_dep

    return ville, "", ""


def distance_km(lat1, lon1, lat2, lon2):
    r = 6371
    dlat = math.radians(float(lat2) - float(lat1))
    dlon = math.radians(float(lon2) - float(lon1))
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(float(lat1)))
        * math.cos(math.radians(float(lat2)))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return r * c


def get_selected_types_from_form(form):
    selected_types = form.getlist("types")
    if not selected_types:
        single_value = form.get("type_unique", "all")
        if single_value and single_value != "all":
            selected_types = [single_value]
    selected_types = [t for t in selected_types if t in ALL_TYPES]
    if not selected_types:
        return ["all"]
    return sorted(set(selected_types))


def get_type_filter(selected_types):
    if not selected_types or "all" in selected_types:
        return filter_types_for_current_user(ALL_TYPES)

    selected = [t for t in selected_types if t in ALL_TYPES]
    return filter_types_for_current_user(selected)


def get_supports_for_type(commerce_type):
    supports = SUPPORTS_DISPLAY_BY_TYPE.get(commerce_type, [])

    if not is_restricted_user():
        return supports

    return [
        support for support in supports
        if support not in RESTRICTED_HIDDEN_SUPPORT_LABELS
    ]


def get_available_supports(selected_types):
    if not selected_types or "all" in selected_types:
        return filter_support_keys_for_current_user([
            "all",
            "sac_pharmacie",
            "sac_pain",
            "sac_galette",
            "set_table",
            "sous_bock",
            "flyer",
            "affiche",
        ])

    merged = {"all"}

    for commerce_type in selected_types:
        for support in SUPPORTS_BY_TYPE.get(commerce_type, []):
            merged.add(support)

    merged = set(filter_support_keys_for_current_user(merged))

    ordered = ["all"]

    for key in ["sac_pharmacie", "sac_pain", "sac_galette", "set_table", "sous_bock", "flyer", "affiche"]:
        if key in merged:
            ordered.append(key)

    return ordered

def get_types_for_support(selected_support):
    if not selected_support or selected_support == "all":
        return filter_types_for_current_user(ALL_TYPES)

    matched_types = []

    for commerce_type, supports in SUPPORTS_BY_TYPE.items():
        if commerce_type == "all":
            continue

        if selected_support in supports:
            matched_types.append(commerce_type)

    return filter_types_for_current_user(matched_types)
    
def build_results_from_rows(rows):
    results = []
    seen_keys = set()
    for row in rows:
        nom = (row["nom"] or "").strip()
        if not nom or is_generic_name(nom):
            continue
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
        except (TypeError, ValueError):
            continue
        commerce_type = row["type"]
        key = (normalize_name(nom), normalize_name(row["ville"]), str(row["code_postal"] or "").strip(), commerce_type)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        supports_list = get_supports_for_type(commerce_type)
        potentiel_supports = 0
        for support_label in supports_list:
            for support_key, label in SUPPORT_LABELS.items():
                if label == support_label:
                    potentiel_supports += {
                        "sac_pain": 1000,
                        "set_table": 1000,
                        "sous_bock": 250,
                        "flyer": 50,
                        "affiche": 1,
                        "sac_pharmacie": 1000,
                        "sac_galette": 1000,
                    }.get(support_key, 0)
        results.append({
            "id": row["id"], "name": nom, "lat": lat, "lon": lon, "type": commerce_type,
            "ville": row["ville"] or "", "code_postal": row["code_postal"] or "", "adresse": row["adresse"] or "",
            "telephone": row["telephone"] or "",
            "accepte_support": row["accepte_support"] if "accepte_support" in row.keys() else "",
            "commentaire_support": row["commentaire_support"] if "commentaire_support" in row.keys() else "",
            "quantite_support": row["quantite_support"] if "quantite_support" in row.keys() else 0,
            "etoiles": row["etoiles"] if "etoiles" in row.keys() else "",
            "source": "sqlite",
            "supports": supports_list,
            "nb_supports": len(supports_list),
            "potentiel_support": potentiel_supports,
        })
    return results


def get_results_for_city(city_value, selected_types):
    raw_value = (city_value or "").strip()

    forced_city = ""
    forced_cp = ""

    match = re.search(r"^(.*?)\s*\((\d{5})\)\s*$", raw_value)
    if match:
        forced_city = match.group(1).strip()
        forced_cp = match.group(2).strip()

    requested_city_clean = normalize_search_text(forced_city or raw_value)
    requested_cp = forced_cp or (raw_value if raw_value.isdigit() and len(raw_value) == 5 else "")

    if not requested_city_clean and not requested_cp:
        return []

    type_filter = get_type_filter(selected_types)
    placeholders = ",".join("?" for _ in type_filter)

    params = list(type_filter)
    extra_sql = ""

    if requested_cp:
        extra_sql = " AND code_postal = ?"
        params.append(requested_cp)
    elif requested_city_clean:
        words = [w for w in requested_city_clean.split() if len(w) >= 3]

        if words:
            extra_sql = " AND " + " AND ".join(["LOWER(ville) LIKE ?" for _ in words])
            params.extend([f"%{word}%" for word in words])

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT rowid AS id, nom, latitude, longitude, type, ville, code_postal, adresse, telephone,
               accepte_support, commentaire_support, quantite_support, etoiles
        FROM commerces
        WHERE is_active = 1
          AND COALESCE(exclude_from_results, 0) = 0
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND type IN ({placeholders})
          {extra_sql}
        ORDER BY nom
    """, params)

    rows = cursor.fetchall()
    conn.close()

    filtered_rows = []

    for row in rows:
        ville_db = normalize_search_text(row["ville"] or "")
        cp_db = str(row["code_postal"] or "").strip()

        city_match = False
        cp_match = False

        if requested_city_clean:
            searched_words = requested_city_clean.split()
            city_match = (
                requested_city_clean in ville_db
                or ville_db in requested_city_clean
                or all(word in ville_db for word in searched_words)
            )

        if requested_cp:
            cp_match = (cp_db == requested_cp)

        if forced_city and forced_cp:
            if ville_db == requested_city_clean:
                filtered_rows.append(row)
        else:
            if city_match or cp_match:
                filtered_rows.append(row)

    return build_results_from_rows(filtered_rows)


def get_results_for_departement(departement_code, selected_types):
    type_filter = get_type_filter(selected_types)
    placeholders = ",".join("?" for _ in type_filter)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT rowid AS id, nom, latitude, longitude, type, ville, code_postal, adresse, telephone,
       accepte_support, commentaire_support, quantite_support, etoiles
        FROM commerces
        WHERE is_active = 1
          AND COALESCE(exclude_from_results, 0) = 0
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND COALESCE(departement, '') = ?
          AND code_postal LIKE ?
          AND type IN ({placeholders})
        ORDER BY nom
    """, [departement_code, f"{departement_code}%"] + type_filter)
    rows = cursor.fetchall()
    conn.close()
    return build_results_from_rows(rows)


def enrich_and_sort_departement_results(data):
    if not data:
        return data, None, None
    valid_points = []
    for item in data:
        try:
            valid_points.append((float(item["lat"]), float(item["lon"])))
        except (TypeError, ValueError, KeyError):
            continue
    if not valid_points:
        return data, None, None
    center_lat = sum(p[0] for p in valid_points) / len(valid_points)
    center_lon = sum(p[1] for p in valid_points) / len(valid_points)
    for item in data:
        try:
            item["distance_km"] = round(haversine_km(center_lat, center_lon, float(item["lat"]), float(item["lon"])), 2)
        except (TypeError, ValueError, KeyError):
            item["distance_km"] = None
    data.sort(key=lambda x: x.get("distance_km") if x.get("distance_km") is not None else 999999)
    return data, center_lat, center_lon


def get_results_in_radius(city_value, radius_km, selected_types):
    center_lat, center_lon = get_coords_commune(city_value)
    if center_lat is None or center_lon is None:
        return [], None, None

    type_filter = get_type_filter(selected_types)
    placeholders = ",".join("?" for _ in type_filter)
    lat_delta = radius_km / 111.0
    lon_divisor = max(math.cos(math.radians(center_lat)), 0.1)
    lon_delta = radius_km / (111.0 * lon_divisor)
    min_lat = center_lat - lat_delta
    max_lat = center_lat + lat_delta
    min_lon = center_lon - lon_delta
    max_lon = center_lon + lon_delta

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT rowid AS id, nom, latitude, longitude, type, ville, code_postal, adresse, telephone,
       accepte_support, commentaire_support, quantite_support, etoiles
        FROM commerces
        WHERE is_active = 1
          AND COALESCE(exclude_from_results, 0) = 0
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND type IN ({placeholders})
          AND latitude BETWEEN ? AND ?
          AND longitude BETWEEN ? AND ?
    """, type_filter + [min_lat, max_lat, min_lon, max_lon])
    rows = cursor.fetchall()
    conn.close()

    formatted = []
    seen_keys = set()
    for row in rows:
        nom = (row["nom"] or "").strip()
        if not nom or is_generic_name(nom):
            continue
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
        except (TypeError, ValueError):
            continue
        dist = distance_km(center_lat, center_lon, lat, lon)
        if dist > radius_km:
            continue
        commerce_type = row["type"]
        key = (normalize_name(nom), normalize_name(row["ville"]), str(row["code_postal"] or "").strip(), commerce_type)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        supports_list = get_supports_for_type(commerce_type)
        formatted.append({
            "id": row["id"],
            "name": nom,
            "lat": lat,
            "lon": lon,
            "type": commerce_type,
            "ville": row["ville"] or "",
            "code_postal": row["code_postal"] or "",
            "adresse": row["adresse"] or "",
            "telephone": row["telephone"] or "",
            "etoiles": row["etoiles"] if "etoiles" in row.keys() else "",
            "accepte_support": row["accepte_support"] if "accepte_support" in row.keys() else "",
            "commentaire_support": row["commentaire_support"] if "commentaire_support" in row.keys() else "",
            "quantite_support": row["quantite_support"] if "quantite_support" in row.keys() else 0,
            "source": "sqlite",
            "supports": supports_list,
            "nb_supports": len(supports_list),
            "distance_km": round(dist, 2),
    })
    formatted.sort(key=lambda x: x.get("distance_km", 999999))
    return formatted, center_lat, center_lon


def make_result_key(item):
    return (normalize_name(item.get("name")), normalize_name(item.get("ville")), str(item.get("code_postal") or "").strip(), item.get("type") or "")


def merge_results_lists(data_lists):
    merged = []
    by_key = {}
    for data in data_lists:
        for item in data:
            item_copy = dict(item)
            key = make_result_key(item_copy)
            if key not in by_key:
                by_key[key] = item_copy
                merged.append(item_copy)
            else:
                existing = by_key[key]
                new_dist = item_copy.get("distance_km")
                old_dist = existing.get("distance_km")
                if new_dist is not None and (old_dist is None or new_dist < old_dist):
                    existing["distance_km"] = new_dist
    merged.sort(key=lambda x: (x.get("distance_km") is None, x.get("distance_km", 999999), x.get("name", "")))
    return merged


def compute_center_from_data(data):
    valid_points = []
    for item in data:
        try:
            valid_points.append((float(item["lat"]), float(item["lon"])))
        except (TypeError, ValueError, KeyError):
            continue
    if not valid_points:
        return None, None
    center_lat = sum(p[0] for p in valid_points) / len(valid_points)
    center_lon = sum(p[1] for p in valid_points) / len(valid_points)
    return center_lat, center_lon


def build_search_label(criteria):
    mode = criteria.get("mode", "ville")
    if mode == "rayon":
        base = (criteria.get("search_value") or "").strip()
        rayon = (criteria.get("rayon_value") or "").strip()
        return f"{base} - {rayon} km"
    if mode == "departement":
        code = (criteria.get("departement_value") or "").strip()
        label = next((f"{c} - {n}" for c, n in DEPARTEMENTS if c == code), code)
        return label or "Département"
    return (criteria.get("search_value") or "").strip() or "Ville / CP"


def execute_search_criteria(criteria):
    data = []
    lat, lon = DEFAULT_LAT, DEFAULT_LON
    show_circle = False
    selected_types = criteria.get("selected_types", ["all"])
    selected_support = criteria.get("selected_support", "all")
    search_value = (criteria.get("search_value") or "").strip()
    mode = criteria.get("mode", "ville")
    departement_value = (criteria.get("departement_value") or "").strip()
    rayon_value = (criteria.get("rayon_value") or "").strip()

    if mode == "ville" and search_value:
        search_for_coords = search_value
        has_forced_cp = False

        match = re.search(r"^(.*?)\s*\((\d{5})\)\s*$", search_value)
        if match:
            search_for_coords = search_value
            has_forced_cp = True

        found_lat, found_lon = get_coords_commune(search_for_coords)
        if found_lat is not None and found_lon is not None:
            lat, lon = found_lat, found_lon

        data = get_results_for_city(search_value, selected_types)

        if data:
            latitudes = [float(x["lat"]) for x in data if x.get("lat") is not None]
            longitudes = [float(x["lon"]) for x in data if x.get("lon") is not None]

            if latitudes and longitudes:
                lat = sum(latitudes) / len(latitudes)
                lon = sum(longitudes) / len(longitudes)

        if lat is not None and lon is not None:
            requested_cp = (
                search_value.strip().isdigit()
                and len(search_value.strip()) == 5
            ) or has_forced_cp

            if not requested_cp:
                data = filtrer_homonymes_par_distance(data, lat, lon, rayon_km=20)

            data = sorted(data, key=lambda x: x.get("distance_km", 999999))

    elif mode == "departement" and departement_value:
        data = get_results_for_departement(departement_value, selected_types)
        data, dept_lat, dept_lon = enrich_and_sort_departement_results(data)
        if dept_lat is not None and dept_lon is not None:
            lat = dept_lat
            lon = dept_lon

    elif mode == "rayon" and search_value and rayon_value:
        try:
            rayon_km = float(rayon_value)
            data, center_lat, center_lon = get_results_in_radius(search_value, rayon_km, selected_types)
            if center_lat is not None and center_lon is not None:
                lat, lon = center_lat, center_lon
                show_circle = True
        except ValueError:
            data = []

    if selected_support != "all":
        selected_label = SUPPORT_LABELS.get(selected_support)
        data = [item for item in data if selected_label in item.get("supports", [])]
    return data, lat, lon, show_circle


def compute_potentiel_and_supports(data):
    counts = {}
    for item in data:
        t = item.get("type", "")
        if t:
            counts[t] = counts.get(t, 0) + 1
    potentiel = 0
    totals_by_label = {}

    def add_support(label, qty):
        totals_by_label[label] = totals_by_label.get(label, 0) + int(qty)

    for t, count in counts.items():
        if t == "restaurant":
            p = math.floor(count * 0.3); potentiel += p; add_support("Sets de table", p * 1000); add_support("Sous-bocks", p * 250); add_support("Affiches", math.floor(count * 0.2))
        elif t == "pharmacy":
            p = math.floor(count * 0.4); potentiel += p; add_support("Sacs pharmacie", p * 1000)
        elif t == "bar":
            p = math.floor(count * 0.3); potentiel += p; add_support("Sous-bocks", p * 250); add_support("Affiches", math.floor(count * 0.2))
        elif t == "bakery":
            p = max(1, math.floor(count * 0.5)); potentiel += p; add_support("Sacs à pain", p * 1000); add_support("Sacs galettes", p * 1000); add_support("Affiches", math.floor(count * 0.2))
        elif t == "fast_food":
            p = math.floor(count * 0.3); potentiel += p; add_support("Sets de table", p * 1000); add_support("Sous-bocks", p * 250); add_support("Affiches", math.floor(count * 0.2))
        elif t == "camping":
            p = math.floor(count * 0.3); potentiel += p; add_support("Sets de table", p * 1000); add_support("Flyers", p * 50); add_support("Affiches", math.floor(count * 0.2)); add_support("Sacs à pain", p * 1000);
        elif t == "tourism_office":
            p = math.floor(count * 0.3); potentiel += p; add_support("Flyers", p * 50); add_support("Affiches", math.floor(count * 0.2))
        elif t == "hotel":
            p = math.floor(count * 0.3); potentiel += p; add_support("Flyers", p * 50); add_support("Affiches", math.floor(count * 0.2))
        elif t == "tobacco":
            p = math.floor(count * 0.3); potentiel += p; add_support("Flyers", p * 50); add_support("Affiches", math.floor(count * 0.2))
        elif t == "hair_salon":
            p = math.floor(count * 0.3); potentiel += p; add_support("Flyers", p * 50); add_support("Affiches", math.floor(count * 0.2))
    return potentiel, totals_by_label


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper

def init_commerces_extra_columns():
    conn = get_db_connection()
    cur = conn.cursor()

    for column_sql in [
        "ALTER TABLE commerces ADD COLUMN departement TEXT",
        "ALTER TABLE commerces ADD COLUMN is_active INTEGER DEFAULT 1",
        "ALTER TABLE commerces ADD COLUMN exclude_from_results INTEGER DEFAULT 0",
        "ALTER TABLE commerces ADD COLUMN accepte_support TEXT DEFAULT ''",
        "ALTER TABLE commerces ADD COLUMN commentaire_support TEXT DEFAULT ''",
        "ALTER TABLE commerces ADD COLUMN quantite_support INTEGER DEFAULT 0"
    ]:
        try:
            cur.execute(column_sql)
        except Exception:
            pass

    try:
        cur.execute("""
            UPDATE commerces
            SET departement = substr(code_postal, 1, 2)
            WHERE code_postal IS NOT NULL
              AND code_postal != ''
              AND (departement IS NULL OR departement = '')
        """)
    except Exception:
        pass

    conn.commit()
    conn.close()

@app.before_request
def ensure_databases_exist():
    if not Path(AUTH_DB_FILE).exists():
        conn = sqlite3.connect(AUTH_DB_FILE)
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            role TEXT NOT NULL DEFAULT 'user'
        )
        """)
        conn.commit()
        conn.close()

    conn = sqlite3.connect(AUTH_DB_FILE)
    cur = conn.cursor()

    try:
        cur.execute("ALTER TABLE users ADD COLUMN last_login_at TEXT")
    except Exception:
        pass
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_hidden_commerces (
            user_id INTEGER NOT NULL,
            commerce_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, commerce_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            role TEXT,
            action TEXT,
            details TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.commit()

    admin_exists = cur.execute(
        "SELECT * FROM users WHERE username = ?",
        ("admin",)
    ).fetchone()

    if not admin_exists:
        cur.execute("""
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
        """, (
            "admin",
            generate_password_hash("admin123"),
            "admin"
        ))
        conn.commit()

    conn.close()

conn = sqlite3.connect(CAMPAIGN_DB_FILE)
cur = conn.cursor()
cur.execute("""
    CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        notes TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        token TEXT UNIQUE
    )
    """)
conn.commit()
conn.close()


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))

    error = ""

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "")

        conn = get_auth_connection()
        cur = conn.cursor()

        user = cur.execute("""
            SELECT id, username, password_hash, is_active, role
            FROM users
            WHERE username = ?
        """, (username,)).fetchone()

        if not user:
            conn.close()
            error = "Identifiant ou mot de passe invalide."
        elif int(user["is_active"]) != 1:
            conn.close()
            error = "Compte désactivé."
        elif not check_password_hash(user["password_hash"], password):
            conn.close()
            error = "Identifiant ou mot de passe invalide."
        else:
            cur.execute("""
                UPDATE users
                SET last_login_at = datetime('now', 'localtime')
                WHERE id = ?
            """, (user["id"],))

            cur.execute("""
                INSERT INTO activity_logs (user_id, username, role, action, details)
                VALUES (?, ?, ?, ?, ?)
            """, (user["id"], user["username"], user["role"], "Connexion", "Connexion à l'application"))
            
            conn.commit()
            conn.close()

            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            return redirect(url_for("index"))

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    conn_auth = get_auth_connection()
    conn_auth.execute("""
        INSERT INTO activity_logs (user_id, username, role, action, details)
        VALUES (?, ?, ?, ?, ?)
    """, (
        session.get("user_id"),
        session.get("username"),
        session.get("role"),
        "Déconnexion",
        "Déconnexion de l'application"
    ))
    conn_auth.commit()
    conn_auth.close()
    session.clear()
    return redirect(url_for("login"))


@app.route("/autocomplete")
@login_required
def autocomplete():
    q = (request.args.get("q") or "").strip()
    q_clean = normalize_search_text(q)

    if q_clean in {"sainte marie de la mer", "sainte marie la mer", "sainte marie la mer 66", "sainte marie de la mer 66"}:
        return jsonify([{"nom": "SAINTE-MARIE-LA-MER", "code_postal": "66470", "label": "Sainte-Marie-la-Mer (66470)"}])

    if len(q) < 2:
        return jsonify([])
    try:
        response = session_http.get(
            "https://geo.api.gouv.fr/communes",
            params={"nom": q, "boost": "population", "limit": 8, "fields": "codesPostaux"},
            timeout=10,
        )
        if response.status_code != 200:
            return jsonify([])
        communes = response.json()
        results = []
        for c in communes:
            nom = c.get("nom", "")
            cps = c.get("codesPostaux", [])

            ville_clean = normalize_search_text(nom)

            if ville_clean == "paris":
                for i in range(1, 21):
                    cp = f"750{i:02d}"
                    results.append({
                        "nom": "Paris",
                        "code_postal": cp,
                        "label": f"Paris ({cp})"
                    })

            elif ville_clean == "lyon":
                for i in range(1, 10):
                    cp = f"690{i:02d}"
                    results.append({
                        "nom": "Lyon",
                        "code_postal": cp,
                        "label": f"Lyon ({cp})"
                    })

            elif ville_clean == "marseille":
                for i in range(1, 17):
                    cp = f"130{i:02d}"
                    results.append({
                        "nom": "Marseille",
                        "code_postal": cp,
                        "label": f"Marseille ({cp})"
                    })

            elif len(cps) > 1:
                results.append({
                    "nom": nom,
                    "code_postal": "",
                    "label": nom
                })

            else:
                cp = cps[0] if cps else ""
                label = f"{nom} ({cp})" if cp else nom

                results.append({
                    "nom": nom,
                    "code_postal": cp,
                    "label": label
                })
        return jsonify(results)
    except Exception:
        return jsonify([])


@app.route("/supports")
@login_required
def supports_by_type():
    requested_types = request.args.getlist("types")
    if not requested_types:
        one_type = request.args.get("type", "all")
        requested_types = [one_type]
    support_keys = get_available_supports(requested_types)
    return jsonify([{"value": key, "label": SUPPORT_LABELS.get(key, key)} for key in support_keys])


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    global LAST_RESULTS
    data = []
    lat, lon = DEFAULT_LAT, DEFAULT_LON
    nb_commerces = 0
    potentiel = 0
    supports = 0
    stats = []
    selected_types = ["all"]
    selected_type = "all"
    selected_support = "all"
    camping_stars = "all"
    search_value = ""
    mode = "ville"
    departement_value = ""
    rayon_value = ""
    show_circle = False
    search_mode = request.args.get("search_mode", "commerce")
    temp_searches = session.get("temp_searches", [])

    if request.args.get("reset_search") == "1":
        session.pop("last_search_criteria", None)
        session["last_results_count"] = 0
        search_value = ""
        departement_value = ""
        rayon_value = ""
        selected_support = "all"
        selected_types = ["all"]
        selected_type = "all"

    def rebuild_cumulative_results(saved_searches):
        if not saved_searches:
            return [], DEFAULT_LAT, DEFAULT_LON
        all_data = []
        for saved_search in saved_searches:
            saved_data, _, _, _ = execute_search_criteria(saved_search)
            all_data.append(saved_data)
        merged_data = merge_results_lists(all_data)
        center_lat, center_lon = compute_center_from_data(merged_data)
        if center_lat is None or center_lon is None:
            center_lat, center_lon = DEFAULT_LAT, DEFAULT_LON
        return merged_data, center_lat, center_lon

    if request.method == "POST":
        action = request.form.get("action", "search")
        search_mode = request.form.get("search_mode", "commerce")
        selected_support = request.form.get("support", "all")

        if search_mode == "support":
            selected_types = get_types_for_support(selected_support)
        else:
            selected_types = get_selected_types_from_form(request.form)
        selected_type = selected_types[0] if len(selected_types) == 1 and selected_types[0] != "all" else "all"
        session["selected_support"] = selected_support
        camping_stars = request.form.get("camping_stars", "all")
        search_value = (request.form.get("ville") or "").strip()
        mode = request.form.get("mode", "ville")
        departement_value = (request.form.get("departement") or "").strip()
        rayon_value = (request.form.get("rayon") or "").strip()
        current_criteria = {
            "search_mode": search_mode,
            "selected_types": selected_types,
            "selected_support": selected_support,
            "camping_stars": camping_stars,
            "search_value": search_value,
            "mode": mode,
            "departement_value": departement_value,
            "rayon_value": rayon_value,
            "label": build_search_label({
                "search_value": search_value,
                "mode": mode,
                "departement_value": departement_value,
                "rayon_value": rayon_value,
            }),
        }
        session["last_search_criteria"] = current_criteria
        session.modified = True
        if action == "add_search":
            temp_searches = session.get("temp_searches", [])
            temp_searches.append(current_criteria)
            session["temp_searches"] = temp_searches
            session.modified = True
            data, lat, lon = rebuild_cumulative_results(temp_searches)
            show_circle = False
        else:
            data, lat, lon, show_circle = execute_search_criteria(current_criteria)
            temp_searches = session.get("temp_searches", [])
            
            if session.get("user_id"):
                conn_hidden = sqlite3.connect(AUTH_DB_FILE)
                cur_hidden = conn_hidden.cursor()
                cur_hidden.execute(
                    "DELETE FROM user_hidden_commerces WHERE user_id = ?",
                    (session["user_id"],)
                )
                conn_hidden.commit()
                conn_hidden.close()
    else:
        if temp_searches:
            data, lat, lon = rebuild_cumulative_results(temp_searches)
            show_circle = False
        else:
            last_search_criteria = session.get("last_search_criteria")
            if last_search_criteria:
                selected_types = last_search_criteria.get("selected_types", ["all"])
                selected_type = selected_types[0] if len(selected_types) == 1 and selected_types[0] != "all" else "all"
                selected_support = last_search_criteria.get("selected_support", "all")
                camping_stars = last_search_criteria.get("camping_stars", "all")
                search_value = last_search_criteria.get("search_value", "")
                mode = last_search_criteria.get("mode", "ville")
                departement_value = last_search_criteria.get("departement_value", "")
                rayon_value = last_search_criteria.get("rayon_value", "")
                data, lat, lon, show_circle = execute_search_criteria(last_search_criteria)


    hidden_ids = []

    if session.get("user_id"):
        conn_hidden = sqlite3.connect(AUTH_DB_FILE)
        cur_hidden = conn_hidden.cursor()
        cur_hidden.execute(
            "SELECT commerce_id FROM user_hidden_commerces WHERE user_id = ?",
        (session["user_id"],)
        )
        hidden_ids = [str(row[0]) for row in cur_hidden.fetchall()]
        conn_hidden.close()

    if camping_stars == "3_5":
        data = [
            item for item in data
            if item.get("type") == "camping" and str(item.get("etoiles")) in ["3", "4", "5"]
        ]

    for item in data:
        item["is_hidden"] = str(item.get("id")) in hidden_ids

    visible_data = [
        item for item in data
        if not item.get("is_hidden")
    ]

    print("Nombre data :", len(data))
    print("Nombre visible_data :", len(visible_data))

    LAST_RESULTS = visible_data
    session["last_results_count"] = len(visible_data)
    nb_commerces = len(visible_data)

    if request.method == "POST":
        conn_auth = get_auth_connection()
        conn_auth.execute("""
            INSERT INTO activity_logs (user_id, username, role, action, details)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session.get("user_id"),
            session.get("username"),
            session.get("role"),
            "Recherche",
            f"{nb_commerces} résultat(s)"
        ))
        conn_auth.commit()
        conn_auth.close()
    
    potentiel, totals_by_label = compute_potentiel_and_supports(visible_data)
    if selected_support == "all":
        supports = sum(totals_by_label.values())
        stats = sorted(totals_by_label.items(), key=lambda x: x[0])
        
    else:
        selected_label = SUPPORT_LABELS.get(selected_support)
        supports = totals_by_label.get(selected_label, 0)
        stats = [(selected_label, supports)] if selected_label else []

        if selected_support == "affiche":
            potentiel = supports
    
    available_supports = get_available_supports(selected_types)
    temp_searches = session.get("temp_searches", [])

    return render_template(
        "index.html", data=data, lat=lat, lon=lon, nb=nb_commerces,
        potentiel=potentiel, supports=supports, stats=stats, selected_type=selected_type,
        selected_types=selected_types, selected_support=selected_support, search_value=search_value,
        available_supports=available_supports, support_labels=SUPPORT_LABELS, type_labels=TYPE_LABELS,
        mode=mode, search_mode=search_mode,
        departement_value=departement_value, rayon_value=rayon_value, show_circle=show_circle,
        departements=DEPARTEMENTS, current_user=session.get("username", ""), temp_searches=temp_searches,
    )


@app.route("/hide_result/<int:commerce_id>")
@login_required
def hide_result(commerce_id):
    if session.get("user_id"):
        conn_hidden = sqlite3.connect(AUTH_DB_FILE)
        cur_hidden = conn_hidden.cursor()
        cur_hidden.execute(
            "INSERT OR IGNORE INTO user_hidden_commerces (user_id, commerce_id) VALUES (?, ?)",
            (session["user_id"], commerce_id)
        )
        conn_hidden.commit()
        conn_hidden.close()

    return redirect(url_for("index") + f"#commerce-{commerce_id}")


@app.route("/unhide_result/<int:commerce_id>")
@login_required
def unhide_result(commerce_id):
    if session.get("user_id"):
        conn_hidden = sqlite3.connect(AUTH_DB_FILE)
        cur_hidden = conn_hidden.cursor()
        cur_hidden.execute(
            "DELETE FROM user_hidden_commerces WHERE user_id = ? AND commerce_id = ?",
            (session["user_id"], commerce_id)
        )
        conn_hidden.commit()
        conn_hidden.close()

    return redirect(request.referrer or url_for("index"))

@app.route("/create_campaign", methods=["GET", "POST"])
@login_required
def create_campaign():
    error = ""
    success = ""
    campaign_link = None
    current_user = session.get("username", "")

    if request.method == "POST":
        campaign_name = (request.form.get("campaign_name") or "").strip()
        campaign_notes = (request.form.get("campaign_notes") or "").strip()

        if not campaign_name:
            error = "Le nom de la campagne est obligatoire."

        else:
            temp_searches = session.get("temp_searches", [])
            campaign_results = []
            search_zone_labels = []

            if temp_searches:
                all_data = []

                for saved_search in temp_searches:
                    saved_data, _, _, _ = execute_search_criteria(saved_search)
                    all_data.append(saved_data)

                    label = (saved_search.get("label") or "").strip()
                    if label:
                        search_zone_labels.append(label)

                campaign_results = merge_results_lists(all_data)

            else:
                campaign_results = LAST_RESULTS
                search_zone_labels = []

            if session.get("user_id"):
                conn_hidden = sqlite3.connect(AUTH_DB_FILE)
                cur_hidden = conn_hidden.cursor()
                cur_hidden.execute(
                    "SELECT commerce_id FROM user_hidden_commerces WHERE user_id = ?",
                    (session["user_id"],)
                )
                hidden_ids = {str(row[0]) for row in cur_hidden.fetchall()}
                conn_hidden.close()

                campaign_results = [
                    item for item in campaign_results
                    if str(item.get("id")) not in hidden_ids
                ]

            conn = get_campaign_connection()
            cur = conn.cursor()
            token = uuid.uuid4().hex

            selected_support = session.get("selected_support", "")

            cur.execute("""
                INSERT INTO campaigns (
                    name, notes, created_by, created_at, token, search_zones, support
                )
                VALUES (?, ?, ?, datetime('now'), ?, ?, ?)
            """, (
                campaign_name,
                campaign_notes,
                current_user,
                token,
                json.dumps(search_zone_labels, ensure_ascii=False),
                selected_support
            ))

            campaign_id = cur.lastrowid

            conn_auth = get_auth_connection()
            conn_auth.execute("""
                INSERT INTO activity_logs (user_id, username, role, action, details)
                VALUES (?, ?, ?, ?, ?)
            """, (session.get("user_id"), session.get("username"), session.get("role"), "Création campagne", campaign_name))
            conn_auth.commit()
            conn_auth.close()

            quantite_par_commerce = {
                "sac_pain": 1000,
                "set_table": 1000,
                "sous_bock": 250,
                "flyer": 50,
                "affiche": 1,
                "sac_pharmacie": 1000,
                "sac_galette": 1000,
            }.get(selected_support, 0)
            
            for item in campaign_results:
                cur.execute("""
                    INSERT INTO campaign_items (
                        campaign_id, name, type, ville, code_postal,
                        adresse, telephone, lat, lon, quantite, potentiel_support
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    campaign_id,
                    item.get("name"),
                    item.get("type"),
                    item.get("ville"),
                    item.get("code_postal"),
                    item.get("adresse"),
                    item.get("telephone"),
                    item.get("lat"),
                    item.get("lon"),
                    0,
                    compute_item_potentiel_for_support(item, selected_support)
                ))

            conn.commit()
            conn.close()

            campaign_link = url_for("campaign_resume", token=token, _external=True)
            success = "Campagne enregistrée avec succès."

            return redirect(url_for("campaign_resume", token=token, created="1"))

    return render_template(
        "create_campaign.html",
        current_user=current_user,
        error=error,
        success=success,
        campaign_name="",
        campaign_notes="",
        campaign_link=campaign_link
    )


@app.route("/export")
@login_required
def export_csv():
    global LAST_RESULTS
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Nom", "Type", "Adresse", "Ville", "Code postal", "Téléphone", "Distance (km)"])
    for item in LAST_RESULTS:
        writer.writerow([
            item["name"], item["type"], item.get("adresse", ""), item.get("ville", ""),
            item.get("code_postal", ""), item.get("telephone", ""),
            str(item.get("distance_km", "")).replace(".", ",") if item.get("distance_km") not in (None, "") else "",
        ])
    csv_content = "\ufeff" + output.getvalue()
    conn_auth = get_auth_connection()
    conn_auth.execute("""
        INSERT INTO activity_logs (user_id, username, role, action, details)
        VALUES (?, ?, ?, ?, ?)
    """, (session.get("user_id"), session.get("username"), session.get("role"), "Export CSV", "Export commerces.csv"))
    conn_auth.commit()
    conn_auth.close()
    return Response(csv_content, mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=commerces.csv"})


@app.route("/campaign/<token>")
def view_campaign(token):
    conn = get_campaign_connection()
    cur = conn.cursor()
    campaign = cur.execute("SELECT * FROM campaigns WHERE token = ?", (token,)).fetchone()
    if not campaign:
        conn.close()
        return "Campagne introuvable", 404
    filter_value = request.args.get("filter", "all")
    if filter_value == "all":
        items = cur.execute("SELECT * FROM campaign_items WHERE campaign_id = ? ORDER BY name", (campaign["id"],)).fetchall()
    else:
        try:
            selected_priority = int(filter_value)
        except ValueError:
            selected_priority = 0
        items = cur.execute("SELECT * FROM campaign_items WHERE campaign_id = ? AND priority = ? ORDER BY name", (campaign["id"], selected_priority)).fetchall()
        last_update_row = cur.execute("SELECT MAX(updated_at) AS last_update FROM campaign_items WHERE campaign_id = ?", (campaign["id"],)).fetchone()
        all_items = cur.execute("SELECT * FROM campaign_items WHERE campaign_id = ?", (campaign["id"],)).fetchall()
        campaign_stats = {
            "total": len(all_items),
            "acceptes": sum(1 for item in all_items if item["accepte"] == "oui"),
            "refuses": sum(1 for item in all_items if item["accepte"] == "non"),
            "jamais": sum(1 for item in all_items if item["accepte"] == "jamais"),
            "non_renseignes": sum(1 for item in all_items if not item["accepte"]),
        }
    conn.close()
    return render_template("view_campaign.html", campaign=campaign, items=items, last_update=last_update_row["last_update"], campaign_stats=campaign_stats)
    
@app.route("/campaign_resume/<token>")
@login_required
def campaign_resume(token):
    conn = get_campaign_connection()
    cur = conn.cursor()

    campaign = cur.execute(
        "SELECT * FROM campaigns WHERE token = ?",
        (token,)
    ).fetchone()

    if not campaign:
        conn.close()
        return "Campagne introuvable", 404

    items = cur.execute("""
        SELECT *
        FROM campaign_items
        WHERE campaign_id = ?
        ORDER BY name
    """, (campaign["id"],)).fetchall()

    conn.close()

    total_commerces = len(items)
    total_quantite = sum((item["quantite"] or 0) for item in items)

    items_as_dict = [dict(item) for item in items]
    _, totals_by_label = compute_potentiel_and_supports(items_as_dict)

    support_label = SUPPORT_LABELS.get(campaign["support"], campaign["support"] or "Tous les supports")

    if campaign["support"] == "all":
        potentiel_quantite = sum(totals_by_label.values())
    else:
        potentiel_quantite = totals_by_label.get(support_label, 0)

    total_acceptes = sum(1 for item in items if (item["accepte"] or "") == "oui")
    
    quantite_acceptes = sum(
        (item["quantite"] or 0)
        for item in items
        if (item["accepte"] or "") == "oui"
    )

    return render_template(
        "campaign_resume.html",
        campaign=campaign,
        items=items,
        total_commerces=total_commerces,
        total_quantite=total_quantite,
        potentiel_quantite=potentiel_quantite,
        total_acceptes=total_acceptes,
        quantite_acceptes=quantite_acceptes,
        support_label=support_label
    )

    
@app.route("/campaign/<token>/set_priority", methods=["POST"])
def set_campaign_priority(token):
    item_id = request.form.get("item_id")
    priority = request.form.get("priority")
    try:
        item_id = int(item_id)
        priority = int(priority)
    except (TypeError, ValueError):
        return "Paramètres invalides", 400
    if priority not in [0, 1, 2, 3]:
        return "Priorité invalide", 400
    conn = get_campaign_connection()
    cur = conn.cursor()
    campaign = cur.execute("SELECT * FROM campaigns WHERE token = ?", (token,)).fetchone()
    if not campaign:
        conn.close()
        return "Campagne introuvable", 404
    cur.execute("""
        UPDATE campaign_items
        SET priority = ?, updated_at = datetime('now', 'localtime')
        WHERE id = ? AND campaign_id = ?
    """, (priority, item_id, campaign["id"]))
    conn.commit()
    conn.close()
    return redirect(url_for("campaign_resume", token=token) + f"#commerce-{item_id}")

@app.route("/campaign/<token>/update_item", methods=["POST"])
def update_campaign_item(token):

    item_id = request.form.get("item_id")
    accepte = (request.form.get("accepte") or "").strip()
    commentaire = (request.form.get("commentaire") or "").strip()
    quantite = request.form.get("quantite") or "0"
    
    try:
        item_id = int(item_id)
        quantite = int(quantite)
    except ValueError:
        return "Paramètres invalides", 400

    conn = get_campaign_connection()
    cur = conn.cursor()

    campaign = cur.execute("""
        SELECT * FROM campaigns WHERE token = ?
    """, (token,)).fetchone()

    if not campaign:
        conn.close()
        return "Campagne introuvable", 404

    if session.get("role") == "admin":
        cur.execute("""
            UPDATE campaign_items
            SET accepte = ?,
                commentaire = ?,
                quantite = ?,
                updated_at = datetime('now', 'localtime')
            WHERE id = ? AND campaign_id = ?
        """, (
            accepte,
            commentaire,
            quantite,
            item_id,
            campaign["id"]
        ))
    else:
        cur.execute("""
            UPDATE campaign_items
            SET commentaire = ?,
                updated_at = datetime('now', 'localtime')
            WHERE id = ? AND campaign_id = ?
        """, (
            commentaire,
            item_id,
            campaign["id"]
        ))

    item_row = cur.execute("""
        SELECT name, ville, code_postal, type
        FROM campaign_items
        WHERE id = ? AND campaign_id = ?
    """, (item_id, campaign["id"])).fetchone()

    conn.commit()
    conn.close()

    if item_row and session.get("role") == "admin":
        main_conn = get_db_connection()
        main_cur = main_conn.cursor()

        main_cur.execute("""
            UPDATE commerces
            SET accepte_support = ?,
                commentaire_support = ?,
                quantite_support = ?
            WHERE nom = ?
              AND ville = ?
              AND code_postal = ?
              AND type = ?
        """, (
            accepte,
            commentaire,
            quantite,
            item_row["name"],
            item_row["ville"],
            item_row["code_postal"],
            item_row["type"]
        ))

        main_conn.commit()
        main_conn.close()

    return redirect(url_for("campaign_resume", token=token) + f"#commerce-{item_id}")


init_campaign_items_table()
init_campaigns_extra_columns()
init_commerces_extra_columns()


@app.route("/campaign/<token>/export")
def export_campaign(token):
    filter_value = request.args.get("filter", "all")
    conn = get_campaign_connection()
    cur = conn.cursor()
    campaign = cur.execute("SELECT * FROM campaigns WHERE token = ?", (token,)).fetchone()
    if not campaign:
        conn.close()
        return "Campagne introuvable", 404
    if filter_value == "all":
        items = cur.execute("SELECT * FROM campaign_items WHERE campaign_id = ? ORDER BY name", (campaign["id"],)).fetchall()
    elif filter_value == "all_sorted":
        items = cur.execute("SELECT * FROM campaign_items WHERE campaign_id = ? ORDER BY priority DESC, name", (campaign["id"],)).fetchall()
    else:
        try:
            selected_priority = int(filter_value)
        except ValueError:
            selected_priority = 0
        items = cur.execute("SELECT * FROM campaign_items WHERE campaign_id = ? AND priority = ? ORDER BY name", (campaign["id"], selected_priority)).fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["Nom", "Type", "Adresse", "Ville", "Code postal", "Téléphone", "Priorité"])
    for item in items:
        writer.writerow([item["name"] or "", item["type"] or "", item["adresse"] or "", item["ville"] or "", item["code_postal"] or "", item["telephone"] or "", item["priority"] if item["priority"] is not None else 0])
    csv_content = "\ufeff" + output.getvalue()
    conn_auth = get_auth_connection()
    conn_auth.execute("""
        INSERT INTO activity_logs (user_id, username, role, action, details)
        VALUES (?, ?, ?, ?, ?)
    """, (
        session.get("user_id"),
        session.get("username"),
        session.get("role"),
        "Export campagne",
        campaign["name"]
    ))
    conn_auth.commit()
    conn_auth.close()
    return Response(csv_content, mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": f"attachment; filename=campagne_{campaign['name']}.csv"})

@app.route("/massive_campaign/<int:campaign_id>")
@login_required
def massive_campaign_detail(campaign_id):
    conn = get_campaign_connection()
    cur = conn.cursor()

    campaign = cur.execute("""
        SELECT *
        FROM campaigns
        WHERE id = ? AND notes = 'Campagne massive'
    """, (campaign_id,)).fetchone()

    if not campaign:
        conn.close()
        return "Campagne massive introuvable", 404

    items = cur.execute("""
        SELECT *
        FROM campaign_items
        WHERE campaign_id = ?
        ORDER BY name
    """, (campaign_id,)).fetchall()

    potential_data = [dict(row) for row in items]

    _, totals_by_label = compute_potentiel_and_supports(potential_data)
    support_label = SUPPORT_LABELS.get(campaign["support"], "")

    if campaign["support"] == "all":
        supports_potentiels = sum(totals_by_label.values())
    else:
        supports_potentiels = totals_by_label.get(support_label, 0)

    quantite_par_commerce = {
        "sac_pain": 1000,
        "set_table": 1000,
        "sous_bock": 250,
        "flyer": 50,
        "affiche": 1,
        "sac_pharmacie": 1000,
        "sac_galette": 1000,
    }

    qte_unitaire = quantite_par_commerce.get(campaign["support"], 1)

    commerces_potentiels = int(supports_potentiels / qte_unitaire) if qte_unitaire else 0

    support_display = support_label or "Supports concernés"

    conn.close()

    total_commerces = len(items)
    total_quantite = sum((item["quantite"] or 0) for item in items)

    return render_template(
        "massive_campaign.html",
        campaign=campaign,
        items=items,
        total_commerces=total_commerces,
        total_quantite=total_quantite,
        commerces_potentiels=commerces_potentiels,
        supports_potentiels=supports_potentiels,
        support_display=support_display,
        is_public=False
    )

@app.route("/massive_campaign_client/<token>")
def massive_campaign_client(token):
    conn = get_campaign_connection()
    cur = conn.cursor()

    campaign = cur.execute("""
        SELECT *
        FROM campaigns
        WHERE token = ? AND notes = 'Campagne massive'
    """, (token,)).fetchone()

    if not campaign:
        conn.close()
        return "Campagne massive introuvable", 404

    items = cur.execute("""
        SELECT *
        FROM campaign_items
        WHERE campaign_id = ?
        ORDER BY name
    """, (campaign["id"],)).fetchall()

    potential_data = [dict(row) for row in items]

    _, totals_by_label = compute_potentiel_and_supports(potential_data)

    support_label = SUPPORT_LABELS.get(campaign["support"], "")

    if campaign["support"] == "all":
        supports_potentiels = sum(totals_by_label.values())
    else:
        supports_potentiels = totals_by_label.get(support_label, 0)

    quantite_par_commerce = {
        "sac_pain": 1000,
        "set_table": 1000,
        "sous_bock": 250,
        "flyer": 50,
        "affiche": 1,
        "sac_pharmacie": 1000,
        "sac_galette": 1000,
    }

    qte_unitaire = quantite_par_commerce.get(campaign["support"], 1)
    commerces_potentiels = int(supports_potentiels / qte_unitaire) if qte_unitaire else 0

    support_display = support_label or "Supports concernés"

    conn.close()

    total_commerces = len(items)
    total_quantite = sum((item["quantite"] or 0) for item in items)

    return render_template(
        "massive_campaign.html",
        campaign=campaign,
        items=items,
        total_commerces=total_commerces,
        total_quantite=total_quantite,
        commerces_potentiels=commerces_potentiels,
        supports_potentiels=supports_potentiels,
        support_display=support_display,
        is_public=True
    )

@app.route("/massive_export/<int:campaign_id>/download")
@login_required
def massive_export_download(campaign_id):
    conn = get_campaign_connection()
    cur = conn.cursor()

    items = cur.execute("""
        SELECT name, type, adresse, ville, code_postal, telephone
        FROM campaign_items
        WHERE campaign_id = ?
        ORDER BY name
    """, (campaign_id,)).fetchall()

    campaign = cur.execute("""
        SELECT name
        FROM campaigns
        WHERE id = ?
    """, (campaign_id,)).fetchone()

    conn.close()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

    writer.writerow([
        "Nom", "Type", "Adresse", "Ville", "Code postal", "Téléphone"
    ])

    for item in items:
        writer.writerow([
            item["name"] or "",
            item["type"] or "",
            item["adresse"] or "",
            item["ville"] or "",
            item["code_postal"] or "",
            item["telephone"] or ""
        ])

    csv_content = "\ufeff" + output.getvalue()

    safe_filename = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        campaign["name"] or "campagne_massive"
    )

    return Response(
        csv_content,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=massive_{safe_filename}.csv"
        }
    )

@app.route("/log_massive_export", methods=["POST"])
@login_required
def log_massive_export():
    data = request.get_json()

    nb_commerces = data.get("nb_commerces", 0)
    support = data.get("support", "")

    quantite_map = {
        "sac_pain": 1000,
        "set_table": 1000,
        "sous_bock": 250,
        "flyer": 50,
        "affiche": 1,
        "sac_pharmacie": 1000,
        "sac_galette": 1000,
    }

    quantite_totale = nb_commerces * quantite_map.get(support, 0)

    filename = data.get(
        "filename",
        f"Campagne massive du {datetime.now().strftime('%d/%m/%Y')}"
    )

    conn = sqlite3.connect(CAMPAIGN_DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO massive_exports (
            username, filename, nb_commerces, created_at, support, quantite_totale
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        session.get("username"),
        filename,
        nb_commerces,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        support,
        quantite_totale
    ))

    token = uuid.uuid4().hex

    cur.execute("""
        INSERT INTO campaigns (
            name, notes, created_by, created_at, token, search_zones, support
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        filename,
        "Campagne massive",
        session.get("username"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        token,
        "[]",
        support
    ))

    campaign_id = cur.lastrowid

    conn_auth = get_auth_connection()
    conn_auth.execute("""
        INSERT INTO activity_logs (user_id, username, role, action, details)
        VALUES (?, ?, ?, ?, ?)
    """, (session.get("user_id"), session.get("username"), session.get("role"), "Création campagne massive", filename))
    conn_auth.commit()
    conn_auth.close()

    massive_results = LAST_RESULTS

    if session.get("user_id"):
        conn_hidden = sqlite3.connect(AUTH_DB_FILE)
        cur_hidden = conn_hidden.cursor()
        cur_hidden.execute(
            "SELECT commerce_id FROM user_hidden_commerces WHERE user_id = ?",
            (session["user_id"],)
        )
        hidden_ids = {str(row[0]) for row in cur_hidden.fetchall()}
        conn_hidden.close()

        massive_results = [
            item for item in massive_results
            if str(item.get("id")) not in hidden_ids
        ]

    for item in massive_results:
        cur.execute("""
            INSERT INTO campaign_items (
                campaign_id, name, type, ville, code_postal,
                adresse, telephone, lat, lon, quantite, potentiel_support
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            campaign_id,
            item.get("name"),
            item.get("type"),
            item.get("ville"),
            item.get("code_postal"),
            item.get("adresse"),
            item.get("telephone"),
            item.get("lat"),
            item.get("lon"),
            compute_item_potentiel_for_support(item, support) if support == "all" else quantite_map.get(support, 0),
            compute_item_potentiel_for_support(item, support)
        ))
        
    conn.commit()
    conn.close()

    return jsonify({"success": True})

@app.route("/campaigns")
@login_required
def list_campaigns():
    conn = get_campaign_connection()
    cur = conn.cursor()

    if session.get("role") == "admin":
        campaigns_rows = cur.execute("""
            SELECT
                campaigns.*,
                MAX(campaign_items.updated_at) AS last_update,
                SUM(CASE WHEN campaign_items.priority = 1 THEN 1 ELSE 0 END) AS count_p1,
                SUM(CASE WHEN campaign_items.priority = 2 THEN 1 ELSE 0 END) AS count_p2,
                SUM(CASE WHEN campaign_items.priority = 3 THEN 1 ELSE 0 END) AS count_p3
            FROM campaigns
            LEFT JOIN campaign_items ON campaign_items.campaign_id = campaigns.id
            GROUP BY campaigns.id
            ORDER BY campaigns.created_at DESC
        """).fetchall()
    else:
        campaigns_rows = cur.execute("""
            SELECT
                campaigns.*,
                MAX(campaign_items.updated_at) AS last_update,
                SUM(CASE WHEN campaign_items.priority = 1 THEN 1 ELSE 0 END) AS count_p1,
                SUM(CASE WHEN campaign_items.priority = 2 THEN 1 ELSE 0 END) AS count_p2,
                SUM(CASE WHEN campaign_items.priority = 3 THEN 1 ELSE 0 END) AS count_p3
            FROM campaigns
            LEFT JOIN campaign_items ON campaign_items.campaign_id = campaigns.id
            WHERE campaigns.created_by = ?
            GROUP BY campaigns.id
            ORDER BY campaigns.created_at DESC
        """, (session.get("username"),)).fetchall()

    conn.close()

    campaigns = []
    for row in campaigns_rows:
        campaign_dict = dict(row)
        raw_zones = campaign_dict.get("search_zones")
        zones = []

        if raw_zones:
            try:
                decoded = json.loads(raw_zones)
                if isinstance(decoded, list):
                    zones = [str(item).strip() for item in decoded if str(item).strip()]
            except Exception:
                zones = []

        campaign_dict["search_zones_list"] = zones
        campaigns.append(campaign_dict)

    return render_template("campaigns.html", campaigns=campaigns)


@app.route("/campaign/<token>/delete", methods=["POST"])
@login_required
def delete_campaign(token):
    conn = get_campaign_connection()
    cur = conn.cursor()

    campaign = cur.execute("SELECT * FROM campaigns WHERE token = ?", (token,)).fetchone()
    if not campaign:
        conn.close()
        return "Campagne introuvable", 404

    can_delete = False

    if session.get("role") == "admin":
        can_delete = True

    elif session.get("role") == "user":
        can_delete = campaign["created_by"] == session.get("username")

    elif session.get("role") == "manager":
        if campaign["created_by"] == session.get("username"):
            can_delete = True
        else:
            conn_auth = get_auth_connection()
            cur_auth = conn_auth.cursor()
            commercial = cur_auth.execute(
                "SELECT id FROM users WHERE username = ? AND manager_id = ?",
                (campaign["created_by"], session.get("user_id"))
            ).fetchone()
            conn_auth.close()
            can_delete = commercial is not None

    if not can_delete:
        conn.close()
        return "Accès interdit", 403

    conn_auth = get_auth_connection()
    conn_auth.execute("""
        INSERT INTO activity_logs (user_id, username, role, action, details)
        VALUES (?, ?, ?, ?, ?)
    """, (
        session.get("user_id"),
        session.get("username"),
        session.get("role"),
        "Suppression campagne",
        campaign["name"]
    ))
    conn_auth.commit()
    conn_auth.close()

    cur.execute("DELETE FROM campaign_items WHERE campaign_id = ?", (campaign["id"],))
    cur.execute("DELETE FROM campaigns WHERE id = ?", (campaign["id"],))
    conn.commit()
    conn.close()

    if session.get("role") == "user":
        return redirect(url_for("mon_dashboard"))
    else:
        return redirect(url_for("dashboard_equipe"))


@app.route("/remove_temp_search/<int:index>")
@login_required
def remove_temp_search(index):
    temp_searches = session.get("temp_searches", [])
    if 0 <= index < len(temp_searches):
        temp_searches.pop(index)
        session["temp_searches"] = temp_searches
        session.modified = True
    return redirect(url_for("index"))


@app.route("/clear_temp_searches")
@login_required
def clear_temp_searches():
    session["temp_searches"] = []
    session.modified = True
    return redirect(url_for("index"))


@app.route("/add_commerce", methods=["POST"])
@login_required
def add_commerce():
    if session.get("role") != "admin":
        return jsonify({"status": "error", "message": "Accès refusé"})

    data = request.get_json() or {}
    try:
        nom = (data.get("nom") or "").strip()
        type_c = (data.get("type") or "").strip()
        ville = (data.get("ville") or "").strip()
        adresse = (data.get("adresse") or "").strip()
        telephone = (data.get("telephone") or "").strip()
        code_postal = (data.get("code_postal") or "").strip()
        lat = data.get("latitude")
        lon = data.get("longitude")

        if not nom or not type_c:
            return jsonify({"status": "error", "message": "Nom ou type manquant"})

        lat_value = None
        lon_value = None
        if lat not in (None, ""):
            try:
                lat_value = float(str(lat).replace(",", "."))
            except ValueError:
                return jsonify({"status": "error", "message": "Latitude invalide"})
        if lon not in (None, ""):
            try:
                lon_value = float(str(lon).replace(",", "."))
            except ValueError:
                return jsonify({"status": "error", "message": "Longitude invalide"})

        ville, code_postal, departement = normalize_added_city_and_postal(ville, code_postal, lat_value, lon_value)
        if not code_postal:
            return jsonify({"status": "error", "message": "Code postal manquant : choisis une ville dans les suggestions ou saisis le code postal."})
        if not ville:
            ville = ""
        if not departement:
            departement = code_postal[:2]

        conn = get_db_connection()
        cur = conn.cursor()
        existing = cur.execute("""
            SELECT rowid AS rid, exclude_from_results
            FROM commerces
            WHERE LOWER(TRIM(nom)) = LOWER(TRIM(?))
              AND COALESCE(code_postal, '') = ?
              AND type = ?
        """, (nom, code_postal, type_c)).fetchone()

        if existing:
            if int(existing["exclude_from_results"] or 0) == 1:
                cur.execute("""
                    UPDATE commerces
                    SET ville = ?, code_postal = ?, departement = ?, adresse = ?, telephone = ?,
                        latitude = COALESCE(?, latitude), longitude = COALESCE(?, longitude),
                        is_active = 1, exclude_from_results = 0
                    WHERE rowid = ?
                """, (ville, code_postal, departement, adresse, telephone, lat_value, lon_value, existing["rid"]))
                conn.commit()
                conn.close()
                return jsonify({"status": "ok", "message": "Commerce réactivé"})
            conn.close()
            return jsonify({"status": "error", "message": "Ce commerce existe déjà"})

        cur.execute("""
            INSERT INTO commerces
            (nom, type, ville, code_postal, departement, adresse, telephone, latitude, longitude, is_active, exclude_from_results)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
        """, (nom, type_c, ville, code_postal, departement, adresse, telephone, lat_value, lon_value))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/delete_commerce", methods=["POST"])
@login_required
def delete_commerce():
    if session.get("role") != "admin":
        return jsonify({"status": "error", "message": "Accès refusé"})
    data = request.get_json() or {}
    commerce_id = data.get("id")
    if not commerce_id:
        return jsonify({"status": "error", "message": "ID manquant"})
    try:
        commerce_id = int(commerce_id)
    except ValueError:
        return jsonify({"status": "error", "message": "ID invalide"})
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE commerces
            SET exclude_from_results = 1
            WHERE rowid = ?
        """, (commerce_id,))

        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


def extract_google_maps_data(url):
    """
    Lit un lien Google Maps et récupère le nom + les coordonnées du vrai lieu.
    Important : on privilégie les coordonnées !3d / !4d du lieu, car les coordonnées
    après @ correspondent parfois au centre de la carte et non au commerce.
    """
    try:
        r = requests.get(
            url,
            allow_redirects=True,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        final_url = r.url

        name = ""
        m_name = re.search(r"/place/([^/@?]+)", final_url)
        if m_name:
            raw_name = m_name.group(1)
            name = unquote(raw_name)
            name = unquote(name)
            name = name.replace("+", " ").strip()
            name = name.title()
            name = name.replace(" De ", " de ").replace(" Du ", " du ").replace(" Des ", " des ")
            name = name.replace(" Le ", " le ").replace(" La ", " la ").replace(" Les ", " les ")
            name = name.replace(" D'", " d'").replace(" L'", " l'")
            if name:
                name = name[0].upper() + name[1:]

        lat = None
        lon = None

        # Coordonnées du lieu Google Maps : priorité absolue
        m_place = re.search(r"!3d([-0-9.]+)!4d([-0-9.]+)", final_url)
        if m_place:
            lat = float(m_place.group(1))
            lon = float(m_place.group(2))

        # Fallback : coordonnées dans l'URL après @
        if lat is None or lon is None:
            m_at = re.search(r"@([-0-9.]+),([-0-9.]+)", final_url)
            if m_at:
                lat = float(m_at.group(1))
                lon = float(m_at.group(2))

        # Fallback : q=lat,lon
        if lat is None or lon is None:
            m_q = re.search(r"[?&]q=([-0-9.]+),([-0-9.]+)", final_url)
            if m_q:
                lat = float(m_q.group(1))
                lon = float(m_q.group(2))

        if lat is None or lon is None:
            return None, None, None, "", final_url

        return name, lat, lon, "", final_url

    except Exception:
        return None, None, None, "", None


def coords_too_far_from_commune(ville, code_postal, lat, lon, max_km=35):
    """
    Sécurité pour éviter d'enregistrer un commerce très loin de la ville saisie.
    Si Google donne le centre de la carte au lieu du commerce, on le détecte ici.
    """
    try:
        search_value = (code_postal or ville or "").strip()
        center_lat, center_lon = get_coords_commune(search_value)
        if center_lat is None or center_lon is None:
            return False
        return distance_km(center_lat, center_lon, lat, lon) > max_km
    except Exception:
        return False


@app.route("/add_commerce_from_link", methods=["POST"])
@login_required
def add_commerce_from_link():
    if session.get("role") != "admin":
        return jsonify({"status": "error", "message": "Accès refusé"})

    data = request.get_json() or {}
    lien = (data.get("lien") or "").strip()
    nom_saisi = (data.get("nom") or "").strip()
    type_c = (data.get("type") or "").strip()
    ville = (data.get("ville") or "").strip()
    code_postal = (data.get("code_postal") or "").strip()
    adresse = (data.get("adresse") or "").strip()
    telephone = (data.get("telephone") or "").strip()

    if not lien or not type_c or not ville:
        return jsonify({"status": "error", "message": "Lien, type ou ville manquant"})

    nom_google, lat, lon, _, final_url = extract_google_maps_data(lien)
    if lat is None or lon is None:
        return jsonify({"status": "error", "message": "Impossible de lire le lien Google Maps"})

    nom = nom_saisi or nom_google or "Commerce ajouté manuellement"
    ville, code_postal, departement = normalize_added_city_and_postal(ville, code_postal, lat, lon)
    if not code_postal:
        return jsonify({"status": "error", "message": "Code postal manquant : choisis une ville dans les suggestions ou saisis le code postal."})
    if not departement:
        departement = code_postal[:2]

    # Sécurité : si les coordonnées Google sont trop éloignées de la ville saisie,
    # on replace le commerce au centre de la commune au lieu de l'envoyer loin sur la carte.
    if coords_too_far_from_commune(ville, code_postal, lat, lon):
        safe_lat, safe_lon = get_coords_commune(code_postal or ville)
        if safe_lat is not None and safe_lon is not None:
            lat, lon = safe_lat, safe_lon

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        existing = cur.execute("""
            SELECT rowid AS rid, exclude_from_results
            FROM commerces
            WHERE LOWER(TRIM(nom)) = LOWER(TRIM(?))
              AND COALESCE(code_postal, '') = ?
              AND type = ?
        """, (nom, code_postal, type_c)).fetchone()

        if existing:
            if int(existing["exclude_from_results"] or 0) == 1:
                cur.execute("""
                    UPDATE commerces
                    SET ville = ?, code_postal = ?, departement = ?, adresse = ?, telephone = ?,
                        latitude = ?, longitude = ?, is_active = 1, exclude_from_results = 0
                    WHERE rowid = ?
                """, (ville, code_postal, departement, adresse, telephone, lat, lon, existing["rid"]))
                conn.commit()
                conn.close()
                return jsonify({"status": "ok", "message": "Commerce réactivé", "nom": nom, "lat": lat, "lon": lon})
            conn.close()
            return jsonify({"status": "error", "message": "Ce commerce existe déjà"})

        cur.execute("""
            INSERT INTO commerces
            (nom, type, ville, code_postal, departement, adresse, telephone, latitude, longitude, is_active, exclude_from_results)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
        """, (nom, type_c, ville, code_postal, departement, adresse, telephone, lat, lon))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "nom": nom, "lat": lat, "lon": lon, "adresse": adresse, "telephone": telephone})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/preview_google_maps_link", methods=["POST"])
@login_required
def preview_google_maps_link():
    if session.get("role") != "admin":
        return jsonify({"status": "error", "message": "Accès refusé"})
    data = request.get_json() or {}
    lien = (data.get("lien") or "").strip()
    if not lien:
        return jsonify({"status": "error", "message": "Lien manquant"})
    nom, lat, lon, _, final_url = extract_google_maps_data(lien)
    if not nom:
        return jsonify({"status": "error", "message": "Nom introuvable"})
    return jsonify({"status": "ok", "nom": nom})


@app.route("/fix_google_maps_addresses")
@login_required
def fix_google_maps_addresses():
    if session.get("role") != "admin":
        return "Accès refusé"
    conn = get_db_connection()
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT rowid AS id, latitude, longitude
        FROM commerces
        WHERE is_active = 1
          AND COALESCE(exclude_from_results, 0) = 0
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND (adresse IS NULL OR adresse = '')
        ORDER BY rowid DESC
        LIMIT 300
    """).fetchall()
    updated = 0
    for row in rows:
        lat = row["latitude"]
        lon = row["longitude"]
        try:
            reverse_url = f"https://data.geopf.fr/geocodage/reverse?lon={lon}&lat={lat}&index=address&limit=1"
            r = requests.get(reverse_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            geo = r.json()
            features = geo.get("features", [])
            if features:
                props = features[0].get("properties", {})
                adresse = (props.get("label") or "").strip()
                if adresse:
                    cur.execute("UPDATE commerces SET adresse = ? WHERE rowid = ?", (adresse, row["id"]))
                    updated += 1
        except Exception:
            continue
    conn.commit()
    conn.close()
    return f"{updated} adresses mises à jour"


@app.route("/update_commerce_address", methods=["POST"])
@login_required
def update_commerce_address():
    if session.get("role") != "admin":
        return jsonify({"status": "error", "message": "Accès refusé"})
    data = request.get_json() or {}
    commerce_id = data.get("id")
    nouvelle_adresse = (data.get("adresse") or "").strip()
    if not commerce_id:
        return jsonify({"status": "error", "message": "ID manquant"})
    if not nouvelle_adresse:
        return jsonify({"status": "error", "message": "Adresse manquante"})
    try:
        commerce_id = int(commerce_id)
    except ValueError:
        return jsonify({"status": "error", "message": "ID invalide"})
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE commerces SET adresse = ? WHERE rowid = ?", (nouvelle_adresse, commerce_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/edit_commerce/<int:commerce_id>", methods=["GET", "POST"])
@login_required
def edit_commerce(commerce_id):
    if session.get("role") != "admin":
        return "Accès refusé", 403
    conn = get_db_connection()
    cur = conn.cursor()
    commerce = cur.execute("SELECT rowid AS id, nom, adresse, telephone FROM commerces WHERE rowid = ?", (commerce_id,)).fetchone()
    if not commerce:
        conn.close()
        return "Commerce introuvable", 404
    if request.method == "POST":
        nouveau_nom = (request.form.get("nom") or "").strip()
        nouvelle_adresse = (request.form.get("adresse") or "").strip()
        nouveau_telephone = (request.form.get("telephone") or "").strip()
        if not nouveau_nom:
            conn.close()
            return "<h3>Nom manquant</h3><a href='javascript:history.back()'>Retour</a>"
        cur.execute("UPDATE commerces SET nom = ?, adresse = ?, telephone = ? WHERE rowid = ?", (nouveau_nom, nouvelle_adresse, nouveau_telephone, commerce_id))
        conn.commit()
        conn.close()
        return redirect(url_for("index"))

    commerce_nom = html.escape(commerce["nom"] or "")
    commerce_adresse = html.escape(commerce["adresse"] or "")
    commerce_telephone = html.escape(commerce["telephone"] or "")
    back_url = url_for("index")
    conn.close()
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Modifier le commerce</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #eceff3; margin: 0; padding: 30px; }}
            .box {{ max-width: 700px; margin: 0 auto; background: white; padding: 24px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
            h2 {{ margin-top: 0; }}
            label {{ display: block; margin-bottom: 6px; font-weight: bold; }}
            input[type="text"] {{ width: 100%; padding: 12px; font-size: 16px; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; margin-bottom: 16px; }}
            button, a.btn {{ background: #f97316; color: white; border: none; padding: 10px 16px; border-radius: 8px; text-decoration: none; cursor: pointer; font-size: 15px; display: inline-block; }}
            a.btn {{ background: #6b7280; margin-left: 8px; }}
        </style>
    </head>
    <body>
        <div class="box">
            <h2>Modifier le commerce</h2>
            <form method="POST">
                <label>Nom</label>
                <input type="text" name="nom" value="{commerce_nom}" placeholder="Nom du commerce">
                <label>Adresse</label>
                <input type="text" name="adresse" value="{commerce_adresse}" placeholder="Adresse">
                <label>Téléphone</label>
                <input type="text" name="telephone" value="{commerce_telephone}" placeholder="Téléphone">
                <button type="submit">Enregistrer</button>
                <a class="btn" href="{back_url}">Annuler</a>
            </form>
        </div>
    </body>
    </html>
    """
@app.route("/mon_equipe", methods=["GET", "POST"])
@login_required
def mon_equipe():
    if session.get("role") not in ("manager", "admin"):
        return "Accès refusé", 403

    conn = get_auth_connection()
    cur = conn.cursor()

    if request.method == "POST":
        member_id = request.form.get("member_id")
        display_name = (request.form.get("display_name") or "").strip()

        if session.get("role") == "admin":
            cur.execute(
                "UPDATE users SET display_name = ? WHERE id = ? AND role = 'user'",
                (display_name, member_id)
            )
        else:
            cur.execute(
                "UPDATE users SET display_name = ? WHERE id = ? AND manager_id = ? AND role = 'user'",
                (display_name, member_id, session.get("user_id"))
            )

        conn.commit()
        conn.close()
        return redirect(url_for("mon_equipe"))

    if session.get("role") == "admin":
        members = cur.execute("""
            SELECT u.id, u.username, u.display_name, u.manager_id, m.username AS manager_username
            FROM users u
            LEFT JOIN users m ON m.id = u.manager_id
            WHERE u.role = 'user'
            ORDER BY m.username, u.username
        """).fetchall()
    else:
        members = cur.execute("""
            SELECT id, username, display_name, manager_id, NULL AS manager_username
            FROM users
            WHERE manager_id = ?
            ORDER BY username
        """, (session.get("user_id"),)).fetchall()

    conn.close()

    rows = ""
    for member in members:
        manager_name = member["manager_username"] or session.get("username", "")
        display_name = member["display_name"] or ""

        rows += f"""
            <tr>
                <td><span class="manager-badge">👤 {manager_name}</span></td>
                <td>
                    <a class="commercial-link" href="/commercial/{member['id']}">{member['username']}</a>
                </td>
                <td>
                    <form method="POST" class="edit-form" id="form-{member['id']}">
                        <input type="hidden" name="member_id" value="{member['id']}">
                        <input type="text" name="display_name" value="{display_name}">
                    </form>
                </td>
                <td>
                    <button type="submit" form="form-{member['id']}" class="save-btn">💾 Enregistrer</button>
                </td>
            </tr>
        """

    return f"""
    <style>
        body {{
            margin: 0;
            background: #f4f6f8;
            font-family: Arial, sans-serif;
            color: #111827;
        }}

        .top-nav {{
            height: 78px;
            background: white;
            display: flex;
            justify-content: flex-end;
            align-items: center;
            gap: 14px;
            padding: 0 28px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        }}

        .user-pill {{
            font-size: 18px;
            margin-right: 20px;
            color: #111827;
        }}

        .nav-btn {{
            background: #ff5a00;
            color: white;
            text-decoration: none;
            padding: 13px 18px;
            border-radius: 8px;
            font-weight: bold;
            box-shadow: 0 4px 10px rgba(255,90,0,0.22);
        }}

        .page {{
            padding: 24px;
        }}

        .team-card {{
            background: white;
            border-radius: 14px;
            padding: 34px 28px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        }}

        .title-row {{
            display: flex;
            align-items: center;
            gap: 18px;
            margin-bottom: 10px;
        }}

        .team-icon {{
            font-size: 42px;
            color: #5b2aa0;
        }}

        h1 {{
            margin: 0;
            font-size: 32px;
        }}

        .subtitle {{
            margin: 0 0 26px 64px;
            color: #4b5563;
            font-size: 16px;
        }}

        .back-btn {{
            display: inline-block;
            background: #ff7a00;
            color: white;
            text-decoration: none;
            padding: 13px 20px;
            border-radius: 8px;
            font-weight: bold;
            margin-bottom: 28px;
        }}

        .table-wrap {{
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            overflow: hidden;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th {{
            background: #fff4e8;
            padding: 18px;
            font-size: 16px;
            text-align: center;
        }}

        td {{
            padding: 20px 28px;
            border-top: 1px solid #e5e7eb;
            border-right: 1px solid #e5e7eb;
            vertical-align: middle;
            font-size: 16px;
        }}

        td:last-child {{
            border-right: none;
            text-align: center;
        }}

        .manager-badge {{
            color: #111827;
            font-weight: 500;
        }}

        .commercial-link {{
            color: #4c1d95;
            font-weight: 500;
        }}

        .edit-form input {{
            width: 75%;
            padding: 12px 14px;
            border: 1px solid #d1d5db;
            border-radius: 7px;
            font-size: 15px;
        }}

        .save-btn {{
            background: #ff5a00;
            color: white;
            border: none;
            border-radius: 7px;
            padding: 12px 18px;
            font-weight: bold;
            cursor: pointer;
            font-size: 15px;
        }}

        .info-box {{
            margin-top: 26px;
            background: #fff7ed;
            border: 1px solid #fed7aa;
            border-left: 5px solid #ff7a00;
            border-radius: 10px;
            padding: 22px 26px;
            display: flex;
            gap: 18px;
            align-items: flex-start;
        }}

        .info-icon {{
            background: #ff8a00;
            color: white;
            border-radius: 50%;
            width: 34px;
            height: 34px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            flex: 0 0 auto;
        }}

        .info-title {{
            color: #f97316;
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 6px;
        }}

        .info-text {{
            line-height: 1.6;
        }}
    </style>

    <div class="top-nav">
        <span class="user-pill">👤 {session.get("username", "")}</span>
        <a class="nav-btn" href="/mon_equipe">Mon équipe</a>
        <a class="nav-btn" href="/dashboard_equipe">Dashboard équipe</a>
        <a class="nav-btn" href="/logout">Déconnexion</a>
    </div>

    <div class="page">
        <div class="team-card">
            <div class="title-row">
                <div class="team-icon">👥</div>
                <h1>Mon équipe</h1>
            </div>

            <p class="subtitle">Gérez les commerciaux rattachés à votre compte</p>

            <a href="/" class="back-btn">← Retour</a>

            <div class="table-wrap">
                <table>
                    <tr>
                        <th>Manager</th>
                        <th>Identifiant commercial</th>
                        <th>Nom affiché</th>
                        <th>Actions</th>
                    </tr>
                    {rows}
                </table>
            </div>
        </div>

        <div class="info-box">
            <div class="info-icon">i</div>
            <div>
                <div class="info-title">Information</div>
                <div class="info-text">
                    Modifiez le nom affiché de vos commerciaux. Ce nom sera visible dans toute l'application.<br>
                    L'identifiant commercial sert à la connexion des utilisateurs.
                </div>
            </div>
        </div>
    </div>
    """

@app.route("/activity_logs")
@login_required
def activity_logs():
    if session.get("role") != "admin":
        return "Accès refusé", 403

    conn = get_auth_connection()
    logs = conn.execute("""
        SELECT username, role, action, details, created_at
        FROM activity_logs
        ORDER BY id DESC
        LIMIT 200
    """).fetchall()
    conn.close()

    rows = ""
    for log in logs:
        rows += f"<tr><td>{log['created_at']}</td><td>{log['username']}</td><td>{log['role']}</td><td>{log['action']}</td><td>{log['details']}</td></tr>"
    return f"<a href='/dashboard_equipe' style='display:inline-block;margin-bottom:15px;padding:8px 12px;background:#2563eb;color:white;text-decoration:none;border-radius:6px;'>⬅ Retour au dashboard</a><h1>Journal d'activité</h1><table border='1' cellpadding='8'><tr><th>Date</th><th>Utilisateur</th><th>Rôle</th><th>Action</th><th>Détail</th></tr>{rows}</table>"
    
@app.route("/dashboard_equipe")
@login_required
def dashboard_equipe():
    if session.get("role") not in ("manager", "admin"):
        return "Accès refusé", 403
    selected_month = request.args.get("month", "")
    selected_commercial = request.args.get("commercial", "")

    conn_auth = get_auth_connection()
    cur_auth = conn_auth.cursor()

    if session.get("role") == "admin":
        commerciaux = cur_auth.execute("""
            SELECT id, username, display_name, role, last_login_at
            FROM users
            WHERE role IN ('user', 'manager', 'admin')
        """).fetchall()
    else:
        commerciaux = cur_auth.execute("""
            SELECT id, username, display_name, role, last_login_at
            FROM users
            WHERE role = 'user' AND manager_id = ?

            UNION ALL

            SELECT id, username, username AS display_name, role, last_login_at
            FROM users
            WHERE id = ?
        """, (session.get("user_id"), session.get("user_id"))).fetchall()

    conn_auth.close()

    conn_campaign = get_campaign_connection()
    cur_campaign = conn_campaign.cursor()

    total_campaigns = 0
    total_commerces = 0
    total_quantite = 0
    active_commerciaux = set()
    support_totals = {}

    rows = ""

    for commercial in commerciaux:
        username = commercial["username"]
        display_name = commercial["display_name"] or username
        role_label = {"user": "Commercial", "manager": "Manager", "admin": "Admin"}.get(commercial["role"], commercial["role"])
        last_login = commercial["last_login_at"] or "Jamais connecté"

        if selected_commercial and username != selected_commercial:
            continue

        items = cur_campaign.execute("""
            SELECT
                campaigns.id,
                campaigns.name,
                campaigns.notes,
                campaigns.created_at,
                campaigns.support,
                campaigns.token,
                COUNT(campaign_items.id) AS nb_commerces,
                SUM(COALESCE(campaign_items.quantite, 0)) AS quantite_totale
            FROM campaigns
            LEFT JOIN campaign_items
                ON campaign_items.campaign_id = campaigns.id
            WHERE campaigns.created_by = ?
            GROUP BY campaigns.id
            ORDER BY campaigns.created_at DESC
        """, (username,)).fetchall()

        for item in items:
            created_at = item["created_at"]
            annee = created_at[:4]
            mois = created_at[5:7]
            mois_key = created_at[:7]

            if selected_month and mois_key != selected_month:
                continue

            total_campaigns += 1
    
            campaign_items_for_potential = cur_campaign.execute("""
                SELECT type
                FROM campaign_items
                WHERE campaign_id = ?
            """, (item["id"],)).fetchall()

            potential_data = [dict(row) for row in campaign_items_for_potential]

            _, totals_by_label = compute_potentiel_and_supports(potential_data)

            support_label = SUPPORT_LABELS.get(item["support"], "")

            if item["support"] == "all":
                potentiel_quantite = sum(totals_by_label.values())
            else:
                potentiel_quantite = totals_by_label.get(support_label, 0)
                total_commerces += int(
                potentiel_quantite / (item["quantite_totale"] / item["nb_commerces"])
                ) if item["nb_commerces"] and item["quantite_totale"] else 0

                total_quantite += potentiel_quantite    

            active_commerciaux.add(username)

            support_key = item["support"] or "Sans support"
            support_totals[support_key] = support_totals.get(support_key, 0) + 1

            rows += f"""
                <tr class="dashboard-row">
                    <td><span class="year-pill">{annee}</span></td>
                    <td><span class="month-pill">{mois}</span></td>
                    <td>
                        <span class="commercial-badge">👤 {display_name}<br><small>{role_label}</small><br><small>🕒 {last_login}</small></span>
                    </td>
                    <td>
                        {"<a class='campaign-link' href='/massive_campaign/" + str(item["id"]) + "'>" + item["name"] + "</a>" if item["notes"] == "Campagne massive" else "<strong>" + item["name"] + "</strong><br><a class='campaign-link' href='/campaign_resume/" + item["token"] + "'>📊 Ouvrir la campagne</a>"}
                    </td>
                    <td>
                        <span class="support-badge">{SUPPORT_LABELS.get(item["support"], item["support"] or "-")}</span>
                    </td>
                    <td>
                        {"<span class='type-badge type-massive'>Massive</span>" if item["notes"] == "Campagne massive" else "<span class='type-badge type-ciblee'>Ciblée</span>"}
                    </td>
                    <td><strong>{item['nb_commerces']}</strong></td>
                    <td><strong>{int(potentiel_quantite / (item['quantite_totale'] / item['nb_commerces'])) if item['nb_commerces'] and item['quantite_totale'] else 0}</strong></td>
                    <td>
                        <span class="potentiel-pill">{potentiel_quantite}</span>
                    </td>
                    <td>
                        <form method="POST" action="/campaign/{item['token']}/delete" onsubmit="return confirm('Supprimer cette campagne ?');">
                            <button type="submit" style="
                                background:#dc2626;
                                color:white;
                                border:none;
                                padding:8px 12px;
                                border-radius:6px;
                                cursor:pointer;
                                font-weight:bold;
                            ">
                                Supprimer
                            </button>
                        </form>
                    </td>
                </tr>
            """
            
    conn_campaign.close()

    commercial_options = ""
    for commercial in commerciaux:
        username = commercial["username"]
        display_name = commercial["display_name"] or username
        selected = "selected" if username == selected_commercial else ""
        commercial_options += f'<option value="{username}" {selected}>{display_name}</option>'

    support_summary = ""
    for support, count in support_totals.items():
        support_summary += f"""
            <div class="summary-card">
                <div class="summary-card-title">{"Tous les supports" if support == "all" else support}</div>
                <div class="summary-card-value">{count}</div>
            </div>
        """    

    return f"""
    <style>
        body {{
            margin: 0;
            background: #f4f6f8;
            font-family: Arial, sans-serif;
            color: #111827;
        }}

        .top-nav {{
            height: 78px;
            background: white;
            display: flex;
            justify-content: flex-end;
            align-items: center;
            gap: 14px;
            padding: 0 28px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        }}

        .user-pill {{
            font-size: 18px;
            margin-right: 20px;
        }}

        .nav-btn {{
            background: #ff5a00;
            color: white;
            text-decoration: none;
            padding: 13px 18px;
            border-radius: 8px;
            font-weight: bold;
        }}

        .dashboard-container {{
            margin: 24px;
            background: white;
            border-radius: 14px;
            padding: 34px 28px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        }}

        .dashboard-title-row {{
            display: flex;
            align-items: center;
            gap: 18px;
            margin-bottom: 8px;
        }}

        .dashboard-icon {{
            font-size: 42px;
            color: #5b2aa0;
        }}

        .dashboard-title {{
            font-size: 32px;
            font-weight: bold;
        }}

        .dashboard-subtitle {{
            margin: 0 0 28px 64px;
            color: #4b5563;
            font-size: 16px;
        }}

        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 22px;
            margin-bottom: 28px;
        }}

        .summary-card {{
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 22px;
            background: white;
            display: flex;
            align-items: center;
            gap: 20px;
            min-height: 100px;
        }}

        .summary-icon {{
            width: 64px;
            height: 64px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 30px;
            background: #fff1e6;
        }}

        .summary-card-title {{
            font-size: 16px;
            color: #111827;
            margin-bottom: 8px;
        }}

        .summary-card-value {{
            font-size: 30px;
            font-weight: bold;
            color: #111827;
        }}

        .summary-card-help {{
            color: #4b5563;
            font-size: 14px;
            margin-top: 4px;
        }}

        .filters {{
            display: grid;
            grid-template-columns: 1fr 1fr auto;
            gap: 28px;
            align-items: end;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 22px;
            margin-bottom: 28px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.04);
        }}

        .filter-group label {{
            display: block;
            font-weight: bold;
            margin-bottom: 10px;
        }}

        .filters input,
        .filters select {{
            width: 100%;
            padding: 13px 14px;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            font-size: 15px;
            box-sizing: border-box;
            background: white;
        }}

        .filters button {{
            background: #ff5a00;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 14px 26px;
            font-weight: bold;
            cursor: pointer;
            font-size: 15px;
        }}

        .back-link {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: linear-gradient(135deg, #ff5a00, #ff7a1a);
            color: white;
            text-decoration: none;
            padding: 12px 18px;
            border-radius: 10px;
            font-weight: bold;
            font-size: 15px;
            box-shadow: 0 4px 12px rgba(255,90,0,0.25);
            transition: all 0.2s ease;
        }}

        .back-link:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(255,90,0,0.35);
        }}

        .dashboard-table {{
            width: 100%;
            border-collapse: collapse;
            overflow: hidden;
            border-radius: 12px;
        }}

        .dashboard-table th {{
            background: #fff4e8;
            color: #111827;
            padding: 14px;
            text-align: left;
        }}

        .dashboard-table td {{
            padding: 14px;
            border-bottom: 1px solid #eee;
        }}

        .dashboard-table tr:nth-child(even) {{
            background: #fafafa;
        }}

        .dashboard-table tr:hover {{
            background: #fff4e8;
        }}

        .type-badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: bold;
        }}

        .type-ciblee {{
            background: #e8f5e9;
            color: #2e7d32;
        }}

        .type-massive {{
            background: #e3f2fd;
            color: #1565c0;
        }}
    </style>

    <div class="top-nav">
        <span class="user-pill">👤 {session.get("username", "")}</span>
        {"<a class='nav-btn' href='/activity_logs'>Journal d'activité</a>" if session.get("role") == "admin" else ""}
        <a class="nav-btn" href="/dashboard_equipe">Dashboard équipe</a>
        <a class="nav-btn" href="/logout">Déconnexion</a>
    </div>

    <div class="dashboard-container">

        <div class="dashboard-title-row">
            <div style="display:flex;align-items:center;gap:16px;">
                <div class="dashboard-icon">📊</div>
                <div>
                    <div class="dashboard-title">Dashboard équipe</div>
                    <p class="dashboard-subtitle">Vue d'ensemble des performances de votre équipe</p>
                </div>
            </div>

            <a href="/" class="back-link">← Retour</a>
        </div>

        <div class="summary-cards">
            <div class="summary-card">
                <div class="summary-icon">📋</div>
                <div>
                    <div class="summary-card-title">Total campagnes</div>
                    <div class="summary-card-value">{total_campaigns}</div>
                    <div class="summary-card-help">Campagnes créées</div>
                </div>
            </div>

            <div class="summary-card">
                <div class="summary-icon">🏪</div>
                <div>
                    <div class="summary-card-title">Total commerces</div>
                    <div class="summary-card-value">{total_commerces}</div>
                    <div class="summary-card-title">Commerces retenus</div>
                </div>
            </div>

            <div class="summary-card">
                <div class="summary-icon">📦</div>
                <div>
                    <div class="summary-card-title">Potentiel diffusion</div>
                    <div class="summary-card-value">{total_quantite}</div>
                    <div class="summary-card-help">Supports distribués</div>
                </div>
            </div>

            <div class="summary-card">
                <div class="summary-icon">👥</div>
                <div>
                    <div class="summary-card-title">Commerciaux actifs</div>
                    <div class="summary-card-value">{len(active_commerciaux)}</div>
                    <div class="summary-card-help">Sur la période filtrée</div>
                </div>
            </div>
        </div>

        <form method="GET" class="filters">
            <div class="filter-group">
                <label>Période</label>
                <input type="month" name="month" value="{selected_month}">
            </div>

            <div class="filter-group">
                <label>Commercial</label>
                <select name="commercial">
                    <option value="">Tous les commerciaux</option>
                    {commercial_options}
                </select>
            </div>

            <button type="submit">Filtrer</button>
        </form>

        <table class="dashboard-table">
            <tr>
                <th>Année</th>
                <th>Mois</th>
                <th>Commercial</th>
                <th>Campagne</th>
                <th>Support</th>
                <th>Type</th>
                <th>Commerces ciblés</th>
                <th>Commerces retenus</th>
                <th>Potentiel diffusion</th>
                <th>Action</th>
            </tr>
            {rows}
        </table>

    </div>
    """

@app.route("/mon_dashboard")
@login_required
def mon_dashboard():
    if session.get("role") != "user":
        return "Accès refusé", 403

    username = session.get("username", "")
    selected_month = request.args.get("month", "")

    conn = get_campaign_connection()
    cur = conn.cursor()

    targeted = cur.execute("""
        SELECT
            campaigns.id,
            campaigns.name,
            campaigns.notes,
            campaigns.created_at,
            campaigns.support,
            campaigns.token,
            COUNT(campaign_items.id) AS nb_commerces,
            SUM(COALESCE(campaign_items.quantite, 0)) AS quantite_totale
        FROM campaigns
        LEFT JOIN campaign_items
            ON campaign_items.campaign_id = campaigns.id
        WHERE campaigns.created_by = ?
        GROUP BY campaigns.id
        ORDER BY campaigns.created_at DESC
    """, (username,)).fetchall()

    total_ciblees = len(targeted)
    total_campaigns = total_ciblees

    total_commerces = 0
    total_quantite = 0

    rows = ""

    for item in targeted:
        created_at = item["created_at"] or ""
        date_label = created_at[:10]
        
        mois_key = created_at[:7]

        if selected_month and mois_key != selected_month:
            continue
            
        campaign_items_for_potential = cur.execute("""
            SELECT type
            FROM campaign_items
            WHERE campaign_id = ?
        """, (item["id"],)).fetchall()

        potential_data = [dict(row) for row in campaign_items_for_potential]

        _, totals_by_label = compute_potentiel_and_supports(potential_data)

        support_label = SUPPORT_LABELS.get(item["support"], "")

        if item["support"] == "all":
            potentiel_quantite = sum(totals_by_label.values())
        else:
            potentiel_quantite = totals_by_label.get(support_label, 0)
            total_commerces += int(
                potentiel_quantite / (item["quantite_totale"] / item["nb_commerces"])
            ) if item["nb_commerces"] and item["quantite_totale"] else 0

            total_quantite += potentiel_quantite
            
        rows += f"""
            <tr>
                <td>{date_label}</td>
                <td>
                    {"<a class='campaign-link' href='/massive_campaign/" + str(item["id"]) + "'>" + item["name"] + "</a>" if item["notes"] == "Campagne massive" else "<strong>" + item["name"] + "</strong><br><a class='campaign-link' href='/campaign_resume/" + item["token"] + "'>📊 Ouvrir la campagne</a>"}
                </td>
                <td><span class="support-badge">{SUPPORT_LABELS.get(item["support"], item["support"] or "-")}</span></td>
                <td>
                    {"<span class='type-badge type-massive'>Massive</span>" if item["notes"] == "Campagne massive" else "<span class='type-badge type-ciblee'>Ciblée</span>"}
                </td>
                <td>{item['nb_commerces'] or 0}</td>
                <td>{int(potentiel_quantite / (item['quantite_totale'] / item['nb_commerces'])) if item['nb_commerces'] and item['quantite_totale'] else 0}</td>
                <td>{potentiel_quantite}</td>
                <td>
                    <form method="POST" action="/campaign/{item['token']}/delete" onsubmit="return confirm('Supprimer cette campagne ?');">
                        <button type="submit" style="
                            background:#dc2626;
                            color:white;
                            border:none;
                            padding:8px 12px;
                            border-radius:6px;
                            cursor:pointer;
                            font-weight:bold;
                    ">
                        Supprimer
                    </button>
                </form>
            </td>
            </tr>
        """
    conn.close()
    
    return f"""
<style>
    body {{
        margin: 0;
        background: #f4f6f8;
        font-family: Arial, sans-serif;
        color: #111827;
    }}

    .top-nav {{
        height: 78px;
        background: white;
        display: flex;
        justify-content: flex-end;
        align-items: center;
        gap: 14px;
        padding: 0 28px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    }}

    .user-pill {{
        font-size: 18px;
        margin-right: 20px;
    }}

    .nav-btn {{
        background: #ff5a00;
        color: white;
        text-decoration: none;
        padding: 13px 18px;
        border-radius: 8px;
        font-weight: bold;
    }}

    .dashboard-container {{
        margin: 24px;
        background: white;
        border-radius: 14px;
        padding: 34px 28px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.08);
    }}

    .dashboard-title-row {{
        display: flex;
        align-items: center;
        gap: 18px;
        margin-bottom: 8px;
    }}

    .dashboard-icon {{
        font-size: 42px;
        color: #5b2aa0;
    }}

    .dashboard-title {{
        font-size: 32px;
        font-weight: bold;
    }}

    .dashboard-subtitle {{
        margin: 0 0 28px 64px;
        color: #4b5563;
        font-size: 16px;
    }}

    .summary-cards {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 22px;
        margin-bottom: 28px;
    }}

    .summary-card {{
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 22px;
        background: white;
        display: flex;
        align-items: center;
        gap: 20px;
        min-height: 100px;
    }}

    .summary-icon {{
        width: 64px;
        height: 64px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 30px;
        background: #fff1e6;
    }}

    .summary-card-title {{
        font-size: 16px;
        margin-bottom: 8px;
    }}

    .summary-card-value {{
        font-size: 30px;
        font-weight: bold;
    }}

    .summary-card-help {{
        color: #4b5563;
        font-size: 14px;
        margin-top: 4px;
    }}

    .dashboard-table {{
        width: 100%;
        border-collapse: collapse;
        overflow: hidden;
        border-radius: 12px;
    }}

    .dashboard-table th {{
        background: #fff4e8;
        color: #111827;
        padding: 14px;
        text-align: left;
    }}

    .dashboard-table td {{
        padding: 14px;
        border-bottom: 1px solid #eee;
    }}

    .dashboard-table tr:nth-child(even) {{
        background: #fafafa;
    }}

    .dashboard-table tr:hover {{
        background: #fff4e8;
    }}

    .campaign-link {{
        color: #4c1d95;
        font-weight: bold;
        text-decoration: none;
    }}

    .support-badge {{
        background: #fff7ed;
        color: #f97316;
        padding: 6px 12px;
        border-radius: 999px;
        font-weight: bold;
        font-size: 12px;
    }}

    .type-badge {{
        display: inline-block;
        padding: 6px 12px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: bold;
    }}

    .type-ciblee {{
        background: #e8f5e9;
        color: #2e7d32;
    }}

    .type-massive {{
        background: #e3f2fd;
        color: #1565c0;
    }}

    .filters {{
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 28px;
        align-items: end;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 22px;
        margin-bottom: 28px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.04);
    }}

    .filter-group label {{
        display: block;
        font-weight: bold;
        margin-bottom: 10px;
    }}

    .filters input {{
        width: 100%;
        padding: 13px 14px;
        border: 1px solid #d1d5db;
        border-radius: 8px;
        font-size: 15px;
        box-sizing: border-box;
        background: white;
    }}

    .filters button {{
        background: #ff5a00;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 14px 26px;
        font-weight: bold;
        cursor: pointer;
        font-size: 15px;
    }}

    .back-link {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: linear-gradient(135deg, #ff5a00, #ff7a1a);
        color: white;
        text-decoration: none;
        padding: 12px 18px;
        border-radius: 10px;
        font-weight: bold;
        font-size: 15px;
        box-shadow: 0 4px 12px rgba(255,90,0,0.25);
        transition: all 0.2s ease;
    }}

    .back-link:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(255,90,0,0.35);
    }}
    
</style>

<div class="top-nav">
    <span class="user-pill">👤 {username}</span>
    <a class="nav-btn" href="/logout">Déconnexion</a>
</div>

<div class="dashboard-container">

    <div class="dashboard-title-row">
        <div style="display:flex;align-items:center;gap:16px;">
            <div class="dashboard-icon">📊</div>
            <div>
                <div class="dashboard-title">Mon dashboard</div>
                <p class="dashboard-subtitle">Vue d'ensemble de vos campagnes et distributions</p>
            </div>
        </div>

        <a href="/" class="back-link">← Retour</a>
    </div>

    <div class="summary-cards">
        <div class="summary-card">
            <div class="summary-icon">📋</div>
            <div>
                <div class="summary-card-title">Total campagnes</div>
                <div class="summary-card-value">{total_campaigns}</div>
                <div class="summary-card-help">Ciblées + massives</div>
            </div>
        </div>

        <div class="summary-card">
            <div class="summary-icon">🎯</div>
            <div>
                <div class="summary-card-title">Campagnes</div>
                <div class="summary-card-value">{total_ciblees}</div>
                <div class="summary-card-help">Campagnes enregistrées</div>
            </div>
        </div>

        <div class="summary-card">
            <div class="summary-icon">🏪</div>
            <div>
                <div class="summary-card-title">Commerces retenus</div>
                <div class="summary-card-value">{total_commerces}</div>
                <div class="summary-card-help">Toutes campagnes</div>
            </div>
        </div>

        <div class="summary-card">
            <div class="summary-icon">📦</div>
            <div>
                <div class="summary-card-title">Potentiel diffusion</div>
                <div class="summary-card-value">{total_quantite}</div>
                <div class="summary-card-help">Supports distribués</div>
            </div>
        </div>
    </div>

    <form method="GET" class="filters">
        <div class="filter-group">
            <label>Période</label>
            <input type="month" name="month" value="{selected_month}">
        </div>

        <button type="submit">Filtrer</button>
    </form>

    <table class="dashboard-table">
        <tr>
            <th>Date</th>
            <th>Campagne</th>
            <th>Support</th>
            <th>Type</th>
            <th>Commerces ciblés</th>
            <th>Commerces retenus</th>
            <th>Potentiel diffusion</th>
            <th>Action</th>
        </tr>
        {rows}
    </table>

</div>
"""    
    
@app.route("/commercial/<int:user_id>")
@login_required
def commercial_detail(user_id):
    if session.get("role") not in ("manager", "admin"):
        return "Accès refusé", 403

    conn = get_auth_connection()
    cur = conn.cursor()

    if session.get("role") == "admin":
        commercial = cur.execute("""
            SELECT u.id, u.username, u.display_name, u.role, m.username AS manager_username
            FROM users u
            LEFT JOIN users m ON m.id = u.manager_id
            WHERE u.id = ? AND u.role = 'user'
        """, (user_id,)).fetchone()
    else:
        commercial = cur.execute("""
            SELECT u.id, u.username, u.display_name, u.role, m.username AS manager_username
            FROM users u
            LEFT JOIN users m ON m.id = u.manager_id
            WHERE u.id = ? AND u.manager_id = ? AND u.role = 'user'
        """, (user_id, session.get("user_id"))).fetchone()

    conn.close()

    if not commercial:
        return "Commercial introuvable", 404

    conn_campaign = sqlite3.connect(CAMPAIGN_DB_FILE)
    conn_campaign.row_factory = sqlite3.Row
    cur_campaign = conn_campaign.cursor()

    campaigns = cur_campaign.execute("""
    SELECT
        campaigns.id,
        campaigns.name,
        campaigns.created_at,
        campaigns.token,
        COUNT(campaign_items.id) AS nb_items
    FROM campaigns
    LEFT JOIN campaign_items ON campaign_items.campaign_id = campaigns.id
    WHERE campaigns.created_by = ?
    GROUP BY campaigns.id
    ORDER BY campaigns.created_at DESC
""", (commercial["username"],)).fetchall()

    conn_campaign.close()
    conn_massive = sqlite3.connect(CAMPAIGN_DB_FILE)
    conn_massive.row_factory = sqlite3.Row
    cur_massive = conn_massive.cursor()

    massive_exports = cur_massive.execute("""
        SELECT filename, nb_commerces, created_at
        FROM massive_exports
        WHERE username = ?
        ORDER BY created_at DESC
    """, (commercial["username"],)).fetchall()

    conn_massive.close()

    campaign_rows = ""
    for campaign in campaigns:
        campaign_rows += f"""
            <li>
                <a href="/campaign/{campaign['token']}">{campaign['name']}</a>
                ({campaign['created_at']}) — {campaign['nb_items']} commerce(s)
            </li>
        """

    if not campaign_rows:
        campaign_rows = "<li>Aucune campagne</li>"

    massive_rows = ""
    for export in massive_exports:
        massive_rows += f"""
            <li>
                {export['filename']} ({export['created_at']}) — {export['nb_commerces']} commerce(s)
            </li>
        """

    if not massive_rows:
        massive_rows = "<li>Aucun export massif</li>"

    return f"""
    <h2>Fiche commercial</h2>
    <p><a href="/mon_equipe">← Retour équipe</a></p>

    <p><b>Identifiant :</b> {commercial['username']}</p>
    <p><b>Nom affiché :</b> {commercial['display_name'] or ''}</p>
    <p><b>Manager :</b> {commercial['manager_username'] or ''}</p>

    <h3>Campagnes ciblées</h3>
    <ul>
        {campaign_rows}
    </ul>
    <h3>Campagnes massives</h3>
    <ul>
        {massive_rows}
    </ul>
    """

if __name__ == "__main__":
    print("DB commerces utilisée =", Path(DB_FILE).resolve())
    print("DB auth utilisée      =", Path(AUTH_DB_FILE).resolve())
    app.run(debug=True)
