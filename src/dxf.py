import os
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsMapLayer, QgsCoordinateReferenceSystem,
    QgsRectangle, QgsGradientColorRamp
)
from qgis.utils import iface
from qgis.PyQt.QtGui import QColor
import processing
import copy

def export_layers_to_dxf_with_inverted_grayscale(output_filename, selected_layers=None):
    """
    Exportuje viditelné vrstvy do DXF s invertovanými odstíny šedi.
    Poté upraví formát DXF z AC1015 na AC1021 a převede soubor do UTF-8.
    
    Args:
        output_filename (str): Cesta a název výstupního souboru (bez přípony)
        selected_layers (list): Seznam názvů vrstev k exportu (None = všechny viditelné)
    """
    
    # Odvodit výstupní adresář z output_filename
    output_dir = os.path.dirname(output_filename)
    if not output_dir:
        output_dir = os.getcwd()
        output_filename = os.path.join(output_dir, output_filename)
    
    # Vytvoření output adresáře, pokud neexistuje
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Získání projektu
    project = QgsProject.instance()
    
    # Určení, které vrstvy budou exportovány
    layers_to_export = []
    if selected_layers:
        # Export jen specifikovaných vrstev
        for layer_name in selected_layers:
            layers = project.mapLayersByName(layer_name)
            if layers:
                layers_to_export.append(layers[0])
    else:
        # Export všech viditelných vrstev
        root = project.layerTreeRoot()
        for layer in root.findLayers():
            if layer.isVisible():
                layers_to_export.append(layer.layer())
    
    if not layers_to_export:
        print("Žádné vrstvy ke exportu!")
        return False
    
    print(f"Nalezeno {len(layers_to_export)} vrstev k exportu.")
    
    # Filtrujeme jen vektorové vrstvy
    vector_layers = [layer for layer in layers_to_export if layer.type() == QgsMapLayer.VectorLayer]
    
    if not vector_layers:
        print("Žádné vektorové vrstvy ke zpracování!")
        return False
    
    # Uložení původních rendererů a barev
    original_renderers = {}
    for layer in vector_layers:
        original_renderers[layer.id()] = layer.renderer().clone()
    
    # Funkce pro kontrolu, zda je barva odstínem šedi
    def je_odstin_sedi(barva):
        # Barva je odstín šedi, pokud R=G=B
        return barva.red() == barva.green() == barva.blue()
    
    # Funkce pro invertování barvy
    def invertuj_barvu(barva):
        if je_odstin_sedi(barva):
            # Pro odstíny šedi, invertujeme hodnotu (255 - hodnota)
            hodnota = 255 - barva.red()
            return QColor(hodnota, hodnota, hodnota)
        else:
            # Pro barevné ponecháme původní barvu
            return barva
    
    # Invertovat odstíny šedi na vrstvách
    for layer in vector_layers:
        if layer.isValid():
            print(f"Zpracovavam vrstvu: {layer.name()}")
            
            renderer = layer.renderer()
            
            # Zpracování podle typu rendereru
            if renderer.type() == "singleSymbol":
                # Jednoduchý symbol
                symbol = renderer.symbol()
                for i in range(symbol.symbolLayerCount()):
                    symbolLayer = symbol.symbolLayer(i)
                    if hasattr(symbolLayer, 'color') and hasattr(symbolLayer, 'setColor'):
                        barva = symbolLayer.color()
                        symbolLayer.setColor(invertuj_barvu(barva))
                    if hasattr(symbolLayer, 'fillColor') and hasattr(symbolLayer, 'setFillColor'):
                        barva = symbolLayer.fillColor()
                        symbolLayer.setFillColor(invertuj_barvu(barva))
            
            elif renderer.type() == "categorizedSymbol":
                # Kategorizovaný symbol
                for category in renderer.categories():
                    symbol = category.symbol()
                    for i in range(symbol.symbolLayerCount()):
                        symbolLayer = symbol.symbolLayer(i)
                        if hasattr(symbolLayer, 'color') and hasattr(symbolLayer, 'setColor'):
                            barva = symbolLayer.color()
                            symbolLayer.setColor(invertuj_barvu(barva))
                        if hasattr(symbolLayer, 'fillColor') and hasattr(symbolLayer, 'setFillColor'):
                            barva = symbolLayer.fillColor()
                            symbolLayer.setFillColor(invertuj_barvu(barva))
            
            elif renderer.type() == "graduatedSymbol":
                # Odstupňovaný symbol
                for range2 in renderer.ranges():
                    symbol = range2.symbol()
                    for i in range(symbol.symbolLayerCount()):
                        symbolLayer = symbol.symbolLayer(i)
                        if hasattr(symbolLayer, 'color') and hasattr(symbolLayer, 'setColor'):
                            barva = symbolLayer.color()
                            symbolLayer.setColor(invertuj_barvu(barva))
                        if hasattr(symbolLayer, 'fillColor') and hasattr(symbolLayer, 'setFillColor'):
                            barva = symbolLayer.fillColor()
                            symbolLayer.setFillColor(invertuj_barvu(barva))
            
            elif renderer.type() == "RuleRenderer" or renderer.type() == "ruleBasedRenderer":
                # Rule-based renderer
                root_rule = renderer.rootRule()
                for rule in root_rule.children():
                    symbol = rule.symbol()
                    for i in range(symbol.symbolLayerCount()):
                        symbolLayer = symbol.symbolLayer(i)
                        if hasattr(symbolLayer, 'color') and hasattr(symbolLayer, 'setColor'):
                            barva = symbolLayer.color()
                            symbolLayer.setColor(invertuj_barvu(barva))
                        if hasattr(symbolLayer, 'fillColor') and hasattr(symbolLayer, 'setFillColor'):
                            barva = symbolLayer.fillColor()
                            symbolLayer.setFillColor(invertuj_barvu(barva))
            
            elif renderer.type() == "heatmapRenderer":
                # Heatmap renderer - zkontrolujeme, zda používá odstíny šedi
                color_ramp = renderer.colorRamp()
                if isinstance(color_ramp, QgsGradientColorRamp):
                    start_color = color_ramp.color1()
                    end_color = color_ramp.color2()
                    
                    if je_odstin_sedi(start_color) and je_odstin_sedi(end_color):
                        # Pokud oba koncové body jsou odstíny šedi, invertujeme je
                        novy_start = invertuj_barvu(start_color)
                        novy_konec = invertuj_barvu(end_color)
                        renderer.setColorRamp(QgsGradientColorRamp(novy_start, novy_konec))
            
            elif renderer.type() == "pointDisplacement" or renderer.type() == "pointCluster":
                # Point displacement nebo cluster renderer
                symbol = renderer.symbol()
                for i in range(symbol.symbolLayerCount()):
                    symbolLayer = symbol.symbolLayer(i)
                    if hasattr(symbolLayer, 'color') and hasattr(symbolLayer, 'setColor'):
                        barva = symbolLayer.color()
                        symbolLayer.setColor(invertuj_barvu(barva))
                    if hasattr(symbolLayer, 'fillColor') and hasattr(symbolLayer, 'setFillColor'):
                        barva = symbolLayer.fillColor()
                        symbolLayer.setFillColor(invertuj_barvu(barva))
                        
                # Také změnit barvu jednotlivých symbolů v clusteru
                if hasattr(renderer, 'clusterSymbol'):
                    clusterSymbol = renderer.clusterSymbol()
                    for i in range(clusterSymbol.symbolLayerCount()):
                        symbolLayer = clusterSymbol.symbolLayer(i)
                        if hasattr(symbolLayer, 'color') and hasattr(symbolLayer, 'setColor'):
                            barva = symbolLayer.color()
                            symbolLayer.setColor(invertuj_barvu(barva))
                        if hasattr(symbolLayer, 'fillColor') and hasattr(symbolLayer, 'setFillColor'):
                            barva = symbolLayer.fillColor()
                            symbolLayer.setFillColor(invertuj_barvu(barva))
            
            # Pro ostatní typy rendererů - pokus o získání a změnu symbolu
            else:
                try:
                    if hasattr(renderer, 'symbol'):
                        symbol = renderer.symbol()
                        for i in range(symbol.symbolLayerCount()):
                            symbolLayer = symbol.symbolLayer(i)
                            if hasattr(symbolLayer, 'color') and hasattr(symbolLayer, 'setColor'):
                                barva = symbolLayer.color()
                                symbolLayer.setColor(invertuj_barvu(barva))
                            if hasattr(symbolLayer, 'fillColor') and hasattr(symbolLayer, 'setFillColor'):
                                barva = symbolLayer.fillColor()
                                symbolLayer.setFillColor(invertuj_barvu(barva))
                except:
                    print(f"  - Nelze nastavit barvu pro renderer typu {renderer.type()}")
            
            # Aktualizace vrstvy
            layer.triggerRepaint()
    
    # Obnovení plátna
    iface.mapCanvas().refresh()
    
    print("Inverze šedých barev dokončena. Zahajuji export...")
    
    # DXF soubor
    output_dxf = output_filename + ".dxf"
    
    # Odstranění existujícího souboru, pokud existuje
    if os.path.exists(output_dxf):
        os.remove(output_dxf)
   
    layer_crs = QgsCoordinateReferenceSystem("EPSG:5514")
    if layer_crs.isValid():
        print("CRS Description: {}".format(layer_crs.description()))
        print("CRS PROJ text: {}".format(layer_crs.toProj()))
    else:
        print("Invalid CRS!")
    
    parameters = {
        'LAYERS': [],
        'SYMBOLOGY_MODE': 2,
        'OUTPUT': output_dxf,
        'SYMBOLOGY_EXPORT': 2,  # Bez symbologie pro BYLAYER barvy
        'ENCODING': 'cp1250',  # Explicitní nastavení kódování
        'CRS': layer_crs,
        'FORCE_2D': False,
        'SYMBOLOGY_SCALE': 500,  # Přidáno nastavení měřítka symbologie
        
    }
    
    layer_params = []
    for layer in vector_layers:
        if layer.isValid():
            # Create proper layer parameter structure
            layer_param = {
                'layer': layer.source(),
                'attributeIndex': -1,  # No splitting by attribute
                'overriddenLayerName': '',  # Use original layer name
                'buildDataDefinedBlocks': False,
                'dataDefinedBlocksMaximumNumberOfClasses': -1
            }
            print(f"Přidávám vrstvu: {layer.name()}, source: {layer.source()}")
            layer_params.append(layer_param)
        else:
            print(f"Neplatná vrstva: {layer.name()}")
    
    # Set the properly structured LAYERS parameter
    parameters['LAYERS'] = layer_params
    parameters['USE_LAYER_COLORS'] = True       # Use layer colors instead of feature colors
    parameters['LAYERED_EXPORT'] = True         # Export objects on separate layers
    parameters['EXPORT_STYLES_FOR_LAYERS'] = True  # Export QGIS styles
    
    export_success = False
    try:
        result = processing.run("native:dxfexport", parameters)
        print(f"Export dokončen: {result}")
        
        # Ověřte, zda soubor existuje
        if os.path.exists(output_dxf):
            print(f"Soubor existuje na cestě: {output_dxf}")
            print(f"Velikost souboru: {os.path.getsize(output_dxf)} bytů")
            export_success = True
            
            # Upravíme DXF soubor - změníme AC1015 na AC1021 a převedeme do UTF-8
            print("Modifikuji DXF soubor - změna AC1015 na AC1021 a konverze do UTF-8...")
            
            try:
                # Nejprve načteme obsah souboru
                with open(output_dxf, 'rb') as f:
                    content = f.read()
                
                # Konverze do UTF-8 pokud soubor není v UTF-8
                try:
                    # Zkusíme dekódovat jako cp1250 (původní kódování)
                    decoded_content = content.decode('cp1250')
                    # Nahradíme AC1015 za AC1021
                    modified_content = decoded_content.replace('AC1015', 'AC1021')
                    # Uložíme v UTF-8
                    with open(output_dxf, 'w', encoding='utf-8') as f:
                        f.write(modified_content)
                    print("Soubor úspěšně převeden do UTF-8 a aktualizován na AC1021")

                except UnicodeDecodeError:
                    # Pokud ani to nejde, zkusíme poslední možnost - přímou binární náhradu
                    modified_content = content.replace(b'AC1015', b'AC1021')
                    with open(output_dxf, 'wb') as f:
                        f.write(modified_content)
                    print("Binární nahrazení AC1015 na AC1021 provedeno, ale konverze do UTF-8 se nezdařila.")
            except Exception as e:
                print(f"Chyba při úpravě DXF souboru: {str(e)}")
        else:
            print(f"Soubor NEBYL vytvořen na cestě: {output_dxf}")
    except Exception as e:
        print(f"Došlo k chybě během exportu: {str(e)}")
    
    # Obnovení původních rendererů
    print("Obnovuji původní barvy vrstev...")
    for layer in vector_layers:
        if layer.id() in original_renderers:
            layer.setRenderer(original_renderers[layer.id()])
            layer.triggerRepaint()
    
    # Obnovení plátna
    iface.mapCanvas().refresh()
    
    if export_success:
        print("Export úspěšně dokončen a původní barvy vrstev obnoveny.")
        return True
    else:
        print("Export se nezdařil, ale původní barvy vrstev byly obnoveny.")
        return False