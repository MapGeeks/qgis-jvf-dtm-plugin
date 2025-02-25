"""
@brief Feature batch processing

Classes:
 - BatchFeatureProcessor

(C) 2024-2025 by MapGeeks
@author Petr Barandovski petr.barandovski@gmail.com
@author Linda Karlovska linda.karlovska@seznam.cz

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.    
"""

from typing import List
import logging

from qgis.core import QgsFeature, QgsVectorLayer

logger = logging.getLogger(__name__)


class BatchFeatureProcessor:
    """Třída pro dávkové zpracování features"""

    def __init__(self, batch_size: int = 1000):
        """
        Inicializace procesoru.

        Args:
            batch_size: Velikost dávky pro zpracování
        """
        self.batch_size = batch_size
        self._current_batch: List[QgsFeature] = []
        self._target_layer: QgsVectorLayer = None

    def set_target_layer(self, layer: QgsVectorLayer) -> None:
        """
        Nastaví cílovou vrstvu pro zpracování features.

        Args:
            layer: QGIS vektorová vrstva
        """
        self._target_layer = layer
        self._current_batch = []

    def add_feature(self, feature: QgsFeature) -> None:
        """
        Přidá feature do aktuální dávky.

        Args:
            feature: QGIS feature k přidání
        """
        self._current_batch.append(feature)

        if len(self._current_batch) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        """
        Zpracuje aktuální dávku features.
        """
        if not self._current_batch or not self._target_layer:

            return

        try:
            self._target_layer.dataProvider().addFeatures(self._current_batch)
            self._target_layer.updateExtents()

        except Exception as e:

            print(f"Error adding features batch: {e}")
        finally:
            self._current_batch = []

    def process_features(
        self, features: List[QgsFeature], layer: QgsVectorLayer
    ) -> None:

        """
        Zpracuje seznam features pro danou vrstvu.

        Args:
            features: Seznam QGIS features k zpracování
            layer: Cílová QGIS vektorová vrstva
        """
        self.set_target_layer(layer)

        for feature in features:
            self.add_feature(feature)

        self.flush()
