"""
@brief Style manager

Classes:
 - StyleManager

(C) 2024-2025 by MapGeeks
@author Petr Barandovski petr.barandovski@gmail.com
@author Linda Karlovska linda.karlovska@seznam.cz

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.    
"""

import json
import logging
from typing import Optional, Dict
import pandas as pd

from .helpers import resolve_path, load_config

logger = logging.getLogger(__name__)


class StyleManager:
    """Třída pro efektivní správu stylů"""

    def __init__(self):
        self._style_cache: Dict[str, str] = {}

        self.initialized: bool = False
        self.style_df: Optional[pd.DataFrame] = None

    def load_styles(self, filename: Optional[str] = None) -> None:
        """
        Načte styly z CSV souboru a uloží je do cache pro rychlý přístup.
        Provede se pouze jednou při prvním požadavku.

        Args:
            filename (Optional[str]): Cesta k souboru se styly. Pokud není zadána,
                                      použije se cesta z konfigurace.
        """
        if self.initialized:
            return

        config = load_config()
        filename = filename or config.get("styles", None)

        try:
            # Načtení CSV souboru s optimalizací na potřebné sloupce
            self.style_df = pd.read_csv(
                resolve_path(filename),
                delimiter="|",
                encoding="utf-8",
                dtype={"key": str, "qgis_symbol": str},
                usecols=["key", "qgis_symbol"],
                quotechar='"',
                keep_default_na=False,
            )
            # Převedeme DataFrame na dict pro O(1) přístup
            self._style_cache = dict(
                zip(self.style_df["key"], self.style_df["qgis_symbol"])
            )
            self.initialized = True

        except Exception as e:
            logger.error(f"Error loading styles: {e}")
            self._style_cache = {}
            self.initialized = False

    def get_style(self, style_key: str) -> Optional[dict]:
        """
        Získá styl z cache podle klíče.
        Podporuje fallback logiku pro různé varianty klíčů.
        """
        # Přímé vyhledání v cache
        if style := self._style_cache.get(style_key):
            return json.loads(style)

        # Fallback logika pro různé varianty klíčů
        if "nezjištěno/neurčeno" in style_key:
            # Zkusíme variantu s "nezjištěno"
            alt_key = style_key.replace("nezjištěno/neurčeno", "nezjištěno")
            if style := self._style_cache.get(alt_key):
                return json.loads(style)

            # Zkusíme variantu s "neurčeno"
            alt_key = style_key.replace("nezjištěno/neurčeno", "neurčeno")
            if style := self._style_cache.get(alt_key):
                return json.loads(style)

        # Zkusíme verzi bez typu
        if " - " in style_key:
            parts = style_key.split(" - ")
            base_name = parts[0] + "_" + style_key.split("_")[-1]
            alt_key = f"{base_name}_{style_key.split('_')[-1]}"
            if style := self._style_cache.get(alt_key):
                return json.loads(style)

        return None
