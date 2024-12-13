from typing import Dict, List, Optional
import lxml.etree as ET
from qgis.core import QgsVectorLayer, QgsField
from PyQt5.QtCore import QVariant
import logging

logger = logging.getLogger(__name__)

class AttributeProcessor:
    def __init__(self, schema_doc: dict, value_mappings: dict):
        self.schema_documentation = schema_doc
        self.value_mappings = value_mappings
        self._field_cache: Dict[str, List[QgsField]] = {}
        self._xpath_cache: Dict[str, ET.XPath] = {}

    def create_fields(self, layer: QgsVectorLayer, element: ET.Element) -> None:
        cache_key = layer.name()
        if cache_key in self._field_cache:
            provider = layer.dataProvider()
            provider.addAttributes(self._field_cache[cache_key])
            layer.updateFields()
            return

        provider = layer.dataProvider()
        attributes = []
        seen_fields = set()
        
        # Přidáme pole pro GML ID
        attributes.append(QgsField("gml_id", QVariant.String))
        seen_fields.add("gml_id")
        
        # Najdeme AtributyObjektu
        root = ET.ElementTree(element)

        #print(ET.tostring(element, encoding='utf8'))
        #atributy = element.find("//*[local-name()='AtributyObjektu']//*[not(*)]/local-name()")
        atributy = root.xpath("//*[local-name()='AtributyObjektu']//*[not(*)]")
        if atributy is not None:
            for elem in atributy:
                field_name = elem.tag.replace("{atr}","")

                if field_name not in seen_fields and field_name != 'AtributyObjektu':
                    
                    qgsField = QgsField(field_name, QVariant.String)
                    qgsField.setAlias(self.schema_documentation.get(field_name, field_name))
                    attributes.append(qgsField)
                    seen_fields.add(field_name)

        self._field_cache[cache_key] = attributes
        provider.addAttributes(attributes)
        layer.updateFields()

    def get_attributes(self, element: ET.Element, layer: QgsVectorLayer) -> list:
        values = []
        fields = layer.fields()
        
        for field in fields:
            field_name = field.name()
            
            if field_name == 'gml_id':
                values.append(None)
                continue
                
            field.setAlias(self.schema_documentation.get(field_name, field_name))

            # Upravený XPath bez namespace
            if field_name not in self._xpath_cache:
                xpath = f".//*[local-name()='{field_name}']"
                self._xpath_cache[field_name] = ET.ETXPath(xpath)
            
            elem = self._xpath_cache[field_name](element)
            value = None
            
            if elem and elem[0].text:
                value = elem[0].text.strip()
                if field_name in self.value_mappings and value in self.value_mappings[field_name]:
                    value = self.value_mappings[field_name][value]
                    

            values.append(value)
                
        return values