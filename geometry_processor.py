from typing import Dict, Tuple, Optional, Generator
import lxml.etree as ET
from qgis.core import QgsGeometry, QgsWkbTypes
from osgeo import ogr
import logging

logger = logging.getLogger(__name__)

class GeometryProcessor:
    """Třída pro efektivní zpracování geometrií"""
    
    def __init__(self):
        self._geom_cache: Dict[str, Tuple[QgsGeometry, str, str]] = {}
        self.ns = {
            'gml': 'http://www.opengis.net/gml/3.2',
            'x': '*'
        }

    def process_geometries(self, element: ET.Element) -> Generator[Tuple[QgsGeometry, str, str], None, None]:
        """
        Generátor pro zpracování geometrií - umožňuje postupné zpracování bez načtení všech do paměti.
        
        Args:
            element: XML element obsahující geometrie
            
        Yields:
            Tuple obsahující (QgsGeometry, gml_id, typ_geometrie)
        """
        if element is None:
            return
        
        geom_elems = element.findall('.//*[@gml:id]', self.ns)
        #print(f"Nalezeno elementů s gml:id: {len(geom_elems)}")
        for geom_elem in  geom_elems:
            

            gml_id = geom_elem.get(f'{{{self.ns["gml"]}}}id')
            
            # Kontrola cache
            if gml_id in self._geom_cache:
                yield self._geom_cache[gml_id]
                continue

            try:
                # Optimalizované parsování XML
                gml_str = ET.tostring(geom_elem, encoding='unicode', with_tail=False)
                geom = ogr.CreateGeometryFromGML(gml_str)
                
                if geom and geom.IsValid():
                    qgs_geom = QgsGeometry.fromWkt(geom.ExportToWkt())
                    if qgs_geom:
                        geom_type = self._get_geometry_type(qgs_geom)
                        if geom_type:
                            result = (qgs_geom, gml_id or '', geom_type)
                            self._geom_cache[gml_id] = result
                            yield result
            except Exception as e:
                logger.error(f"Error processing geometry {gml_id}: {e}")
                continue

    @staticmethod
    def _get_geometry_type(qgs_geom: QgsGeometry) -> Optional[str]:
        """
        Určí typ geometrie z QgsGeometry.
        
        Args:
            qgs_geom: QGIS geometrie
            
        Returns:
            Textový popis typu geometrie nebo None
        """
        wkb_type = qgs_geom.wkbType()
        
        # Použijeme dictionary místo if-elif řetězce pro lepší výkon
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
            QgsWkbTypes.MultiPolygonZ: "Polygon"
        }
        
        return type_mapping.get(wkb_type)