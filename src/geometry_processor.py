"""
@brief Geometry processing

Classes:
 - GeometryProcessor

(C) 2024-2025 by MapGeeks
@author Petr Barandovski petr.barandovski@gmail.com
@author Linda Karlovska linda.karlovska@seznam.cz

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.    
"""

import logging
import lxml.etree as ET
from typing import Dict, Tuple, Optional, Generator
from osgeo import ogr

from qgis.core import QgsGeometry, QgsWkbTypes

logger = logging.getLogger(__name__)


class GeometryProcessor:
    """Třída pro efektivní zpracování geometrií"""

    def __init__(self):
        self._geom_cache: Dict[str, Tuple[QgsGeometry, str, str]] = {}
        self.ns = {"gml": "http://www.opengis.net/gml/3.2", "x": "*"}

    @staticmethod
    def _get_geometry_type(qgs_geom: QgsGeometry) -> Optional[str]:
        """
        Určí typ geometrie z QgsGeometry.

        Args:
            qgs_geom: QGIS geometrie

        Returns:
            Textový popis typu geometrie nebo None
        """
        type_mapping = {
            QgsWkbTypes.Point: "Point",
            QgsWkbTypes.PointZ: "Point",
            QgsWkbTypes.MultiPoint: "Point",
            QgsWkbTypes.MultiPointZ: "Point",
            QgsWkbTypes.LineString: "LineString",
            QgsWkbTypes.LineStringZ: "LineString",
            QgsWkbTypes.MultiLineString: "LineString",
            QgsWkbTypes.MultiLineStringZ: "LineString",
            QgsWkbTypes.Polygon: "Polygon",
            QgsWkbTypes.PolygonZ: "Polygon",
            QgsWkbTypes.MultiPolygon: "Polygon",
            QgsWkbTypes.MultiPolygonZ: "Polygon",
        }

        return type_mapping.get(qgs_geom.wkbType())

    def _parse_geometry(
        self, geom_elem: ET.Element
    ) -> Optional[Tuple[QgsGeometry, str, str]]:
        """
        Parsuje XML element na QGIS geometrii.

        Args:
            geom_elem: XML element obsahující geometrii

        Returns:
            Tuple obsahující (QgsGeometry, gml_id, typ_geometrie) nebo None
        """
        try:
            gml_id = geom_elem.get(f'{{{self.ns["gml"]}}}id', "")
            gml_str = ET.tostring(geom_elem, encoding="unicode", with_tail=False)
            geom = ogr.CreateGeometryFromGML(gml_str)

            if geom and geom.IsValid():
                qgs_geom = QgsGeometry.fromWkt(geom.ExportToWkt())
                if qgs_geom:
                    geom_type = self._get_geometry_type(qgs_geom)
                    if geom_type:
                        return qgs_geom, gml_id, geom_type
        except Exception as e:
            logger.error(f"Error processing geometry: {e}")
        return None

    def process_geometries(
        self, element: ET.Element
    ) -> Generator[Tuple[QgsGeometry, str, str], None, None]:
        """
        Generátor pro zpracování geometrií - umožňuje postupné zpracování bez načtení všech do paměti.

        Args:
            element: XML element obsahující geometrie

        Yields:
            Tuple obsahující (QgsGeometry, gml_id, typ_geometrie)
        """
        if element is None:
            return

        geom_elems = element.findall(".//*[@gml:id]", self.ns)
        for geom_elem in geom_elems:
            gml_id = geom_elem.get(f'{{{self.ns["gml"]}}}id')

            # Pokud je geometrie již v cache, vrátí se z ní
            if gml_id in self._geom_cache:
                yield self._geom_cache[gml_id]
                continue

            # Zpracování geometrie
            result = self._parse_geometry(geom_elem)
            if result:
                self._geom_cache[gml_id] = result
                yield result
