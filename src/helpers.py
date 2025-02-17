"""
@brief General helper functions

Functions:
 - resolve_path
 - load_config
 - load_type_mapping

(C) 2024-2025 by MapGeeks
@author Petr Barandovski petr.barandovski@gmail.com
@author Linda Karlovska linda.karlovska@seznam.cz

This plugin is free under the MIT License.
"""

import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)


def resolve_path(name: str, basepath: Optional[str] = None) -> str:
    """
    Vyřeší cestu k souboru relativně k umístění základní cesty.

    Args:
        name (str): Název souboru.
        basepath (Optional[str]): Základní cesta (výchozí je adresář skriptu).

    Returns:
        str: Absolutní cesta k souboru.
    """
    if not basepath:
        basepath = Path(__file__).parent
    return str(Path(basepath) / name)


def load_config(config_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Načte konfiguraci z JSON souboru.

    Args:
        config_file (Optional[str]): Cesta ke konfiguračnímu souboru.
                                     Pokud není uvedena, použije se výchozí cesta.

    Returns:
        Dict[str, Any]: Slovník s konfigurací.
    """
    # Výchozí cesta ke konfiguračnímu souboru
    default_config_path = resolve_path("config.json")

    # Použij zadanou cestu nebo výchozí
    config_path = config_file or default_config_path

    try:
        with open(config_path, "r") as file:
            return json.load(file)
    except Exception as e:
        raise FileNotFoundError(
            f"Chyba při načítání konfigurace z '{config_path}': {e}"
        )


def load_type_mapping() -> Optional[pd.DataFrame]:
    """
    Načte mapování typů z CSV souboru.

    Returns:
        DataFrame s mapováním typů nebo None při chybě
    """
    try:
        config = load_config()
        df = pd.read_csv(
            resolve_path(config.get("type_mapping", None)),
            delimiter="|",
            encoding="utf-8",
            names=["code", "attributes"],
            dtype=str,
        )
        df["code"] = df["code"].str.strip()
        df["attributes"] = df["attributes"].str.split(";")
        return df

    except Exception as e:
        logger.error(f"Error loading type mapping: {e}")
        return None
