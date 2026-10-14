# **QGIS plugin pro digitální technickou mapu** 

Tento **QGIS plugin** umožňuje načítání a vizualizaci **digitální technické mapy (DTM)** ve formátu **JVF**. 
Umožňuje jednoduché zobrazení vrstev dopravní infrastruktury, technické infrastruktury a základní prostorové situace přímo v prostředí **QGIS**.  

- **Podporovaná verze formátu:** **1.4.3**  
- **Autoři:** **MapGeeks – Linda Karlovská & Petr Barandovski**  

## 🔹 **Hlavní funkce**  
✅ **Načítání JVF souborů** – Import DTM dat z formátu JVF včetně podpory více vrstev.  
✅ **Interaktivní vizualizace** – Zobrazení prvků s možností zvýraznění a prohlížení atributů.  
✅ **Podpora 3D geometrií** – Práce s výškovými daty včetně jejich správného zobrazení.  
✅ **Efektivní práce s více geometriemi** – Oddělené zpracování hlavní a doplňkové geometrie.  
✅ **Snadné ovládání** – Intuitivní uživatelské rozhraní dostupné přímo v QGIS.  

## 📌 **Instalace a použití**
Instalace je podrobně popsána [zde](/docs/instalace.md). Použití popsáno [zde](/docs/pouziti.md) je možné nejprve otestovat na testovacích datech.

- **Testovací data:** **Ke stažení [zde](/sample_data/JVF_DTM_143_UkazkyXML.zip)**  

## 📌 **Časté otázky a odpovědi**

## Odkud pocházejí testovací data a jak je použít?  
Testovací data pocházejí z **Portálu DMVS** a jsou ke stažení [zde](/sample_data/JVF_DTM_143_UkazkyXML.zip). Před použitím je nutné je **rozbalit**. Dataset obsahuje ukázkové soubory formátu JVF, zahrnující vrstvy **dopravní infrastruktury, technické infrastruktury a základní prostorové situace**.

## Jaká je rychlost načítání?  
Rychlost načítání závisí na velikosti souboru:  
- **Malé soubory** (jednotky MB) se načítají během několika sekund.  
- **Středně velké soubory** (desítky MB) mohou trvat **desítky sekund**.  
- **Velké soubory** (stovky MB) mohou vyžadovat **až několik minut**.  

🔹 **Poznámka:** Při načítání větších souborů může QGIS dočasně přestat reagovat – vyčkejte, než se proces dokončí.

## Jak plugin řeší více geometrií u jednoho prvku?  
Pokud má prvek v DTM **dvě geometrie**, plugin je zpracuje následovně:  
- **První geometrie** je považována za hlavní, má přiřazený styl a odpovídá atributu `code_suffix`.  
- **Druhá geometrie** je ve výchozím stavu **skrytá**, protože nemá definovaný styl. Pokud ji zobrazíte, bude mít **náhodnou barvu** a nebude vázána na konkrétní měřítko.  

## Jak plugin pracuje s 3D geometriemi?  
Plugin podporuje **3D geometrie**, ale jejich zobrazení závisí na možnostech QGIS. Momentálně:  
- Některé prvky mají výšku **0** (z podstaty formátu JVF DTM).  
- Jiné objekty jsou vykresleny ve **správné výšce**, což může vést k efektu „vznášení se ve vzduchu“.

## Jak je v pluginu řešena logika stylování?
Logika stylování je na třech různě složitých případech popsána [zde](/docs/logika-stylovani.md).

