import os
from qgis.core import (
    Qgis, QgsProject, QgsVectorLayer, QgsLayerTreeGroup, QgsLayerTreeLayer,
    QgsCoordinateReferenceSystem, QgsVectorSimplifyMethod,
    QgsVectorLayerCache, QgsLayerTreeUtils
)
from qgis.utils import iface
import processing
import sqlite3

# Prefix názvu tabulky v GeoPackage: tab + ID vrstvy v projektu
TABLE_PREFIX = 'tab'


def _simplify_flags():
    """Příznaky zjednodušení vykreslování - QGIS 4 (Qgis.VectorRenderingSimplificationFlag) i QGIS 3."""
    try:
        f = Qgis.VectorRenderingSimplificationFlag
        return f.GeometrySimplification | f.AntialiasingSimplification
    except AttributeError:
        h = QgsVectorSimplifyMethod
        return QgsVectorSimplifyMethod.SimplifyHints(
            h.GeometrySimplification | h.AntialiasingSimplification
        )


def export_layers_to_geopackage(output_filename, selected_layers=None, replace_project=True):
    """
    Exportuje vektorové vrstvy do formátu GeoPackage (.gpkg) a nahradí projekt novým,
    který správně odkazuje na vrstvy v GeoPackage.
    
    Parametry:
        output_filename (str): Název výstupního souboru (bez přípony)
        selected_layers (list): Seznam názvů vrstev k exportu. Pokud je None, exportují se všechny viditelné vrstvy.
        replace_project (bool): Pokud True, nahradí projekt novým se správně načtenými vrstvami
    
    Návratová hodnota:
        bool: True pokud byl export úspěšný, jinak False
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
    output_gpkg = output_filename if output_filename.endswith('.gpkg') else output_filename + '.gpkg'

# Filtrujeme jen vektorové vrstvy
    vector_layers = [layer for layer in layers_to_export if isinstance(layer, QgsVectorLayer)]

    # Vytvoříme slovník pro mapování mezi originálními názvy a ID
    original_names = {}

    # Nastavíme názvy vrstev na jejich ID
    for vector_layer in vector_layers:
        original_name = vector_layer.name()
        layer_id = TABLE_PREFIX + vector_layer.id()
        
        # Zapamatujeme si mapování mezi ID a původním názvem
        original_names[layer_id] = original_name
        
        # Nastavíme název vrstvy na ID
        vector_layer.setName(layer_id)
        
        print(f"Vrstva '{original_name}' bude exportována s ID jako názvem")

    # Nyní můžeme exportovat vrstvy do GeoPackage
    parameters = {
        'LAYERS': vector_layers,
        'OUTPUT': output_gpkg,
        'OVERWRITE': True,
        'SAVE_STYLES': True,
        'SAVE_METADATA': True,
    }

    export_success = False
    try:
        # Použití nástroje "package layers" pro export do GeoPackage
        result = processing.run("native:package", parameters)
        print(f"Export vrstev dokončen: {result}")
        export_success = True
        
        # Po exportu aktualizujeme popisy vrstev v GeoPackage
        
        try:
            conn = sqlite3.connect(output_gpkg)
            cursor = conn.cursor()
            
            # Pro každé ID vrstvy aktualizujeme popis v tabulce gpkg_contents
            for layer_id, original_name in original_names.items():
                # Aktualizujeme popis v tabulce gpkg_contents
                cursor.execute(
                    "UPDATE gpkg_contents SET description = ? WHERE table_name = ?",
                    (f"Original name: {original_name}", layer_id)
                )
            
            conn.commit()
            conn.close()
            print("Popis vrstev v GeoPackage byl aktualizován.")
        except sqlite3.Error as sqlite_error:
            print(f"CHYBA při aktualizaci popisů v GeoPackage: {str(sqlite_error)}")
        
    except Exception as e:
        print(f"Došlo k chybě během exportu vrstev: {str(e)}")
        import traceback
        traceback.print_exc()
        export_success = False
    finally:
        # Vždy obnovíme původní názvy vrstev
        # (klíčem je název tabulky = prefix + ID, ne samotné ID)
        for vector_layer in vector_layers:
            layer_id = TABLE_PREFIX + vector_layer.id()
            if layer_id in original_names:
                vector_layer.setName(original_names[layer_id])    


# V části kde exportujeme vrstvy do GeoPackage (ve funkci export_layers_to_geopackage)

# Po úspěšném exportu přidáme prostorové indexy do GeoPackage
    if export_success:
        # Prostorový index (R-tree) vytváří už native:package, zde se přidávají
        # jen indexy na atributy.
        print("Vytvářím indexy na atributy...")
        try:
            conn = sqlite3.connect(output_gpkg)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT table_name, column_name FROM gpkg_geometry_columns")
                geometry_tables = cursor.fetchall()
                print(f"Nalezeno {len(geometry_tables)} geometrických tabulek.")

                for table_name, column_name in geometry_tables:
                    try:
                        cursor.execute(
                            f'CREATE INDEX IF NOT EXISTS "idx_{table_name}_fid" ON "{table_name}"("fid")'
                        )
                        cursor.execute(f'PRAGMA table_info("{table_name}")')
                        pocet = 0
                        for col_info in cursor.fetchall():
                            col_name, col_type = col_info[1], (col_info[2] or '')
                            if (col_name.lower() in [column_name.lower(), 'fid', 'geom', 'geometry', 'shape']
                                    or col_type.upper() in ['GEOMETRY', 'BLOB']):
                                continue
                            try:
                                cursor.execute(
                                    f'CREATE INDEX IF NOT EXISTS "idx_{table_name}_{col_name}" '
                                    f'ON "{table_name}"("{col_name}")'
                                )
                                pocet += 1
                            except sqlite3.Error as e:
                                print(f"✗ Nelze vytvořit index na {table_name}.{col_name}: {e}")
                        print(f"✓ {table_name}: index na fid + {pocet} atributů")
                    except sqlite3.Error as e:
                        print(f"✗ Chyba při vytváření indexů pro {table_name}: {e}")

                conn.commit()

                print("Optimalizuji databázi...")
                cursor.execute("ANALYZE")
                conn.commit()
                cursor.execute("VACUUM")
                print("✓ ANALYZE a VACUUM dokončeny")
            finally:
                conn.close()
        except sqlite3.Error as sqlite_error:
            print(f"CHYBA při vytváření indexů: {str(sqlite_error)}")

    # Ověření, zda soubor existuje
    if os.path.exists(output_gpkg):
        file_size = os.path.getsize(output_gpkg)
        print(f"Soubor úspěšně vytvořen: {output_gpkg}")
        print(f"Velikost souboru: {file_size / 1024:.2f} KB")
        
        
        
        # Nahrazení projektu QGIS novým se správně načtenými vrstvami
        if replace_project and export_success:
            replaced = create_new_project_from_gpkg(output_gpkg)
            if replaced:
                print(f"Vytvořen nový projekt s vrstvami z GeoPackage.")
            else:
                print(f"Nepodařilo se vytvořit nový projekt.")
        
        return True
    else:
        print(f"Soubor nebyl vytvořen!")
        return False
    
def create_new_project_from_gpkg(gpkg_path, save_to_gpkg=True, use_caching=True):
    """
    Vytvoří nový projekt s hierarchií skupin z aktuálního projektu a vrstvami z GeoPackage,
    bez ukládání projektu do GeoPackage. Nastaví pracovní adresář projektu na adresář s GeoPackage.
    
    Parametry:
        gpkg_path (str): Cesta k GeoPackage souboru
    
    Návratová hodnota:
        bool: True pokud byl projekt úspěšně vytvořen, jinak False
    """
    
    global layer_caches
    layer_caches = {}
    
    try:

        # Získáme název souboru a adresář z cesty
        gpkg_filename = os.path.basename(gpkg_path)
        gpkg_dir = os.path.dirname(gpkg_path)
        
        if not gpkg_dir:  # Pokud je cesta relativní a nemá adresář
            gpkg_dir = os.getcwd()
        
        print(f"Pracuji s GeoPackage souborem: {gpkg_filename}")
        print(f"Adresář GeoPackage: {gpkg_dir}")
        
        # Získáme referenci na aktuální projekt
        current_project = QgsProject.instance()
        current_root = current_project.layerTreeRoot()
        
        # Nejprve si uložíme informace o hierarchii skupin a vrstvách
        group_structure = []
        
        # Funkce pro rekurzivní procházení hierarchie a ukládání informací
        def save_hierarchy(group, parent_path=""):
            group_info = {
                "name": group.name(),
                "path": f"{parent_path}/{group.name()}" if parent_path else group.name(),
                "groups": [],
                "layers": []
            }
            
            # Procházíme děti skupiny
            for child in group.children():
                if isinstance(child, QgsLayerTreeGroup):
                    # Rekurzivně zpracujeme podskupinu
                    child_info = save_hierarchy(child, group_info["path"])
                    group_info["groups"].append(child_info)
                elif isinstance(child, QgsLayerTreeLayer):
                    # Uložíme informace o vrstvě
                    layer = child.layer()
                    if isinstance(layer, QgsVectorLayer):
                        layer_info = {
                            "name": layer.name(),
                            "id": layer.id(),  # Uložíme ID vrstvy
                            "table": TABLE_PREFIX + layer.id(),  # název tabulky v GeoPackage
                            "visible": child.itemVisibilityChecked()
                        }
                        group_info["layers"].append(layer_info)
            
            return group_info
        
        # Uložíme hierarchii skupin
        hierarchy = save_hierarchy(current_root)
        
        print(f"Uložena hierarchie skupin a vrstev z původního projektu.")
        
        # Nyní vyčistíme aktuální projekt
        current_project.clear()
        new_root = current_project.layerTreeRoot()
        
        # Nastavíme pracovní adresář projektu
        current_project.setPresetHomePath(gpkg_dir)
        # Nastavit použití relativních cest pro celý projekt
        current_project.writeEntry("Paths", "Absolute", False)

        # Také je dobré nastavit základní cestu pro relativní cesty (obvykle adresář projektu)
        current_project.writeEntry("Paths", "Path", ".")

        # Aktualizovat nastavení
        current_project.write()
        # Po vytvoření nového projektu a před načtením vrstev z GeoPackage:
        # Nastavení souřadnicového systému na EPSG:5514 (S-JTSK / Krovak East North)
        try:
            # Vytvoříme instanci souřadnicového systému EPSG:5514
            crs = QgsCoordinateReferenceSystem("EPSG:5514")
            
            if crs.isValid():
                # Nastavíme souřadnicový systém projektu
                current_project.setCrs(crs)
                print(f"Souřadnicový systém projektu nastaven na: {crs.description()} ({crs.authid()})")
            else:
                print("VAROVÁNÍ: Nelze vytvořit platný souřadnicový systém EPSG:5514!")
        except Exception as e:
            print(f"Chyba při nastavování souřadnicového systému: {str(e)}")
        
        
        
        
        
        print(f"Vytvořen nový projekt. Pracovní adresář nastaven na: {gpkg_dir}")
        print(f"Připojuji vrstvy z {gpkg_filename}")
        
        # Načteme informace o původních názvech vrstev z GeoPackage
        
        try:
            conn = sqlite3.connect(gpkg_path)
            cursor = conn.cursor()
            
            # Získáme seznam vrstev s jejich popisy
            cursor.execute("SELECT table_name, description FROM gpkg_contents WHERE data_type='features'")
            layers_info = {row[0]: row[1] for row in cursor.fetchall()}
            conn.close()
        except sqlite3.Error as sqlite_error:
            print(f"CHYBA při čtení z GeoPackage: {str(sqlite_error)}")
            layers_info = {}
        
        # Slovníky pro mapování vrstev
        id_to_layer = {}     # Mapování ID -> vrstva
        name_to_layer = {}   # Mapování název -> vrstva
        
        # Nejprve načteme všechny vrstvy z GeoPackage
        for table_name, description in layers_info.items():
            # Přeskočíme systémové tabulky
            if table_name.startswith('gpkg_') or table_name.startswith('sqlite_') or table_name.startswith('rtree_') or table_name == 'empty':
                continue
            print("table name " + table_name)        
            # Načteme vrstvu z GeoPackage
            gpgk_basename = os.path.basename(gpkg_path)
            layer_path = f"{gpkg_path}|layername={table_name}"

           # Při načítání vrstvy z GeoPackage (ve funkci create_new_project_from_gpkg)

            # Místo kódu:
            new_layer = QgsVectorLayer(layer_path, table_name, "ogr")

            # Použijeme toto s dodatečnými parametry:
            """
            uri = QgsDataSourceUri()
            uri.setDatabase(gpkg_path)
            uri.setDataSource('', table_name, 'geom', '', 'ogc_fid')
            new_layer = QgsVectorLayer(uri.uri(), table_name, "ogr")
            """
            # Nastavení vykreslování po načtení
            if new_layer.isValid():
                
                # Nastavení optimální velikosti vyrovnávací paměti
                new_layer.setReadExtentFromXml(True)  # Načítá jen rozsah z XML
                
                # Nastavení chování paměti cache
                ##new_layer.setFeatureCacheEstablished(True)
                
                # Optimalizace rendererů pro velké vrstvy
                renderer = new_layer.renderer()
                if renderer:
                    renderer.setForceRasterRender(False)  # Pro vektorové vykreslování použijeme False 
                        
            
            
            
            
            
            if new_layer.isValid():
                
                # Zkontrolujeme, zda má vrstva platné filtry
                if new_layer.subsetString():
                    print(f"Vrstva {table_name} má filtr: {new_layer.subsetString()}")
                    # Pokud je filtr prázdný nebo způsobuje chyby, zkusíme ho vyčistit
                    if new_layer.subsetString().strip() == "":
                        new_layer.setSubsetString("")
                        print(f"Vyčištěn prázdný filtr pro vrstvu {table_name}")
                
                
                
                # Získáme původní název z popisu, pokud existuje
                original_name = table_name  # Výchozí je použít název tabulky
                if description and description.startswith("Original name: "):
                    original_name = description[len("Original name: "):]
                
                # Nastavíme původní název vrstvy
                new_layer.setName(original_name)
                
                # Uložíme vrstvu do slovníků pro vyhledávání
                id_to_layer[table_name] = new_layer
                name_to_layer[original_name] = new_layer
                print(f"Načtena vrstva: {original_name} z tabulky {table_name}")
            else:
                print(f"CHYBA: Nelze načíst vrstvu {table_name}")
        
        # Funkce pro vytvoření struktury skupin podle uložené hierarchie
        def recreate_hierarchy(group_info, parent_group):
            # Vytvoříme skupinu
            if group_info["name"] != parent_group.name():  # Přeskočíme kořenovou skupinu
                new_group = parent_group.addGroup(group_info["name"])
                print(f"Vytvořena skupina: {group_info['path']}")
            else:
                new_group = parent_group
            
            # Přidáme vrstvy do skupiny
            for layer_info in group_info["layers"]:
                layer_name = layer_info["name"]
                # tabulky v GeoPackage se jmenují prefix + ID vrstvy
                layer_id = layer_info["table"]
                
                # Nejprve zkusíme najít vrstvu podle ID
                if layer_id in id_to_layer:
                    new_layer = id_to_layer[layer_id]
                    current_project.addMapLayer(new_layer, False)  # False znamená, že se vrstva nepřidá do root
                    new_group.addLayer(new_layer)
                    print(f"Přidána vrstva {layer_name} (podle ID: {layer_id}) do skupiny {group_info['path']}")
                    
                    # Nastavíme viditelnost
                    new_layer_node = new_group.findLayer(new_layer.id())
                    if new_layer_node:
                        new_layer_node.setItemVisibilityChecked(layer_info["visible"])
                    
                    # Označíme jako použitou
                    id_to_layer.pop(layer_id, None)
                    if new_layer.name() in name_to_layer:
                        name_to_layer.pop(new_layer.name(), None)

                # vrstvy, které se neexportovaly (např. vypnuté), se tiše přeskočí
            
            # Rekurzivně vytvoříme podskupiny
            for subgroup_info in group_info["groups"]:
                recreate_hierarchy(subgroup_info, new_group)

            # Skupina bez vrstev (všechny její vrstvy byly vypnuté) se nevytváří
            if new_group is not parent_group and not new_group.findLayers():
                parent_group.removeChildNode(new_group)
        
        # Vytvoříme strukturu skupin a přidáme vrstvy
        recreate_hierarchy(hierarchy, new_root)

        
        # Sloučíme zbývající slovníky, abychom měli přehled o všech zbývajících vrstvách
        remaining_layers = {}
        remaining_layers.update(id_to_layer)
        remaining_layers.update(name_to_layer)
        
        # Přidáme všechny zbývající vrstvy, které nebyly přidány do hierarchie
        if remaining_layers:
            print(f"Přidávám zbývající vrstvy do kořenové úrovně...")
            for key, layer in remaining_layers.items():
                # Kontrola, zda vrstva již není v projektu
                if not current_project.mapLayer(layer.id()):
                    current_project.addMapLayer(layer)
                    print(f"Přidána vrstva {layer.name()} do kořenové úrovně (nebyla v původní hierarchii)")
        
        # Nastavíme název projektu na název GeoPackage souboru (bez přípony)
        project_name = os.path.splitext(gpkg_filename)[0]
        current_project.setTitle(project_name)
        
        print(f"Projekt '{project_name}' byl úspěšně vytvořen s vrstvami z {gpkg_filename}")
        print(f"Pracovní adresář projektu nastaven na: {gpkg_dir}")
                

        if use_caching:
            print("Optimalizuji projekt pomocí QgsVectorLayerCache...")
            layer_caches = optimize_project_with_caching(current_project)
  

                
        # Po načtení vrstev z GeoPackage a před uložením projektu:

        # Optimalizace vykreslování pro lepší výkon
        print("Optimalizuji nastavení projektu pro rychlejší vykreslování...")

        # Získáme přístup k mapovému plátnu
        canvas = iface.mapCanvas()

        # Nastavení vykreslování pro lepší výkon
        if canvas:
            # Nastavení simplifikace geometrií
            canvas.setMapUpdateInterval(100)  # Intervalové vykreslování (ms)
            
            # Nastavení pro všechny vektorové vrstvy projektu
            for layer in current_project.mapLayers().values():
                if isinstance(layer, QgsVectorLayer):
                    # simplifyMethod() vrací kopii -> nastavit a zapsat zpět
                    method = QgsVectorSimplifyMethod()
                    method.setSimplifyHints(_simplify_flags())
                    method.setThreshold(1.0)
                    layer.setSimplifyMethod(method)

            print("Nastavení projektu optimalizováno pro rychlejší vykreslování.")                
                
                
                
                
        QgsLayerTreeUtils.updateEmbeddedGroupsProjectPath(new_root,current_project )
        current_project.write()
         
                
        if save_to_gpkg:
            try:
                # Uložení projektu do GeoPackage
                project_path = f"geopackage:{gpkg_path}?projectName={project_name}"
                save_success = current_project.write(project_path)
                
                if save_success:
                    print(f"Projekt byl úspěšně uložen do GeoPackage: {gpkg_path}")
                    print(f"Název projektu v GeoPackage: {project_name}")
                else:
                    print(f"CHYBA: Nepodařilo se uložit projekt do GeoPackage!")
            except Exception as e:
                print(f"Chyba při ukládání projektu do GeoPackage: {str(e)}")
                import traceback
                traceback.print_exc()
                return False
        
        return True            
    except Exception as e:
        print(f"Chyba při vytváření nového projektu: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
def apply_vector_layer_cache(layer, cache_size=10000):
    """
    Aplikuje QgsVectorLayerCache na vrstvu pro rychlejší přístup k datům.
    
    Parametry:
        layer: QgsVectorLayer instance
        cache_size: velikost cache (počet prvků)
    
    Návratová hodnota:
        QgsVectorLayerCache instance nebo None při chybě
    """
    try:
        if layer and layer.isValid():
            # Vytvoření cache pro vrstvu
            layer_cache = QgsVectorLayerCache(layer, cache_size)
            
            # Nastavení cache pro všechny prvky
            layer_cache.setCacheSize(cache_size)
            
            print(f"✓ Cache {cache_size} prvků aplikována na vrstvu {layer.name()}")
            return layer_cache
        else:
            print(f"✗ Nelze aplikovat cache - neplatná vrstva")
            return None
            
    except Exception as e:
        print(f"✗ Chyba při aplikaci cache na vrstvu {layer.name()}: {e}")
        return None


def optimize_project_with_caching(project, default_cache_size=10000):
    """
    Optimalizuje projekt pomocí QgsVectorLayerCache pro všechny vektorové vrstvy.
    
    Parametry:
        project: QgsProject instance
        default_cache_size: výchozí velikost cache
    
    Návratová hodnota:
        dict: slovník s layer_id -> QgsVectorLayerCache
    """
    layer_caches = {}
    
    try:
        # Získání všech vrstev v projektu
        layers = project.mapLayers()
        vector_layers = [layer for layer in layers.values()
                        if isinstance(layer, QgsVectorLayer)]
        
        print(f"Optimalizuji {len(vector_layers)} vektorových vrstev pomocí cache...")
        
        for layer in vector_layers:
            try:
                # Určení velikosti cache podle počtu prvků ve vrstvě
                feature_count = layer.featureCount()
                
                if feature_count > 0:
                    # Adaptivní velikost cache podle počtu prvků
                    if feature_count < 1000:
                        cache_size = min(feature_count, 1000)
                    elif feature_count < 10000:
                        cache_size = min(feature_count, 5000)
                    else:
                        cache_size = default_cache_size
                    
                    # Aplikace cache na vrstvu
                    layer_cache = apply_vector_layer_cache(layer, cache_size)
                    
                    if layer_cache:
                        layer_caches[layer.id()] = layer_cache
                        print(f"✓ Vrstva '{layer.name()}' optimalizována (cache: {cache_size})")
                    else:
                        print(f"✗ Nelze optimalizovat vrstvu {layer.name()}")
                else:
                    print(f"⚠ Vrstva '{layer.name()}' je prázdná, přeskakuji optimalizaci")
                    
            except Exception as e:
                print(f"✗ Nelze optimalizovat vrstvu {layer.name()}: {e}")
        
        print(f"Cache optimalizace dokončena pro {len(layer_caches)} vrstev")
        return layer_caches
        
    except Exception as e:
        print(f"Chyba při optimalizaci projektu: {e}")
        return {}


def create_optimized_layer_path(gpkg_path, table_name):
    """
    Vytvoří optimalizovanou cestu k vrstvě v GeoPackage s parametry pro rychlejší načítání.
    
    Parametry:
        gpkg_path: cesta k GeoPackage souboru
        table_name: název tabulky/vrstvy
        
    Návratová hodnota:
        str: optimalizovaná cesta k vrstvě
    """
    layer_path = f"{gpkg_path}|layername={table_name}"
    
    # Přidání parametrů pro optimalizaci
    optimization_params = [
        "spatialindex=yes",      # Použití prostorového indexu
        "loadOnDemand=yes",      # Načítání na vyžádání
        "cacheFeatures=yes"      # Cache prvků
    ]
    
    for param in optimization_params:
        layer_path += f"|{param}"
    
    return layer_path
