# Export do GeoPackage a DXF

Plugin umí uložit načtená data DTM do dvou formátů:

- **GeoPackage (.gpkg)** – pro další práci v QGIS nebo jiném GIS, včetně stylů, struktury skupin a uloženého projektu,
- **DXF (.dxf)** – pro předání do CAD programů (AutoCAD, BricsCAD, LibreCAD apod.).

## Spuštění exportu

1. Načtěte jeden nebo více JVF souborů (viz [Použití](pouziti.md)).
2. V panelu vrstev zaškrtněte to, co chcete exportovat (viz [Co se exportuje](#co-se-exportuje)).
3. Pro DXF nastavte v mapovém okně **měřítko**, ve kterém má výkres vypadat (např. 1:500), viz [Export do DXF](#export-do-dxf).
4. Klikněte na ikonu **JVF DTM Viewer - export to DXF or GeoPackage** (je také v menu *Vektor → JVF DTM Viewer*).
5. V dialogu pro uložení zadejte název souboru a jako typ zvolte **DXF (\*.dxf)** nebo **GeoPackage (\*.gpkg)**.

O formátu exportu rozhoduje **přípona souboru**, nikoli typ vybraný v dialogu. Existující soubor se stejným názvem se přepíše.

⚠️ **Pokud název souboru nekončí na `.dxf` ani `.gpkg`, export se neprovede a plugin o tom nijak neinformuje** (nezobrazí se žádná chyba ani hláška). Na Windows dialog příponu podle vybraného typu obvykle doplní sám, v jiných systémech to není zaručeno. Pokud po exportu soubor nevznikl, zkontrolujte, zda jste příponu zadali, a zadejte ji případně ručně, např. `vykres.dxf` nebo `data.gpkg`.

Export běží v hlavním vlákně QGIS, u velkých dat proto může QGIS na chvíli přestat reagovat. Průběh a případné chyby se vypisují do **Python konzole** (*Zásuvné moduly → Python konzole*).

## Co se exportuje

Pro oba formáty platí stejné pravidlo: exportují se **všechny vektorové vrstvy, které jsou v panelu vrstev zaškrtnuté a zároveň mají zaškrtnuté všechny nadřazené skupiny**. Nezáleží na tom, zda vrstva pochází z pluginu, exportovat lze i jiné vektorové vrstvy v projektu. Rastrové vrstvy (např. WMS podklad) se nikdy neexportují.

Při načtení dalšího JVF souboru plugin odškrtne skupiny dříve načtených souborů, takže bez dalšího zásahu se exportuje jen naposledy načtený soubor. Chcete-li exportovat více souborů najednou, zaškrtněte jejich skupiny ručně.

Do exportu se dostanou i vrstvy s **druhou geometrií** objektů, protože jsou po načtení zaškrtnuté. Pokud je nechcete, odškrtněte je před exportem.

## Export do GeoPackage

### Co se děje

1. **Uložení vrstev** – vrstvy se uloží algoritmem *Zabalit vrstvy* (`native:package`) do jednoho souboru GeoPackage včetně **stylů** a **metadat**. Prostorový index (R-strom) se vytvoří pro každou tabulku automaticky.
2. **Názvy tabulek** – názvy vrstev v DTM obsahují mezery, diakritiku a speciální znaky a mohou se opakovat. Tabulky v GeoPackage se proto jmenují podle ID vrstvy s předponou `tab` a původní název vrstvy se uloží do popisu tabulky (sloupec `description` v tabulce `gpkg_contents` ve tvaru `Original name: …`).
3. **Atributové indexy** – nad sloupcem `fid` a nad všemi atributovými sloupci se vytvoří indexy, aby filtrování a vyhledávání podle atributů bylo rychlé. Nakonec proběhne `ANALYZE` a `VACUUM`.
4. **Nahrazení projektu** – aktuální projekt QGIS se **vyčistí** a vytvoří se nový projekt, ve kterém:
   - je nastaven souřadnicový systém **S-JTSK / Krovak East North (EPSG:5514)**,
   - vrstvy se načtou z GeoPackage a dostanou zpět své **původní názvy**,
   - je obnovena **stejná struktura skupin** a **stejné zaškrtnutí** vrstev jako v původním projektu; skupiny, ve kterých nezůstala žádná exportovaná vrstva, se nevytvářejí,
   - vrstvy, které nebyly ve struktuře skupin nalezeny, se přidají do kořene panelu vrstev,
   - je zapnuto zjednodušování geometrií při vykreslování a cache prvků pro rychlejší práci s velkými daty.
5. **Uložení projektu do GeoPackage** – nový projekt se uloží přímo do souboru GeoPackage pod názvem souboru bez přípony.

### Upozornění

Export do GeoPackage **nahradí aktuální projekt bez dotazu na uložení**. Pokud máte v projektu neuložené změny nebo vrstvy, které nechcete ztratit, uložte projekt před exportem.

### Opětovné otevření

Projekt uložený v GeoPackage otevřete přes *Projekt → Otevřít z → GeoPackage*, vyberte soubor `.gpkg` a v něm projekt se stejným názvem. Načtou se vrstvy, styly i struktura skupin. Jednotlivé vrstvy lze z GeoPackage přidat i samostatně přes *Vrstva → Přidat vrstvu → Přidat vektorovou vrstvu*; v seznamu tabulek je poznáte podle popisu `Original name: …`.

## Export do DXF

### Měřítko exportu

Styly v pluginu jsou **závislé na měřítku** (každý objekt má styl pro měřítka 1:500, 1:5 000, 1:10 000 a 1:25 000, viz [Logika stylování](logika-stylovani.md)). Export do DXF použije **aktuální měřítko mapového okna** (to, které je vidět ve stavovém řádku QGIS) a podle něj:

- vybere, které prvky se exportují – prvky, které v daném měřítku nemají styl a v mapě nejsou vidět, se do DXF **nedostanou**,
- určí velikost bodových značek a textů,
- přepočítá šířky čar na tloušťky čar v DXF.

DXF tedy odpovídá tomu, co vidíte v mapě. Pro výkres v měřítku 1:500 proto před exportem nastavte měřítko mapy na 1:500.

### Co se děje

1. **Inverze odstínů šedi** – CAD programy mají obvykle tmavé pozadí, proto se v symbolech dočasně invertují šedé barvy (černá ↔ bílá, tmavě šedá ↔ světle šedá). Barevné symboly zůstávají beze změny. Po exportu se původní styly vrstev vždy obnoví, i když export skončí chybou.
2. **Export** – vrstvy se exportují přes `QgsDxfExport` (stejná funkce jako *Projekt → Import/Export → Exportovat projekt do DXF*) se symbologií po jednotlivých vrstvách symbolu, v souřadnicovém systému **EPSG:5514** a se zachováním **výšek (3D)**. Každá vrstva QGIS odpovídá jedné **hladině** v DXF se stejným názvem (znaky, které DXF nepovoluje, se nahradí podtržítkem). Prázdné vrstvy se vynechají. Pokud tento způsob selže nebo nevytvoří žádné entity, použije se záložní algoritmus `native:dxfexport`.
3. **Úpravy výsledného souboru**:
   - verze DXF se nastaví na **AC1021 (AutoCAD 2007)** a soubor se převede do **UTF-8**, aby se v CAD správně zobrazila česká diakritika,
   - z tabulky hladin se odstraní **prázdné hladiny**, na které neodkazuje žádná entita,
   - vlastnosti se přesunou do hladin (**DleHlad / ByLayer**): pro každou hladinu se zjistí nejčastější barva, typ čáry a tloušťka čáry jejích entit a zapíše se do hladiny; entity se shodnými hodnotami pak mají vlastnosti *DleHlad*, odlišné entity si je ponechají,
   - **šířka polylinií** se podle měřítka exportu převede na nejbližší standardní **tloušťku čáry** DXF, aby i tloušťka mohla být *DleHlad*,
   - hladinám bez entit se nastaví barva podle symbolu vrstvy (QGIS by jim jinak nechal červenou).

Výsledkem je výkres, ve kterém lze barvy, typy a tloušťky čar měnit hromadně ve správci hladin.

### Poznámky

- Vrstvy s **druhou geometrií** nemají předdefinovaný styl, exportují se proto ve své náhodné barvě a ve všech měřítkách.
- Pokud je výsledný DXF prázdný, zkontrolujte v Python konzoli výpis vrstev a jejich počtu prvků a ověřte, že v nastaveném měřítku mapy jsou prvky vidět.
