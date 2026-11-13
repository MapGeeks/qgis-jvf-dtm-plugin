# Použití

Klikněte na ikonku 
![Ikonka](img/plugin-ikona.png "Ikonka").

Pokud tuto ikonku nevidíte, klikněte na menu "Zobrazit" -> "Nástrojové lišty" a zatrhněte "Panel nástrojů Zásuvné moduly"
![Zobrazit nástrojové lišty - zásuvné moduly](img/zobrazeni-zasuvnych-modulu.png "Zobrazit nástrojové lišty - zásuvné moduly").

Po kliknutí na ikonku na Vás vyskočí následující dialogové okno:
![Dialogové okno - otevřít](img/nacteni-souboru.png "Dialogové okno - otevřít").

Otevřete požadovaný JVF soubor a vyčkejte až se načte.

Výsledek může vypadat například takto:
![Zobrazený soubor JVF](img/zobrazeni-qgis.png "Zobrazený soubor JVF").

Pokud chcete vidět atributy konkrétního objektu, klikněte na tuto ikonu:
![Ikona atributy](img/ikona-info-o-prvku.png "Ikona atributy").
vyberte vrstvu nebo skupinu, která Vás zajímá
![Vrstvy](img/vrstva-v-qgis.png "Vrstvy").

Vybraný objekt (objekty) se zvýrazní červeně a vyskočí na Vás následujcí panel "Identifikovat výsledky" se seznamem atributů objektu (objektů):
![Identifikovat výsledky](img/info-o-prvku.png "Identifikovat výsledky").

## Více geometrií u jednoho objektu

Pokud má objekt v JVF souboru dvě geometrie (např. definiční bod a plochu), načte se každá geometrie do vlastní vrstvy ve stejné skupině. Obě vrstvy jsou po načtení zaškrtnuté a zobrazené. Vrstva s druhou geometrií má v názvu navíc typ geometrie (např. `_Polygon`), nemá předdefinovaný styl, a proto se vykreslí náhodnou barvou ve všech měřítkách. Pokud ji nechcete zobrazit (ani exportovat), odškrtněte ji v panelu vrstev.

## Export

Načtená data lze uložit do GeoPackage nebo DXF druhou ikonou pluginu **JVF DTM Viewer - export to DXF or GeoPackage**
![Ikonka exportu](img/plugin-ikona-export.png "Ikonka exportu")
(je také v menu *Vektor → JVF DTM Viewer*).
Postup a popis toho, co se při exportu děje, najdete na stránce [Export do GeoPackage a DXF](export.md).
