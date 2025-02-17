"""
@brief XSD Schema Loader

Classes:
 - XSDSchemaLoader

(C) 2024-2025 by MapGeeks
@author Petr Barandovski petr.barandovski@gmail.com
@author Linda Karlovska linda.karlovska@seznam.cz

This plugin is free under the MIT License.
"""

import logging
from typing import Dict, Optional, List
import xml.etree.ElementTree as ET

from .helpers import resolve_path, load_config

logger = logging.getLogger(__name__)


class XSDSchemaLoader:
    """Třída pro načítání informací ze XSD schématu."""

    def __init__(self, xsd_file: Optional[str] = None):
        """
        Inicializace loaderu XSD schématu.

        Args:
            xsd_file (Optional[str]): Cesta ke XSD souboru. Pokud není nastavena, použije se hodnota z konfigurace.
        """
        config = load_config()
        self.xsd_file = xsd_file or config.get("xsd_attributes")
        if not self.xsd_file:
            raise ValueError(
                "Path to the XSD file must be provided or defined in the configuration."
            )

    def _get_root(self) -> ET.Element:
        """
        Načte a vrátí kořenový prvek XSD dokumentu.

        Returns:
            ET.Element: Kořenový prvek XML stromu.

        Raises:
            FileNotFoundError: Pokud není XSD soubor nalezen.
            ET.ParseError: Pokud dojde k chybě při parsování XML.
        """
        xsd_path = resolve_path(self.xsd_file)
        tree = ET.parse(xsd_path)
        return tree.getroot()

    def _get_elements(self) -> List[ET.Element]:
        """
        Najde všechny elementy v XSD schématu.

        Returns:
            List[ET.Element]: Seznam elementů nalezených v XSD.
        """
        root = self._get_root()
        return root.findall(".//xs:element", {"xs": "http://www.w3.org/2001/XMLSchema"})

    def load_schema_documentation(self) -> Dict[str, str]:
        """
        Načte dokumentaci schématu z XSD souboru.

        Returns:
            Dict[str, str]: Slovník s dokumentací schématu.
        """
        schema_doc = {}
        try:
            elements = self._get_elements()
            for element in elements:
                name = element.get("name")
                doc_elem = element.find(
                    ".//xs:documentation", {"xs": "http://www.w3.org/2001/XMLSchema"}
                )
                if name and doc_elem is not None and doc_elem.text:
                    schema_doc[name] = doc_elem.text.strip()
        except Exception as e:
            logger.error(f"Error loading XSD schema documentation: {e}")
        return schema_doc

    def load_enum_mappings(self) -> Dict[str, Dict[str, str]]:
        """
        Načte mapování hodnot výčtových typů.

        Returns:
            Dict[str, Dict[str, str]]: Slovník s mapováním hodnot.
        """
        mappings = {}
        try:
            elements = self._get_elements()
            for element in elements:
                name = element.get("name")
                enum_values = {}

                for enum in element.findall(
                    ".//xs:enumeration", {"xs": "http://www.w3.org/2001/XMLSchema"}
                ):
                    value = enum.get("value")
                    doc_elem = enum.find(
                        ".//xs:documentation",
                        {"xs": "http://www.w3.org/2001/XMLSchema"},
                    )
                    if value and doc_elem is not None and doc_elem.text:
                        enum_values[value] = doc_elem.text.strip()

                if name and enum_values:
                    mappings[name] = enum_values
        except Exception as e:
            logger.error(f"Error loading enum mappings: {e}")
        return mappings
