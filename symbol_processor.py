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
    Qgis, QgsSymbol, QgsLineSymbol, QgsMarkerSymbol, QgsFillSymbol,
    QgsSimpleMarkerSymbolLayer, QgsSvgMarkerSymbolLayer,
    QgsSimpleLineSymbolLayer, QgsSimpleFillSymbolLayer,
    QgsMarkerLineSymbolLayer, QgsCentroidFillSymbolLayer,
    QgsPointPatternFillSymbolLayer, QgsLinePatternFillSymbolLayer,
    QgsSymbolLayer
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import Qt, QPointF
import logging
import re

logger = logging.getLogger(__name__)

_RE_PATH_D = re.compile(r'\sd="([^"]*)"')
_RE_TOKEN = re.compile(r'[A-Za-z]|-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?')
_RE_VIEWBOX = re.compile(r'viewBox="[^"]*"')

# Okraj kolem kresby v jednotkách SVG (zdrojové SVG mají kresbu od 6.0)
_SVG_OKRAJ = 6.0
# Rozměr viewBoxu zdrojových SVG
_SVG_MIN_VIEWBOX = 100.0
# viewBox SVG z původního styles.csv (jen u nich se používá korekce posunu)
_RE_PUVODNI_VIEWBOX = re.compile(r'viewBox="0 0 100 100"')

_CAP = {'flat': Qt.PenCapStyle.FlatCap, 'butt': Qt.PenCapStyle.FlatCap,
        'square': Qt.PenCapStyle.SquareCap, 'round': Qt.PenCapStyle.RoundCap}
_JOIN = {'miter': Qt.PenJoinStyle.MiterJoin, 'bevel': Qt.PenJoinStyle.BevelJoin,
         'round': Qt.PenJoinStyle.RoundJoin}


def _offset(value: str) -> QPointF:
    """'x,y' -> QPointF"""
    x, y = (float(v) for v in str(value).split(','))
    return QPointF(x, y)


def vycentruj_svg(svg_data: str) -> str:
    """
    Upraví viewBox SVG tak, aby střed kresby ležel ve středu viewBoxu.

    Zdrojová SVG ve styles.csv mají viewBox "0 0 100 100", ale kresbu mimo
    jeho střed (křížek podrobného bodu je v 6-66, čtverce v 6-206 apod.).
    QGIS ukotvuje značku na střed viewBoxu, takže značka byla posunutá
    vůči bodu a dřív se to obcházelo pevným offsetem 0.5 mm. Ten ale v DXF
    exportu (osa Y je otočená) posun naopak zdvojnásobil.

    Upraví se jen SVG, jejichž kresba se do viewBoxu 100 vejde (např. křížek
    podrobného bodu): viewBox se jen posune, velikost kresby zůstane stejná.
    SVG s kresbou větší než viewBox (čtverce 6-206 apod.) se nemění, protože
    jejich vycentrování by změnilo i jejich velikost nebo ořez v QGIS.

    Zpracuje jen cesty s absolutními příkazy M, L, Z; jinak vrátí SVG beze změny.
    """
    xs, ys = [], []
    for d in _RE_PATH_D.findall(svg_data):
        tokeny = _RE_TOKEN.findall(d)
        cisla = []
        for t in tokeny:
            if t.isalpha():
                if t not in ('M', 'L', 'Z'):
                    return svg_data  # relativní příkazy, křivky... -> neměnit
                if len(cisla) % 2:
                    return svg_data
                continue
            cisla.append(float(t))
        if len(cisla) % 2:
            return svg_data
        xs.extend(cisla[0::2])
        ys.extend(cisla[1::2])

    if not xs or not _RE_VIEWBOX.search(svg_data):
        return svg_data

    strana = _SVG_MIN_VIEWBOX
    if (max(xs) - min(xs) + 2 * _SVG_OKRAJ > strana
            or max(ys) - min(ys) + 2 * _SVG_OKRAJ > strana):
        return svg_data  # kresba větší než viewBox -> ponechat

    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    vb = f'viewBox="{cx - strana / 2:g} {cy - strana / 2:g} {strana:g} {strana:g}"'
    return _RE_VIEWBOX.sub(vb, svg_data, count=1)


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
            'SimpleFill': QgsSimpleFillSymbolLayer,
            'MarkerLine': QgsMarkerLineSymbolLayer,
            'CentroidFill': QgsCentroidFillSymbolLayer,
            'PointPatternFill': QgsPointPatternFillSymbolLayer,
            'LinePatternFill': QgsLinePatternFillSymbolLayer,
        }

        self.shape_map = {
            'square': Qgis.MarkerShape.Square,
            'diamond': Qgis.MarkerShape.Diamond,
            'circle': Qgis.MarkerShape.Circle,
            'triangle': Qgis.MarkerShape.Triangle,
            'pentagon': Qgis.MarkerShape.Pentagon,
            'hexagon': Qgis.MarkerShape.Hexagon,
            'star': Qgis.MarkerShape.Star,
            'arrow': Qgis.MarkerShape.Arrow,
            'cross': Qgis.MarkerShape.Cross,
            'cross2': Qgis.MarkerShape.Cross2
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
                puvodni_svg = layer_def.get('svg_data', '')
                if _RE_PUVODNI_VIEWBOX.search(puvodni_svg):
                    # SVG z původního styles.csv (kresba mimo střed viewBoxu)
                    svg = vycentruj_svg(puvodni_svg)
                    sl = layer_class(svg)
                    sl.setPath(svg)
                    if svg == puvodni_svg:
                        # Nevycentrované SVG: původní korekce posunu kresby.
                        # U vycentrovaných se nepoužívá - v DXF exportu (otočená
                        # osa Y) značky naopak posouvala.
                        sl.setOffset(QPointF(0.5, 0.5))
                else:
                    # SVG převedené z CIM: střed viewBoxu je kotevní bod,
                    # velikost, natočení a posun jsou v definici vrstvy
                    sl = layer_class(puvodni_svg)
                    sl.setPath(puvodni_svg)
                    if 'size' in layer_def:
                        sl.setSize(float(layer_def['size']))
                    if 'angle' in layer_def:
                        sl.setAngle(float(layer_def['angle']))
                    if 'offset' in layer_def:
                        sl.setOffset(_offset(layer_def['offset']))
                return sl
            elif layer_type in ('MarkerLine', 'CentroidFill', 'PointPatternFill'):
                return self._create_placed_marker_layer(layer_class, layer_def)
            elif layer_type == 'LinePatternFill':
                sl = layer_class()
                sl.setLineAngle(float(layer_def.get('angle', 0)))
                sl.setDistance(float(layer_def.get('distance', 5)))
                sl.setLineWidth(float(layer_def.get('line_width', 0.26)))
                if 'color' in layer_def:
                    sl.setColor(QColor(*[int(x) for x in layer_def['color'].split(',')]))
                return sl
            else:
                sl = layer_class()

            self._set_layer_properties(sl, layer_def)
            return sl

        except Exception as e:
            logger.error(f"Error creating symbol layer: {e}")
            return None

    def _create_placed_marker_layer(self, layer_class, layer_def: Dict[str, Any]) -> Optional[QgsSymbolLayer]:
        """Značka na linii / v těžišti / vzorek bodů - podsymbol z klíče 'marker'."""
        marker = self.create_symbol_from_json({'type': 'marker', 'layers': [layer_def['marker']]})
        if marker is None or marker.symbolLayerCount() == 0:
            return None
        sl = layer_class()
        if isinstance(sl, QgsMarkerLineSymbolLayer):
            sl.setInterval(float(layer_def.get('interval', 3)))
            sl.setOffsetAlongLine(float(layer_def.get('offset_along_line', 0)))
            sl.setOffset(float(layer_def.get('offset', 0)))
            sl.setRotateSymbols(layer_def.get('rotate', '1') == '1')
        elif isinstance(sl, QgsCentroidFillSymbolLayer):
            sl.setPointOnSurface(layer_def.get('point_on_surface', '0') == '1')
        elif isinstance(sl, QgsPointPatternFillSymbolLayer):
            sl.setDistanceX(float(layer_def.get('distance_x', 10)))
            sl.setDistanceY(float(layer_def.get('distance_y', 10)))
        sl.setSubSymbol(marker)
        return sl

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

        if 'angle' in properties:
            layer.setAngle(float(properties['angle']))

        if 'offset' in properties:
            layer.setOffset(_offset(properties['offset']))

    def _set_line_properties(self, layer: QgsSimpleLineSymbolLayer, properties: Dict[str, Any]) -> None:
        """Nastaví vlastnosti liniového symbolu"""
        if 'width' in properties:
            layer.setWidth(float(properties['width']))
        
        if 'line_style' in properties:
            layer.setPenStyle(Qt.PenStyle.SolidLine if properties['line_style'] == 'solid' else Qt.PenStyle.DashLine)
        
        if properties.get('use_custom_dash') == '1' and 'customdash' in properties:
            pattern = [float(x) for x in properties['customdash'].split(';')]
            layer.setCustomDashVector(pattern)
            layer.setUseCustomDashPattern(True)

        if 'pen_cap_style' in properties and properties['pen_cap_style'] in _CAP:
            layer.setPenCapStyle(_CAP[properties['pen_cap_style']])

        if 'pen_join_style' in properties and properties['pen_join_style'] in _JOIN:
            layer.setPenJoinStyle(_JOIN[properties['pen_join_style']])

        if 'offset' in properties:
            layer.setOffset(float(properties['offset']))

    def _set_fill_properties(self, layer: QgsSimpleFillSymbolLayer, properties: Dict[str, Any]) -> None:
        """Nastaví vlastnosti výplňového symbolu"""
        if 'outline_color' in properties:
            color = [int(x) for x in properties['outline_color'].split(',')]
            layer.setStrokeColor(QColor(*color))
        
        if 'outline_width' in properties:
            layer.setStrokeWidth(float(properties['outline_width']))
        
        if 'style' in properties:
            layer.setBrushStyle(Qt.BrushStyle.SolidPattern)

        if properties.get('outline_style') == 'no':
            layer.setStrokeStyle(Qt.PenStyle.NoPen)

    def clear_cache(self) -> None:
        """Vyčistí cache symbolů"""
        self._symbol_cache.clear()