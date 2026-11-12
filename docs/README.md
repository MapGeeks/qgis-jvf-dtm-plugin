# **QGIS plugin pro digitální technickou mapu** 

Tento **QGIS plugin** umožňuje načítání a vizualizaci **digitální technické mapy (DTM)** ve formátu **JVF**. 
Umožňuje jednoduché zobrazení vrstev dopravní infrastruktury, technické infrastruktury a základní prostorové situace přímo v prostředí **QGIS**.  

- **Verze pluginu:** **2.0.0**  
- **Podporovaná verze formátu:** **1.5.0.2**. K načtení formátu verze **1.4.3** použijte starší verzi aplikace.  
- **Autoři:** **MapGeeks – Linda Karlovská & Petr Barandovski**  

## 🔹 **Hlavní funkce**  
✅ **Načítání JVF souborů** – Import DTM dat z formátu JVF včetně podpory více vrstev.  
✅ **Interaktivní vizualizace** – Zobrazení prvků s možností zvýraznění a prohlížení atributů.  
✅ **Podpora 3D geometrií** – Práce s výškovými daty včetně jejich správného zobrazení.  
✅ **Efektivní práce s více geometriemi** – Oddělené zpracování hlavní a doplňkové geometrie.  
✅ **Export do GeoPackage a DXF** – Uložení zobrazených vrstev včetně stylů do GeoPackage nebo do DXF pro CAD.  
✅ **Snadné ovládání** – Intuitivní uživatelské rozhraní dostupné přímo v QGIS.  

## 📌 **Instalace a použití**
Instalace je podrobně popsána [zde](/docs/instalace.md). Použití popsáno [zde](/docs/pouziti.md) je možné nejprve otestovat na testovacích datech.
Export do GeoPackage a DXF je popsán [zde](/docs/export.md).

🔹 **Linux:** Plugin potřebuje Python modul **pandas**. Na Windows je součástí instalace QGIS, na Linuxu je ho nutné doinstalovat, postup je popsán [zde](/docs/instalace.md).

- **Testovací data:** **Ke stažení [zde](/sample_data/JVF_DTM_143_UkazkyXML.zip)**  

## 📌 **Časté otázky a odpovědi**

## Odkud pocházejí testovací data a jak je použít?  
Testovací data pocházejí z **Portálu DMVS** a jsou ke stažení [zde](/sample_data/JVF_DTM_143_UkazkyXML.zip). Před použitím je nutné je **rozbalit**. Jde o ukázky ve starší verzi formátu **1.4.3**, k jejich načtení použijte starší verzi aplikace. Dataset obsahuje ukázkové soubory formátu JVF, zahrnující vrstvy **dopravní infrastruktury, technické infrastruktury a základní prostorové situace**.

## Jaká je rychlost načítání?  
Rychlost načítání závisí na velikosti souboru:  
- **Malé soubory** (jednotky MB) se načítají během několika sekund.  
- **Středně velké soubory** (desítky MB) mohou trvat **desítky sekund**.  
- **Velké soubory** (stovky MB) mohou vyžadovat **až několik minut**.  

🔹 **Poznámka:** Při načítání větších souborů může QGIS dočasně přestat reagovat – vyčkejte, než se proces dokončí.

## Co se změnilo s podporou JVF DTM 1.5?  
Od verze **2.0.0** plugin načítá soubory ve formátu **JVF DTM 1.5.0.2**:  
- Záznamy objektu jsou ve verzi 1.5 rozlišeny podle typu zápisu (např. `ZaznamObjektuIns`, `ZaznamObjektuUpd`). Plugin načte všechny záznamy kromě **záznamů o výmazu** (`…Del`), které se nezobrazují.  
- K načtení formátu verze **1.4.3** použijte starší verzi aplikace.  
- Aktualizovány jsou XSD schémata i styly. **Definiční body** mají nově vlastní styly, viz [logika stylování](/docs/logika-stylovani.md).  

## Jak plugin řeší více geometrií u jednoho prvku?  
Pokud má prvek v DTM **dvě geometrie**, plugin je zpracuje následovně:  
- **První geometrie** je považována za hlavní, má přiřazený styl a odpovídá atributu `code_suffix`.  
- **Druhá geometrie** se načte do samostatné vrstvy (název vrstvy je doplněn o typ geometrie, např. `_Polygon`) a je ve výchozím stavu **zobrazená** stejně jako hlavní geometrie. Nemá definovaný styl, proto má **náhodnou barvu** a není vázána na konkrétní měřítko. Pokud ji nechcete vidět, stačí vrstvu v panelu vrstev odškrtnout.  

🔹 **Poznámka:** Export do GeoPackage a DXF zpracovává jen zaškrtnuté vrstvy, takže druhá geometrie se exportuje také, pokud ji před exportem neodškrtnete.  

## Jak plugin pracuje s 3D geometriemi?  
Plugin podporuje **3D geometrie**, ale jejich zobrazení závisí na možnostech QGIS. Momentálně:  
- Některé prvky mají výšku **0** (z podstaty formátu JVF DTM).  
- Jiné objekty jsou vykresleny ve **správné výšce**, což může vést k efektu „vznášení se ve vzduchu“.

## Jak exportovat načtená data do GeoPackage nebo DXF?
Ikonou **JVF DTM Viewer - export to DXF or GeoPackage** vyberte cílový soubor a jako typ zvolte **GeoPackage (\*.gpkg)** nebo **DXF (\*.dxf)**. Exportují se všechny zaškrtnuté vektorové vrstvy. Název souboru musí končit příponou `.dxf` nebo `.gpkg`, jinak se export tiše neprovede. Podrobný popis je [zde](/docs/export.md).

## Jak je v pluginu řešena logika stylování?
Logika stylování je na třech různě složitých případech popsána [zde](/docs/logika-stylovani.md).

