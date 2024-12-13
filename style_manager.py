from typing import Optional, Dict
import pandas as pd
import json
import logging

logger = logging.getLogger(__name__)

class StyleManager:
    """Třída pro efektivní správu stylů"""
    
    def __init__(self):
        self._style_cache: Dict[str, str] = {}
        self._style_df: Optional[pd.DataFrame] = None
        self._initialized: bool = False

    def load_styles(self, filename: str) -> None:
        """
        Načte styly z CSV souboru a uloží je do cache pro rychlý přístup.
        Provede se pouze jednou při prvním požadavku.
        """
        if self._initialized:
            return

        try:
            # Načteme CSV efektivněji - pouze potřebné sloupce
            self._style_df = pd.read_csv(
                filename,
                delimiter='|',
                encoding='utf-8',
                dtype={'key': str, 'qgis_symbol': str},
                usecols=['key', 'qgis_symbol'],
                quotechar='"',
                keep_default_na=False
            )
            
            # Převedeme DataFrame na dict pro O(1) přístup
            self._style_cache = dict(zip(self._style_df['key'], self._style_df['qgis_symbol']))
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Error loading styles: {e}")
            self._style_cache = {}
            self._initialized = False

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