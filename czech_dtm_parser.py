from typing import Dict, List, Tuple, Optional, Generator
from dataclasses import dataclass
from collections import defaultdict
from pathlib import Path
import logging
import json
import pandas as pd
from lxml import etree as ET
from osgeo import ogr
import threading


from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsField, 
    QgsProject, QgsCoordinateReferenceSystem,
    QgsSymbol, QgsLineSymbol, QgsMarkerSymbol, QgsFillSymbol,
    QgsSymbolLayer, QgsSimpleLineSymbolLayer, QgsGroupLayer,
    QgsLayerTreeGroup, QgsLayerTreeNode, QgsSimpleFillSymbolLayer,
    QgsSimpleMarkerSymbolLayer, QgsSvgMarkerSymbolLayer, QgsWkbTypes,
    QgsSimpleMarkerSymbolLayerBase, QgsRuleBasedRenderer, QgsMapLayer
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, QPointF, QVariant
from PyQt5.QtWidgets import QProgressDialog, QApplication

# Import našich tříd ze samostatných souborů
from .style_manager import StyleManager
from .geometry_processor import GeometryProcessor
from .attribute_processor import AttributeProcessor
from .batch_processor import BatchFeatureProcessor
from .symbol_processor import SymbolProcessor
logger = logging.getLogger(__name__)

@dataclass
class ScaleRange:
    """Represents a scale range with minimum and maximum values."""
    min_scale: int
    max_scale: int
    
    def __str__(self) -> str:
        if self.min_scale == 0:
            return f"0 - 1:{self.max_scale}"
        return f"1:{self.min_scale} - 1:{self.max_scale}"

class CzechDTMParser:
    """Parser pro zpracování Czech Digital Terrain Model (DTM) dat."""
    
    def __init__(self, iface):
        """
        Inicializace parseru.
        
        Args:
            iface: QGIS rozhraní
        """
        self._group_cache = {}  # Cache pro skupiny

        self.iface = iface
        
        # Inicializace pomocných tříd
        self.style_manager = StyleManager()
        self.geom_processor = GeometryProcessor()
        self.feature_processor = BatchFeatureProcessor()
        self.symbol_processor = SymbolProcessor()
        
        # Definice rozsahů měřítek
        self.scale_ranges = {
            '500': ScaleRange(0, 500),
            '5000': ScaleRange(501, 5000),
            '10000': ScaleRange(5001, 10000),
            '25000': ScaleRange(10001, 25000)
        }

        # XML namespaces
        self.ns = {
            'objtyp': 'objtyp',
            'gml': 'http://www.opengis.net/gml/3.2',
            'dopinf': 'dopinf',
            'trdpvs': 'trdpvs',
            'trdpes': 'trdpes',
            'atr': 'atr',
            'cmn': 'cmn',
            'x': '*',
            'xs': 'http://www.w3.org/2001/XMLSchema',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }
        
        # Konfigurace vrstev
        self.layer_configs = {
            "01": "Point",
            "02": "LineString",
            "03": "Polygon",
            "04": "DB",
        }

        # Načtení konfigurace
        self._load_configurations()

    def _load_configurations(self):
        """Načtení všech potřebných konfigurací"""
        try:
            self.schema_documentation = self.load_schema_documentation()
            self.value_mappings = self.load_enum_mappings()
            self.type_mapping_df = self.load_type_mapping()
            self.attr_processor = AttributeProcessor(self.schema_documentation, self.value_mappings)
        except Exception as e:
            logger.error(f"Error loading configurations: {e}")
            raise

    def load_type_mapping(self) -> Optional[pd.DataFrame]:
        """
        Načte mapování typů z CSV souboru.
        
        Returns:
            DataFrame s mapováním typů nebo None při chybě
        """
        try:
            df = pd.read_csv(
                self._resolve_path('typy_druhy.csv'),
                delimiter='|',
                encoding='utf-8',
                names=['code', 'attributes'],
                dtype=str
            )
            df['code'] = df['code'].str.strip()
            df['attributes'] = df['attributes'].str.split(';')
            return df
        except Exception as e:
            logger.error(f"Error loading type mapping: {e}")
            return None

    def _resolve_path(self, name: str, basepath: Optional[str] = None) -> str:
        """
        Vyřeší cestu k souboru relativně k umístění skriptu.
        
        Args:
            name: Název souboru
            basepath: Základní cesta (výchozí je adresář skriptu)
            
        Returns:
            str: Absolutní cesta k souboru
        """
        if not basepath:
            basepath = Path(__file__).parent
        return str(Path(basepath) / name)

    def create_group(self, group_name: str, parent=None):
        thread_id = threading.get_ident()
        #print(f"Creating group '{group_name}' in thread {thread_id}")
        
        if parent is None:
            parent = QgsProject.instance().layerTreeRoot()
            #print(f"Using root as parent in thread {thread_id}")
        
        existing_group = parent.findGroup(group_name)
        if existing_group:
            #print(f"Found existing group '{group_name}' in thread {thread_id}")
            return existing_group
                
        #print(f"Creating new group '{group_name}' in thread {thread_id}")
        return parent.addGroup(group_name)

    
    def parse_file(self, filename: str) -> Tuple[bool, str]:
        """
        Hlavní metoda pro parsování DTM souboru.
        
        Args:
            filename: Cesta k souboru pro zpracování
            
        Returns:
            Tuple[bool, str]: (úspěch, zpráva)
        """
        try:
            # Načtení stylů pokud ještě nejsou
            if not self.style_manager._initialized:
                self.style_manager.load_styles(self._resolve_path("styles2.csv"))

            # Parsování XML pomocí iterparse pro efektivní zpracování velkých souborů
            context = ET.iterparse(filename, events=('end',), 
                                 tag=f'{{{self.ns["objtyp"]}}}DataJVFDTM')

            for event, elem in context:
                try:
                    # Zpracování datového elementu
                    processed_count = self._process_data_element(elem)
                    
                    # Vyčištění paměti
                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]
                        
                except Exception as e:
                    logger.error(f"Chyba při zpracování elementu: {e}")
                    continue

            return True, "Data byla úspěšně načtena"

        except Exception as e:
            logger.error(f"Chyba při parsování souboru: {e}", exc_info=True)
            return False, f"Chyba při parsování: {str(e)}"
    
    def _on_processing_finished(self, progress_dialog, success, message):
        """Handler for processing completion"""
        progress_dialog.close()
        if success:
            self.iface.messageBar().pushSuccess("DTM Parser", message)
        else:
            self.iface.messageBar().pushWarning("DTM Parser", message)

    def _process_data_element(self, root_elem: ET.Element) -> int:
        """Zpracování hlavního datového elementu"""
        processed_count = 0
        
        # Získání a seřazení datových objektů
        data_objects = root_elem.findall('./objtyp:Data/*', self.ns)
        data_objects.sort(key=lambda x: x.find('x:ObjektovyTypNazev', self.ns).get('code_base')
                         if x.find('x:ObjektovyTypNazev', self.ns) is not None else '')

        for data_obj in data_objects:
            try:
                processed_count += self._process_data_object(data_obj)
            except Exception as e:
                logger.error(f"Error processing data object: {e}")
                continue

        return processed_count

    def _process_data_object(self, data_obj: ET.Element) -> int:
        """Zpracování jednotlivého datového objektu"""
        obj_type = data_obj.find('x:ObjektovyTypNazev', self.ns)
        if obj_type is None:
            return 0

        # Získání kódů a názvů
        code_num = obj_type.get('code_base')[7:]
        code_suffix = obj_type.get('code_suffix')
        config_type = self.layer_configs.get(code_suffix, "")

        # Vytvoření struktury skupin
        groups = self._create_group_structure(data_obj)
        
        # Zpracování záznamů
        records = data_obj.findall('x:ZaznamyObjektu/x:ZaznamObjektu', self.ns)
        if not records:
            return 0

        return self._process_records(records, obj_type, code_num, config_type, groups)

    def _process_records(self, records: List[ET.Element], obj_type: ET.Element, 
                        code_num: str, config_type: str, groups: Dict[str, QgsLayerTreeGroup]) -> int:
        """Zpracování záznamů objektů"""
        type_features = defaultdict(lambda: {
            'features': [],
            'scale_features': [],
            'first_element': None,
            'tag_name': None,
            'type_value': None,
            'geom_type': None,
            'second_geom_type': None,
            'has_second_geom': False
        })
        #print(f"\nProcessing records for: {code_num} {obj_type.text}")

        processed_count = 0
        for record in records:
            try:
                processed_count += self._process_single_record(record, obj_type, code_num, type_features)
            except Exception as e:
                logger.error(f"Error processing record: {e}")
                continue
            
        #print(f"Found {len(type_features)} different types:")

        # Vytvoření vrstev pro každý typ
        self._create_layers_for_types(type_features, obj_type, config_type, groups)

        return processed_count

    def _process_single_record(self, record: ET.Element, obj_type: ET.Element, 
                             code_num: str, type_features: dict) -> int:
        """Zpracování jednotlivého záznamu"""
        # Získání typu a atributů
        attributes = record.find("x:AtributyObjektu", self.ns)
        record_type, tag_name = self._determine_record_type(attributes, code_num, obj_type.text)

        # Zpracování geometrií
        geom_list = list(self.geom_processor.process_geometries(record.find('x:GeometrieObjektu', self.ns)))

        if not geom_list:
            return 0

        # Uložení dat do type_features
        return self._store_geometries(geom_list, record, record_type, tag_name, type_features)

    def _determine_record_type(self, attributes: ET.Element, code_num: str, obj_type_text: str) -> Tuple[Optional[str], Optional[str]]:
        """Určení typu záznamu"""
        if attributes is None or self.type_mapping_df is None:
            return None, None

        tag_name = None
        record_type = None

        mapping_row = self.type_mapping_df[self.type_mapping_df['code'] == f"{code_num} {obj_type_text}"]
        if not mapping_row.empty:
            expected_attributes = mapping_row.iloc[0]['attributes']
            for expected_attribute in expected_attributes:
                for child in attributes:
                    current_tag = child.tag.split('}')[-1]
                    
                    if current_tag == expected_attribute and child.text != '0':
                        if record_type is None:
                            record_type = self.value_mappings[current_tag][child.text]
                            tag_name = current_tag
                        else:
                            record_type = f"{record_type} {self.value_mappings[current_tag][child.text]}"
                        break

        return record_type, tag_name

    def _store_geometries(self, geom_list: List[Tuple[QgsGeometry, str, str]], 
                         record: ET.Element, record_type: Optional[str], 
                         tag_name: Optional[str], type_features: dict) -> int:
        """Uložení geometrií do type_features"""
        if len(geom_list) == 2:
            first_geom = geom_list[0]
            second_geom = geom_list[1]
            
            type_key = (f"{tag_name}_{record_type}_{first_geom[2]}" 
                       if tag_name and record_type 
                       else f"{tag_name}_{first_geom[2]}")
            
            features_dict = type_features[type_key]
            if not features_dict['first_element']:
                features_dict.update({
                    'first_element': record,
                    'tag_name': tag_name,
                    'type_value': record_type,
                    'geom_type': first_geom[2],
                    'second_geom_type': second_geom[2],
                    'has_second_geom': True
                })
            
            features_dict['scale_features'].append((record, first_geom[0], first_geom[1]))
            features_dict['features'].append((record, second_geom[0], second_geom[1]))
            return 1

        elif len(geom_list) == 1:
            geom, gml_id, geom_type = geom_list[0]
            type_key = (f"{tag_name}_{record_type}_{geom_type}" 
                       if tag_name and record_type 
                       else f"{tag_name}_{geom_type}")
            
            features_dict = type_features[type_key]
            if not features_dict['first_element']:
                features_dict.update({
                    'first_element': record,
                    'tag_name': tag_name,
                    'type_value': record_type,
                    'geom_type': geom_type,
                    'has_second_geom': False
                })
            
            features_dict['scale_features'].append((record, geom, gml_id))
            return 1

        return 0

    def _create_layers_for_types(self, type_features: dict, obj_type: ET.Element, 
                               config_type: str, groups: Dict[str, QgsLayerTreeGroup]):
        """Vytvoření vrstev pro všechny typy"""
        #print(f"\nCreating layers for {len(type_features)} types")

        for type_key, data in type_features.items():
            """
            print(f"\nProcessing type: {type_key}")
            print(f"Tag name: {data['tag_name']}")
            print(f"Type value: {data['type_value']}")
            print(f"Geom type: {data['geom_type']}")
            """
            try:
                self._create_type_layers(type_key, data, obj_type, config_type, groups)
            except Exception as e:
                logger.error(f"Error creating layers for type {type_key}: {e}")
                print(f"Full error details: {str(e)}")

                continue

    def _create_type_layers(self, type_key: str, data: dict, obj_type: ET.Element, 
                        config_type: str, groups: Dict[str, QgsLayerTreeGroup]):
        """
        Vytvoření vrstev pro konkrétní typ.
        
        Args:
            type_key: Klíč typu
            data: Data pro vytvoření vrstev
            obj_type: Typ objektu
            config_type: Typ konfigurace
            groups: Slovník skupin pro organizaci vrstev
        """
        # Vytvoření základního názvu vrstvy
        code_num = obj_type.get('code_base')[7:]
        base_layer_name = f"{code_num} {obj_type.text}_{data['geom_type']}"

        base_layer_name1 = self._get_layer_name(obj_type, data['tag_name'], data['type_value'])
        base_layer_name2 = base_layer_name1 +"_" +  data['geom_type']

        layer_name = f"{base_layer_name1}_{config_type}"

        scale_layer = self._create_scale_layer(base_layer_name,base_layer_name2,layer_name,  data)

        #base_layer_name2 = base_layer_name + "_" + data['geom_type']
        
        second_geom_layer = None
        
        if (data['has_second_geom']) :
            base_layer_name3 = base_layer_name1 +"_" +  data['second_geom_type']
            second_geom_layer = self._create_vector_layer(data['second_geom_type'], base_layer_name3)
            # Přidání atributů a features
            self.attr_processor.create_fields(second_geom_layer, data['first_element'])
            self.feature_processor.process_features(  self._create_features(second_geom_layer, data['features']),     second_geom_layer  )
       
    
        self._add_layers_to_groups(second_geom_layer, scale_layer, layer_name, groups)

        

    def _create_vector_layer(self, geom_type: str, name: str) -> Optional[QgsVectorLayer]:
        """
        Vytvoření vektorové vrstvy.
        
        Args:
            geom_type: Typ geometrie
            name: Název vrstvy
            
        Returns:
            QgsVectorLayer nebo None při chybě
        """
        layer = QgsVectorLayer(f"{geom_type}?crs=EPSG:5514", name, "memory")
        if not layer.isValid():
            logger.error(f"Error creating layer: {name}")
            return None
        return layer

    def _create_scale_layer(self, base_name: str, base_name2: str, layer_name: str, data: dict) -> Optional[QgsVectorLayer]:
        """
        Vytvoření vrstvy pro měřítkové styly.
        """
        scale_layer = self._create_vector_layer(data['geom_type'], layer_name)
        if not scale_layer:
            #print("not scale_layer")
            return None

        self.attr_processor.create_fields(scale_layer, data['first_element'])
        self.feature_processor.process_features(  self._create_features(scale_layer, data['scale_features']),     scale_layer  )
        #print(f"Scale layer feature count after adding: {scale_layer.featureCount()}")

        # Nastavíme renderer před vrácením vrstvy
        renderer = self._create_scale_based_renderer(scale_layer, base_name, base_name2)
        if renderer:
            #print(f"Created renderer with {len(renderer.rootRule().children())} rules")
            scale_layer.setRenderer(renderer)
       
        return scale_layer

    def _create_features(self, layer: QgsVectorLayer, 
                        feature_data: List[Tuple[ET.Element, QgsGeometry, str]]) -> List[QgsFeature]:
        
        features = []
        for elem, geom, gml_id in feature_data:
            feat = QgsFeature(layer.fields())
            attributes = self.attr_processor.get_attributes(elem, layer)
            attributes[0] = gml_id
            feat.setAttributes(attributes)
            feat.setGeometry(geom)
            features.append(feat)
        
        return features

    def _add_layers_to_groups(self, second_geom_layer: QgsVectorLayer, scale_layer: QgsVectorLayer, 
                                base_name: str, groups: Dict[str, QgsLayerTreeGroup]):
        """
        Přidání vrstev do skupin.
        """
        # Pokud jsme ve skupině ZPS, nepřidávat další podskupinu ZPS
        parent_group = groups['skupina']
        
        if second_geom_layer:
            QgsProject.instance().addMapLayer(second_geom_layer, False)    
            tree_layer = parent_group.addLayer(second_geom_layer)
            tree_layer.setItemVisibilityChecked(False)
        
        QgsProject.instance().addMapLayer(scale_layer, False)
        parent_group.addLayer(scale_layer)


    def _create_group_structure(self, data_obj):
        thread_id = threading.get_ident()
        #print(f"Creating group structure in thread {thread_id}")
        
        root = QgsProject.instance().layerTreeRoot()
        
        obsahova_cast = data_obj.find('x:ObsahovaCast', self.ns).text
        kategorie = data_obj.find('x:KategorieObjektu', self.ns).text
        skupina = data_obj.find('x:SkupinaObjektu', self.ns).text
        
        #print(f"Structure: {obsahova_cast} -> {kategorie} -> {skupina} in thread {thread_id}")
        
        obsahova_group = self.create_group(obsahova_cast, root)
        kategorie_group = self.create_group(kategorie, obsahova_group)
        skupina_group = self.create_group(skupina, kategorie_group)
        
        return {
            'obsah': obsahova_group,
            'kategorie': kategorie_group,
            'skupina': skupina_group
        }


    def _get_layer_name(self, obj_type: ET.Element, tag_name: Optional[str], type_value: Optional[str]) -> str:
        """
        Získání názvu vrstvy.
        
        Args:
            obj_type: Typ objektu
            tag_name: Název tagu
            type_value: Hodnota typu
            geom_type: Typ geometrie
            
        Returns:
            Název vrstvy
        """
        code_num = obj_type.get('code_base')[7:]
        base_name = f"{code_num} {obj_type.text}"
        
        if tag_name and type_value and tag_name in self.value_mappings:
            return f"{base_name} - {type_value}"
        
        # Zkusíme najít výchozí typ pro tento objekt
        default_type = None
        if tag_name in self.value_mappings:
            # Hledáme výchozí hodnotu (často '0' nebo podobné)
            default_mapping = self.value_mappings.get(tag_name, {})
            if '0' in default_mapping:
                default_type = default_mapping['0']
            elif '99' in default_mapping:  # někdy se používá 99 pro výchozí hodnotu
                default_type = default_mapping['99']
        
        if default_type:
            return f"{base_name} - {default_type}"
            
        return f"{base_name}"

    def _create_scale_based_renderer(self, layer: QgsVectorLayer, base_layer_name: str, base_layer_name2: str) -> QgsRuleBasedRenderer:
        """Vytvoří renderer s pravidly pro různá měřítka"""
        #print(f"\nCreating renderer for layer: {layer.name()}")
        #print(f"Base layer name: {base_layer_name}")
        
        # Získáme typ geometrie z vrstvy
        """        geom_type = {
                0: "Point",         # QgsWkbTypes.Point
                1: "LineString",    # QgsWkbTypes.Line
                2: "Polygon"        # QgsWkbTypes.Polygon
            }.get(layer.geometryType())
            
        if not geom_type:
            print(f"Unknown geometry type: {layer.geometryType()}")
            return None
        """
        rules = []
        #print("\n")

        for scale, scale_range in self.scale_ranges.items():
            min_scale = scale_range.min_scale
            max_scale = scale_range.max_scale
            
            meritkovy_rozsah = None
            if min_scale == 0:
                meritkovy_rozsah = f"0 - 1:{max_scale}"
            else:
                meritkovy_rozsah = f"1:{min_scale} - 1:{max_scale}"

            # Přidáme typ geometrie do klíče
            style_key = f"{base_layer_name2}_{scale}"
            #print(f"Looking for style with key 1: {style_key}")
            
            style_found = False
            if style_key in self.style_manager._style_df['key'].values:
                # print(f"Found direct match for style: {style_key}")
                style_row = self.style_manager._style_df[self.style_manager._style_df['key'] == style_key].iloc[0]
                style_found = True
            else:
                # Pokud obsahuje "nezjištěno/neurčeno", zkusíme varianty
                if "nezjištěno/neurčeno" in style_key:
                    # Zkusíme variantu s "nezjištěno"
                    style_key_nezjisteno = style_key.replace("nezjištěno/neurčeno", "nezjištěno")
                    #print(f"Looking for style with key 2: {style_key_nezjisteno}")
                    if style_key_nezjisteno in self.style_manager._style_df['key'].values:
                        style_row = self.style_manager._style_df[self.style_manager._style_df['key'] == style_key_nezjisteno].iloc[0]
                        style_found = True
                    else:
                        # Zkusíme variantu s "neurčeno"
                        style_key_neurceno = style_key.replace("nezjištěno/neurčeno", "neurčeno")
                        #print(f"Looking for style with key 3: {style_key_neurceno}")

                        if style_key_neurceno in self.style_manager._style_df['key'].values:
                            style_row = self.style_manager._style_df[self.style_manager._style_df['key'] == style_key_neurceno].iloc[0]
                            style_found = True
                
                # Pokud stále nemáme styl, zkusíme verzi bez typu
                if not style_found:

                    style_key_without_type = f"{base_layer_name}_{scale}"
                    #print(f"Looking for style with key 4: {style_key_without_type}")

                    if style_key_without_type in self.style_manager._style_df['key'].values:
                        style_row = self.style_manager._style_df[self.style_manager._style_df['key'] == style_key_without_type].iloc[0]
                        style_found = True
                                
            if style_found:
                #print(f"Creating rule for scale {scale}")
                qgis_symbol_json = style_row.get('qgis_symbol')
                if qgis_symbol_json:
                    symbol_dict = json.loads(qgis_symbol_json)
                    symbol = self.symbol_processor.create_symbol_from_json(symbol_dict)
                    if symbol:
                        rule = QgsRuleBasedRenderer.Rule(symbol)
                        rule.setMinimumScale(max_scale)
                        rule.setMaximumScale(min_scale)
                        rule.setLabel(meritkovy_rozsah)
                        rule.setDescription(meritkovy_rozsah)
                        rules.append(rule)
                        #print(f"Rule created successfully")
                    else:
                        print("Failed to create symbol")
                else:
                    print("No symbol JSON found")

        root_rule = QgsRuleBasedRenderer.Rule(None)
        for rule in rules:
            root_rule.appendChild(rule)
        
        renderer = QgsRuleBasedRenderer(root_rule)
        if not renderer.rootRule().children():  # pokud renderer nemá žádná pravidla
            layer.setName(layer.name() + " (nenalezen styl)")
        
        #print(f"Created renderer with {len(rules)} rules")
        return renderer


    def load_schema_documentation(self) -> Dict[str, str]:
        """
        Načte dokumentaci schématu z XSD souboru.
        
        Returns:
            Slovník s dokumentací schématu
        """
        try:
            tree = ET.parse(self._resolve_path('xsd/common/atributy.xsd'))
            root = tree.getroot()
            
            schema_doc = {}
            for element in root.findall(".//xs:element", {'xs': 'http://www.w3.org/2001/XMLSchema'}):
                name = element.get('name')
                doc = element.find(".//xs:documentation", {'xs': 'http://www.w3.org/2001/XMLSchema'})
                if name and doc is not None:
                    schema_doc[name] = doc.text.strip()
                    
            return schema_doc
        except Exception as e:
            logger.error(f"Error loading XSD schema: {e}")
            return {}

    def load_enum_mappings(self) -> Dict[str, Dict[str, str]]:
        """
        Načte mapování hodnot výčtových typů.
        
        Returns:
            Slovník s mapováním hodnot
        """
        try:
            tree = ET.parse(self._resolve_path('xsd/common/atributy.xsd'))
            root = tree.getroot()
            
            mappings = {}
            for element in root.findall(".//xs:element", {'xs': 'http://www.w3.org/2001/XMLSchema'}):
                name = element.get('name')
                enum_values = {}
                
                for enum in element.findall(".//xs:enumeration", {'xs': 'http://www.w3.org/2001/XMLSchema'}):
                    value = enum.get('value')
                
                    doc = enum.find(".//xs:documentation", {'xs': 'http://www.w3.org/2001/XMLSchema'})
                    
                    
                    if doc is not None:
                        enum_values[value] = doc.text.strip()
                        #print (name, value, doc.text.strip)
                        
                if enum_values:
                    mappings[name] = enum_values
            
            return mappings
        except Exception as e:
            logger.error(f"Error loading enum mappings: {e}")
            return {}