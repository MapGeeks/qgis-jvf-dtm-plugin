"""
@brief Symbol processor

Classes:
 - SymbolProcessor

(C) 2024-2025 by MapGeeks
@author Petr Barandovski petr.barandovski@gmail.com
@author Linda Karlovska linda.karlovska@seznam.cz

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.    
"""

from typing import Dict, Optional, Any
from qgis.core import (
    QgsSymbol, QgsLineSymbol, QgsMarkerSymbol, QgsFillSymbol,
    QgsSimpleMarkerSymbolLayer, QgsSvgMarkerSymbolLayer,
    QgsSimpleLineSymbolLayer, QgsSimpleFillSymbolLayer,
    QgsSimpleMarkerSymbolLayerBase, QgsSymbolLayer
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, QPointF
import logging

logger = logging.getLogger(__name__)

class SymbolProcessor:
    """Třída pro zpracování a vytváření QGIS symbolů"""
    
    def __init__(self):
        self._symbol_cache: Dict[str, QgsSymbol] = {}
        self._setup_symbol_maps()

    def _setup_symbol_maps(self) -> None:
        """Inicializace mapování pro různé typy symbolů"""
        self.symbol_types = {
            'marker': QgsMarkerSymbol,
            'line': QgsLineSymbol,
            'fill': QgsFillSymbol
        }

        self.layer_types = {
            'SimpleMarker': QgsSimpleMarkerSymbolLayer,
            'SvgMarker': QgsSvgMarkerSymbolLayer,
            'SimpleLine': QgsSimpleLineSymbolLayer,
            'SimpleFill': QgsSimpleFillSymbolLayer
        }

        self.shape_map = {
            'square': QgsSimpleMarkerSymbolLayerBase.Square,
            'diamond': QgsSimpleMarkerSymbolLayerBase.Diamond,
            'circle': QgsSimpleMarkerSymbolLayerBase.Circle,
            'triangle': QgsSimpleMarkerSymbolLayerBase.Triangle,
            'pentagon': QgsSimpleMarkerSymbolLayerBase.Pentagon,
            'hexagon': QgsSimpleMarkerSymbolLayerBase.Hexagon,
            'star': QgsSimpleMarkerSymbolLayerBase.Star,
            'arrow': QgsSimpleMarkerSymbolLayerBase.Arrow,
            'cross': QgsSimpleMarkerSymbolLayerBase.Cross,
            'cross2': QgsSimpleMarkerSymbolLayerBase.Cross2
        }

    def create_symbol_from_json(self, symbol_dict: Dict[str, Any]) -> Optional[QgsSymbol]:
        """
        Vytvoří QGIS symbol z JSON definice.
        
        Args:
            symbol_dict: Slovník obsahující definici symbolu
            
        Returns:
            QgsSymbol nebo None pokud vytvoření selže
        """
        # Kontrola cache
        cache_key = str(hash(str(symbol_dict)))
        if cache_key in self._symbol_cache:
            return self._symbol_cache[cache_key].clone()

        # Vytvoření nového symbolu
        symbol_class = self.symbol_types.get(symbol_dict['type'])
        if not symbol_class:
            logger.error(f"Unsupported symbol type: {symbol_dict['type']}")
            return None

        try:
            symbol = symbol_class()
            # Odstraníme výchozí vrstvu
            while symbol.symbolLayerCount() > 0:
                symbol.deleteSymbolLayer(0)

            # Přidáme vrstvy symbolu
            for layer_def in symbol_dict.get('layers', []):
                if sl := self._create_symbol_layer(layer_def):
                    if sl.isCompatibleWithSymbol(symbol):
                        symbol.appendSymbolLayer(sl)

            # Uložíme do cache
            self._symbol_cache[cache_key] = symbol.clone()
            return symbol

        except Exception as e:
            logger.error(f"Error creating symbol: {e}")
            return None

    def _create_symbol_layer(self, layer_def: Dict[str, Any]) -> Optional[QgsSymbolLayer]:
        """
        Vytvoří vrstvu symbolu z definice.
        
        Args:
            layer_def: Slovník obsahující definici vrstvy symbolu
            
        Returns:
            QgsSymbolLayer nebo None pokud vytvoření selže
        """
        try:
            layer_type = layer_def.get('type')
            layer_class = self.layer_types.get(layer_type)
            
            if not layer_class:
                logger.error(f"Unsupported layer type: {layer_type}")
                return None

            if layer_type == 'SvgMarker':
                sl = layer_class(layer_def.get('svg_data', ''))
                sl.setPath(layer_def.get('svg_data', ''))
                sl.setOffset(QPointF(0.5, 0.5))
            else:
                sl = layer_class()

            self._set_layer_properties(sl, layer_def)
            return sl

        except Exception as e:
            logger.error(f"Error creating symbol layer: {e}")
            return None

    def _set_layer_properties(self, symbol_layer: QgsSymbolLayer, properties: Dict[str, Any]) -> None:
        """
        Nastaví vlastnosti vrstvy symbolu.
        
        Args:
            symbol_layer: Vrstva symbolu
            properties: Slovník vlastností k nastavení
        """
        try:
            # Společné vlastnosti
            if 'color' in properties:
                color = [int(x) for x in properties['color'].split(',')]
                symbol_layer.setColor(QColor(*color))

            # Specifické vlastnosti pro markery
            if isinstance(symbol_layer, QgsSimpleMarkerSymbolLayer):
                self._set_marker_properties(symbol_layer, properties)
            
            # Specifické vlastnosti pro linie
            elif isinstance(symbol_layer, QgsSimpleLineSymbolLayer):
                self._set_line_properties(symbol_layer, properties)
            
            # Specifické vlastnosti pro výplně
            elif isinstance(symbol_layer, QgsSimpleFillSymbolLayer):
                self._set_fill_properties(symbol_layer, properties)

        except Exception as e:
            logger.error(f"Error setting layer properties: {e}")

    def _set_marker_properties(self, layer: QgsSimpleMarkerSymbolLayer, properties: Dict[str, Any]) -> None:
        """Nastaví vlastnosti marker symbolu"""
        if 'size' in properties:
            layer.setSize(float(properties['size']))
        
        if 'symbol_type' in properties:
            shape = self.shape_map.get(properties['symbol_type'].lower())
            if shape is not None:
                layer.setShape(shape)
        
        if 'outline_color' in properties:
            color = [int(x) for x in properties['outline_color'].split(',')]
            layer.setStrokeColor(QColor(*color))
        
        if 'outline_width' in properties:
            layer.setStrokeWidth(float(properties['outline_width']))

    def _set_line_properties(self, layer: QgsSimpleLineSymbolLayer, properties: Dict[str, Any]) -> None:
        """Nastaví vlastnosti liniového symbolu"""
        if 'width' in properties:
            layer.setWidth(float(properties['width']))
        
        if 'line_style' in properties:
            layer.setPenStyle(Qt.SolidLine if properties['line_style'] == 'solid' else Qt.DashLine)
        
        if properties.get('use_custom_dash') == '1' and 'customdash' in properties:
            pattern = [float(x) for x in properties['customdash'].split(';')]
            layer.setCustomDashVector(pattern)
            layer.setUseCustomDashPattern(True)

    def _set_fill_properties(self, layer: QgsSimpleFillSymbolLayer, properties: Dict[str, Any]) -> None:
        """Nastaví vlastnosti výplňového symbolu"""
        if 'outline_color' in properties:
            color = [int(x) for x in properties['outline_color'].split(',')]
            layer.setStrokeColor(QColor(*color))
        
        if 'outline_width' in properties:
            layer.setStrokeWidth(float(properties['outline_width']))
        
        if 'style' in properties:
            layer.setBrushStyle(Qt.SolidPattern)

    def clear_cache(self) -> None:
        """Vyčistí cache symbolů"""
        self._symbol_cache.clear()