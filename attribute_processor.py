"""
@brief Processing of JVF (GML) attributes

Classes:
 - AttributeProcessor

(C) 2024-2025 by MapGeeks
@author Petr Barandovski petr.barandovski@gmail.com
@author Linda Karlovska linda.karlovska@seznam.cz

This plugin is free under the MIT License.
"""

import logging
from typing import Dict, List, Optional
import lxml.etree as ET

from qgis.core import QgsVectorLayer, QgsField
from PyQt5.QtCore import QVariant

from .schema_loader import XSDSchemaLoader

logger = logging.getLogger(__name__)


class AttributeProcessor:
    """Třída pro zpracování atributů z XML a jejich mapování na QGIS vrstvy."""

    def __init__(self):
        """
        Inicializace procesoru atributů.
        Načte dokumentaci a mapování hodnot ze schémat.
        """
        schema_loader = XSDSchemaLoader()
        self.schema_documentation = schema_loader.load_schema_documentation()
        self.value_mappings = schema_loader.load_enum_mappings()

        self._field_cache: Dict[str, List[QgsField]] = {}
        self._xpath_cache: Dict[str, ET.XPath] = {}

    def _apply_cached_fields(self, layer: QgsVectorLayer, cache_key: str) -> None:
        """
        Přidá atributy do vrstvy na základě cache.

        Args:
            layer (QgsVectorLayer): Cílová vrstva.
            cache_key (str): Klíč pro vyhledání v cache.
        """
        provider = layer.dataProvider()
        provider.addAttributes(self._field_cache[cache_key])
        layer.updateFields()

    def _generate_fields_from_element(self, element: ET.Element) -> List[QgsField]:
        """
        Generuje seznam QGIS atributů na základě XML elementu.

        Args:
            element (ET.Element): XML element.

        Returns:
            List[QgsField]: Seznam atributů pro vrstvu.
        """
        attributes = [QgsField("gml_id", QVariant.String)]
        seen_fields = {"gml_id"}

        root = ET.ElementTree(element)
        atributy = root.xpath("//*[local-name()='AtributyObjektu']//*[not(*)]")

        if atributy is not None:
            for elem in atributy:
                field_name = elem.tag.replace("{atr}", "")
                if field_name not in seen_fields and field_name != "AtributyObjektu":
                    qgs_field = QgsField(field_name, QVariant.String)
                    qgs_field.setAlias(
                        self.schema_documentation.get(field_name, field_name)
                    )
                    attributes.append(qgs_field)
                    seen_fields.add(field_name)

        return attributes

    def _extract_field_value(
        self, field_name: str, element: ET.Element
    ) -> Optional[str]:
        """
        Extrahuje hodnotu atributu z XML elementu podle názvu pole.

        Args:
            field_name (str): Název pole.
            element (ET.Element): XML element.

        Returns:
            Optional[str]: Hodnota atributu nebo `None`.
        """
        if field_name not in self._xpath_cache:
            xpath = f".//*[local-name()='{field_name}']"
            self._xpath_cache[field_name] = ET.ETXPath(xpath)

        elem = self._xpath_cache[field_name](element)
        if elem and elem[0].text:
            value = elem[0].text.strip()
            if (
                field_name in self.value_mappings
                and value in self.value_mappings[field_name]
            ):
                return self.value_mappings[field_name][value]
            return value

        return None

    def create_fields(self, layer: QgsVectorLayer, element: ET.Element) -> None:
        """
        Vytvoří a přidá atributy do vrstvy na základě XML elementu.

        Args:
            layer (QgsVectorLayer): QGIS vrstva, kam se přidají atributy.
            element (ET.Element): XML element obsahující definice atributů.
        """
        cache_key = layer.name()
        if cache_key in self._field_cache:
            self._apply_cached_fields(layer, cache_key)
            return

        attributes = self._generate_fields_from_element(element)
        self._field_cache[cache_key] = attributes

        self._apply_cached_fields(layer, cache_key)

    def get_attributes(
        self, element: ET.Element, layer: QgsVectorLayer
    ) -> List[Optional[str]]:
        """
        Extrahuje hodnoty atributů z XML elementu pro danou vrstvu.

        Args:
            element (ET.Element): XML element obsahující atributy.
            layer (QgsVectorLayer): Cílová QGIS vrstva.

        Returns:
            List[Optional[str]]: Seznam hodnot atributů odpovídajících polím vrstvy.
        """
        values = []
        fields = layer.fields()

        for field in fields:
            field_name = field.name()

            if field_name == "gml_id":
                values.append(None)
                continue

            field.setAlias(self.schema_documentation.get(field_name, field_name))
            value = self._extract_field_value(field_name, element)
            values.append(value)

        return values
