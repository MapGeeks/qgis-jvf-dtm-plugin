import os
import re

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsGradientColorRamp,
    QgsProcessingParameterBoolean,
    QgsProject,
    QgsRuleBasedRenderer,
    QgsVectorLayer,
)
from qgis.utils import iface
from qgis.PyQt.QtGui import QColor
import processing


# ---------------------------------------------------------------------------
# Práce s barvami
# ---------------------------------------------------------------------------

def je_odstin_sedi(barva):
    """Barva je odstín šedi, pokud R = G = B."""
    return barva.red() == barva.green() == barva.blue()


def invertuj_barvu(barva):
    """Invertuje odstíny šedi (255 - hodnota), barevné ponechá. Zachová průhlednost."""
    if je_odstin_sedi(barva):
        hodnota = 255 - barva.red()
        return QColor(hodnota, hodnota, hodnota, barva.alpha())
    return barva


def invertuj_symbol(symbol):
    """Invertuje šedé barvy ve všech vrstvách symbolu včetně vnořených (sub)symbolů."""
    if symbol is None:
        return
    for i in range(symbol.symbolLayerCount()):
        sl = symbol.symbolLayer(i)
        for getter, setter in (
            ('color', 'setColor'),
            ('fillColor', 'setFillColor'),
            ('strokeColor', 'setStrokeColor'),
        ):
            if hasattr(sl, getter) and hasattr(sl, setter):
                try:
                    getattr(sl, setter)(invertuj_barvu(getattr(sl, getter)()))
                except Exception:
                    pass
        # např. marker line, centroid fill, ...
        if hasattr(sl, 'subSymbol'):
            invertuj_symbol(sl.subSymbol())


def invertuj_pravidla(rule):
    """Rekurzivně projde rule-based renderer."""
    for child in rule.children():
        invertuj_symbol(child.symbol())
        invertuj_pravidla(child)


def invertuj_renderer(renderer):
    """Invertuje šedé barvy v rendereru. Upravuje renderer na místě."""
    typ = renderer.type()

    if typ == "singleSymbol":
        invertuj_symbol(renderer.symbol())

    elif typ == "categorizedSymbol":
        # categories() vrací kopie -> nutno zapsat zpět přes updateCategorySymbol
        for idx, category in enumerate(renderer.categories()):
            symbol = category.symbol().clone()
            invertuj_symbol(symbol)
            renderer.updateCategorySymbol(idx, symbol)

    elif typ == "graduatedSymbol":
        # ranges() vrací kopie -> nutno zapsat zpět přes updateRangeSymbol
        for idx, rng in enumerate(renderer.ranges()):
            symbol = rng.symbol().clone()
            invertuj_symbol(symbol)
            renderer.updateRangeSymbol(idx, symbol)

    elif typ in ("RuleRenderer", "ruleBasedRenderer"):
        invertuj_pravidla(renderer.rootRule())

    elif typ == "heatmapRenderer":
        ramp = renderer.colorRamp()
        if isinstance(ramp, QgsGradientColorRamp):
            c1, c2 = ramp.color1(), ramp.color2()
            if je_odstin_sedi(c1) and je_odstin_sedi(c2):
                renderer.setColorRamp(QgsGradientColorRamp(invertuj_barvu(c1), invertuj_barvu(c2)))

    elif typ in ("pointDisplacement", "pointCluster"):
        if hasattr(renderer, 'clusterSymbol'):
            invertuj_symbol(renderer.clusterSymbol())
        if hasattr(renderer, 'centerSymbol'):
            invertuj_symbol(renderer.centerSymbol())
        if hasattr(renderer, 'embeddedRenderer') and renderer.embeddedRenderer():
            invertuj_renderer(renderer.embeddedRenderer())

    else:
        try:
            if hasattr(renderer, 'symbol'):
                invertuj_symbol(renderer.symbol())
            else:
                print(f"  - Nelze nastavit barvu pro renderer typu {typ}")
        except Exception:
            print(f"  - Nelze nastavit barvu pro renderer typu {typ}")


# ---------------------------------------------------------------------------
# Prvky bez stylu pro měřítko exportu
# ---------------------------------------------------------------------------

def rozsir_meritka(layer, scale):
    """
    Pokud rule-based renderer vrstvy nemá pro dané měřítko žádné pravidlo
    (např. osy železničních tratí mají styl jen pro 1:10 000 a 1:25 000),
    rozšíří nejpodrobnější dostupné pravidlo i na větší měřítka,
    aby se prvky do DXF dostaly. Upravuje renderer na místě.

    Returns:
        True, pokud bylo pravidlo rozšířeno.
    """
    renderer = layer.renderer()
    if not isinstance(renderer, QgsRuleBasedRenderer):
        return False

    pravidla = [r for r in renderer.rootRule().children() if r.active() and r.symbol()]
    if not pravidla or any(r.isScaleOK(scale) for r in pravidla):
        return False

    # nejpodrobnější = nejmenší jmenovatel "nejbližšího" měřítka
    nejpodrobnejsi = min(pravidla, key=lambda r: r.maximumScale())
    if nejpodrobnejsi.minimumScale() and nejpodrobnejsi.minimumScale() < scale:
        return False  # pravidlo platí jen pro podrobnější měřítka, nerozšiřujeme
    puvodni = nejpodrobnejsi.maximumScale()
    nejpodrobnejsi.setMaximumScale(0)
    print(f"  - {layer.name()}: bez stylu pro 1:{scale:g}, použit styl "
          f"'{nejpodrobnejsi.label()}' (původně od 1:{puvodni:g})")
    return True


# ---------------------------------------------------------------------------
# Parametry algoritmu
# ---------------------------------------------------------------------------

def priprav_parametry(parameters, alg_id="native:dxfexport"):
    """
    Přizpůsobí parametry aktuální verzi algoritmu:
    vyhodí neznámé klíče, chybějící booleany doplní na False,
    ostatní chybějící na výchozí hodnotu.
    """
    alg = QgsApplication.processingRegistry().algorithmById(alg_id)
    if not alg:
        return parameters

    defs = {p.name(): p for p in alg.parameterDefinitions()}

    for k in [k for k in parameters if k not in defs]:
        print(f"  - parametr {k} algoritmus nezná, vynechávám")
        del parameters[k]

    for name, p in defs.items():
        if name in parameters or p.isDestination():
            continue
        if isinstance(p, QgsProcessingParameterBoolean):
            parameters[name] = bool(p.defaultValue()) if p.defaultValue() is not None else False
        elif p.defaultValue() is not None:
            parameters[name] = p.defaultValue()

    return parameters


# ---------------------------------------------------------------------------
# Barvy vrstev v tabulce LAYER
# ---------------------------------------------------------------------------
# QGIS zapisuje všem vrstvám v tabulce LAYER barvu 62 = 1 (červená).
# Prvky mají barvu vlastní, ale ve správci vrstev a u všeho, co je
# "DleHlad" (ByLayer), je pak všechno červené. Proto se barva vrstvy po
# exportu přepíše na barvu jejího symbolu.

# Základní barvy ACI pro přibližnou hodnotu ve skupině 62
# (skutečná barva jde do skupiny 420 jako true color)
_ACI_ZAKLAD = {
    1: (255, 0, 0), 2: (255, 255, 0), 3: (0, 255, 0), 4: (0, 255, 255),
    5: (0, 0, 255), 6: (255, 0, 255), 7: (255, 255, 255), 8: (128, 128, 128),
    9: (192, 192, 192), 250: (51, 51, 51), 251: (80, 80, 80), 252: (105, 105, 105),
    253: (130, 130, 130), 254: (190, 190, 190), 255: (255, 255, 255),
}


def _nejblizsi_aci(rgb):
    r, g, b = rgb
    if r == g == b and r in (0, 255):
        return 7  # černá/bílá -> 7 (AutoCAD ji přepíná podle pozadí)
    return min(_ACI_ZAKLAD, key=lambda i: sum((a - c) ** 2 for a, c in zip(_ACI_ZAKLAD[i], rgb)))


def _dxf_nazev_vrstvy(nazev):
    """Název vrstvy tak, jak ho zapíše QgsDxfExport."""
    try:
        from qgis.core import QgsDxfExport
        return QgsDxfExport.dxfLayerName(nazev)
    except Exception:
        return re.sub(r"[<>/\\\":;?*|=',]", "_", nazev)


def _symbol_pro_meritko(renderer, scale):
    """Symbol, kterým se vrstva vykreslí v daném měřítku (první vhodný)."""
    if renderer is None:
        return None
    if isinstance(renderer, QgsRuleBasedRenderer):
        for r in renderer.rootRule().children():
            if r.active() and r.symbol() and r.isScaleOK(scale):
                return r.symbol()
        return None
    typ = renderer.type()
    if typ == "categorizedSymbol" and renderer.categories():
        return renderer.categories()[0].symbol()
    if typ == "graduatedSymbol" and renderer.ranges():
        return renderer.ranges()[0].symbol()
    if hasattr(renderer, 'symbol'):
        try:
            return renderer.symbol()
        except Exception:
            return None
    return None


def barvy_vrstev(vector_layers, scale):
    """{název vrstvy v DXF: (r, g, b)} podle aktuální (invertované) symbologie."""
    barvy = {}
    for layer in vector_layers:
        symbol = _symbol_pro_meritko(layer.renderer(), scale)
        if symbol is None:
            continue
        c = symbol.color()
        barvy[_dxf_nazev_vrstvy(layer.name())] = (c.red(), c.green(), c.blue())
    return barvy


# Standardní tloušťky čar DXF (skupina 370) v setinách mm
_TLOUSTKY = (0, 5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80,
             90, 100, 106, 120, 140, 158, 200, 211)

BYLAYER_ACI = 256


def _sirka_na_tloustku(sirka, scale):
    """
    Šířka polylinie (skupina 43, mapové jednotky = metry) -> tloušťka čáry
    (skupina 370, setiny mm na papíře) při daném měřítku.
    """
    if not sirka or sirka <= 0:
        return None
    setiny_mm = sirka * 1000.0 / scale * 100.0
    return min(_TLOUSTKY[1:], key=lambda t: abs(t - setiny_mm))


def _fmt(kod, hodnota, eol):
    return [f"{kod:>3}{eol}", f"{hodnota}{eol}"]


class _Entita:
    """Jedna entita jako seznam dvojic [řádek kódu, řádek hodnoty]."""

    def __init__(self, pary):
        self.pary = pary

    @staticmethod
    def kod(par):
        return par[0].strip()

    @staticmethod
    def hodnota(par):
        return par[1].strip()

    def typ(self):
        return self.hodnota(self.pary[0])

    def konec_spolecne_casti(self):
        """Index první dvojice za společnou částí (AcDbEntity)."""
        for i, p in enumerate(self.pary[1:], 1):
            if self.kod(p) == '100' and self.hodnota(p) != 'AcDbEntity':
                return i
        return len(self.pary)

    def najdi(self, kod, od=1, do=None):
        do = len(self.pary) if do is None else do
        for i in range(od, do):
            if self.kod(self.pary[i]) == kod:
                return i
        return None

    def ziskej(self, kod, od=1, do=None):
        i = self.najdi(kod, od, do)
        return self.hodnota(self.pary[i]) if i is not None else None

    def vlastnosti(self, scale, sirka_jako_tloustka):
        """(vrstva, barva, typ čáry, tloušťka) - None = DleHlad / není zadáno."""
        k = self.konec_spolecne_casti()
        vrstva = self.ziskej('8', 1, k)
        aci = self.ziskej('62', 1, k)
        rgb = self.ziskej('420', 1, k)
        barva = None
        if aci is not None and int(aci) not in (0, BYLAYER_ACI):
            barva = (int(aci), int(rgb) if rgb is not None else None)
        ltyp = self.ziskej('6', 1, k)
        if ltyp is not None and ltyp.upper() in ('BYLAYER', 'BYBLOCK'):
            ltyp = None
        lw = self.ziskej('370', 1, k)
        lw = int(lw) if lw is not None and int(lw) >= 0 else None
        if sirka_jako_tloustka and self.typ() == 'LWPOLYLINE':
            sirka = self.ziskej('43', k)
            if sirka is not None:
                lw = _sirka_na_tloustku(float(sirka), scale)
        return vrstva, barva, ltyp, lw

    def odstran(self, kod, od=1, do=None):
        i = self.najdi(kod, od, do)
        if i is not None:
            del self.pary[i]
            return True
        return False

    def nastav(self, kod, hodnota, eol):
        """Nastaví/vloží skupinu ve společné části."""
        k = self.konec_spolecne_casti()
        i = self.najdi(kod, 1, k)
        if i is not None:
            self.pary[i] = _fmt(kod, hodnota, eol)
        else:
            self.pary.insert(k, _fmt(kod, hodnota, eol))


def _rozdel(radky):
    """Řádky -> seznam dvojic. Lichý zbytek (prázdný konec souboru) vrátí zvlášť."""
    pary = [[radky[i], radky[i + 1]] for i in range(0, len(radky) - 1, 2)]
    zbytek = radky[len(pary) * 2:]
    return pary, zbytek


def _entity(pary):
    """Seskupí dvojice do entit podle skupiny 0."""
    vysledek, aktualni = [], None
    for p in pary:
        if p[0].strip() == '0':
            aktualni = []
            vysledek.append(aktualni)
        if aktualni is None:
            aktualni = []
            vysledek.append(aktualni)
        aktualni.append(p)
    return [_Entita(e) for e in vysledek]


def odstran_prazdne_hladiny(text):
    """
    Odstraní z tabulky LAYER hladiny, na které neodkazuje žádná entita
    (v ENTITIES ani v blocích) ani $CLAYER. Hladina "0" zůstává vždy.
    """
    radky = text.split('\n')
    eol = '\r' if radky and radky[0].endswith('\r') else ''
    pary, zbytek = _rozdel(radky)
    entity = _entity(pary)

    pouzite = {'0'}
    sekce = None
    for e in entity:
        t = e.typ()
        if t == 'SECTION':
            sekce = e.ziskej('2')
            if sekce == 'HEADER':
                # $CLAYER: dvojice 9/$CLAYER následovaná 8/<název>
                for i, p in enumerate(e.pary[:-1]):
                    if e.kod(p) == '9' and e.hodnota(p) == '$CLAYER':
                        pouzite.add(e.hodnota(e.pary[i + 1]))
            continue
        if t == 'ENDSEC':
            sekce = None
            continue
        if sekce in ('ENTITIES', 'BLOCKS'):
            vrstva = e.ziskej('8')
            if vrstva is not None:
                pouzite.add(vrstva)

    vystup_entit = []
    odstraneno = []
    tabulka_layer = None
    sekce = None
    for e in entity:
        t = e.typ()
        if t == 'SECTION':
            sekce = e.ziskej('2')
        elif t == 'ENDSEC':
            sekce = None
        if sekce == 'TABLES' and t == 'TABLE' and e.ziskej('2') == 'LAYER':
            tabulka_layer = e
        elif sekce == 'TABLES' and t == 'ENDTAB':
            tabulka_layer = None
        if sekce == 'TABLES' and t == 'LAYER' and e.ziskej('2') not in pouzite:
            odstraneno.append(e.ziskej('2'))
            continue
        vystup_entit.append(e)

    # počet záznamů v hlavičce tabulky LAYER (skupina 70)
    for e in vystup_entit:
        if e.typ() == 'TABLE' and e.ziskej('2') == 'LAYER':
            pocet = sum(1 for x in vystup_entit if x.typ() == 'LAYER')
            i70 = e.najdi('70')
            if i70 is not None:
                e.pary[i70] = _fmt('70', f"{pocet:>6}", eol)

    for n in odstraneno:
        print(f"  - odstraněna prázdná hladina: {n}")
    print(f"Hladiny: odstraněno {len(odstraneno)} prázdných")

    vystup = []
    for e in vystup_entit:
        for p in e.pary:
            vystup.extend(p)
    vystup.extend(zbytek)
    return '\n'.join(vystup)


def atributy_dle_vrstvy(text, barvy=None, scale=500, sirka_jako_tloustka=True):
    """
    Přesune co nejvíc vlastností entit do hladin (DleHlad / ByLayer):

    * pro každou hladinu se z entit v sekci ENTITIES zjistí nejčastější barva,
      typ čáry a tloušťka a zapíší se do tabulky LAYER,
    * entity, které se s hladinou shodují, dostanou barvu 256 (DleHlad),
      typ čáry a tloušťka se u nich vypustí (= DleHlad),
    * entity s odlišnou hodnotou si ji ponechají explicitně,
    * se sirka_jako_tloustka se šířka polylinií (43) převede na tloušťku čáry
      (370) a šířka se vynuluje - jinak by tloušťka nemohla být DleHlad.

    Hladiny bez entit dostanou barvu podle symbolu (barvy), jinak 7.
    Obsah bloků se nemění.
    """
    from collections import Counter, defaultdict

    radky = text.split('\n')
    eol = '\r' if radky and radky[0].endswith('\r') else ''
    pary, zbytek = _rozdel(radky)
    entity = _entity(pary)

    # --- sekce
    sekce = None
    oznaceni = []          # (entita, sekce)
    for e in entity:
        t = e.typ()
        if t == 'SECTION':
            sekce = e.ziskej('2')
        elif t == 'ENDSEC':
            oznaceni.append((e, None))
            sekce = None
            continue
        oznaceni.append((e, sekce))

    # --- 1. průchod: statistika entit po hladinách
    st_barva = defaultdict(Counter)
    st_ltyp = defaultdict(Counter)
    st_lw = defaultdict(Counter)
    for e, s in oznaceni:
        if s != 'ENTITIES' or e.typ() in ('SECTION', 'ENDSEC'):
            continue
        vrstva, barva, ltyp, lw = e.vlastnosti(scale, sirka_jako_tloustka)
        if vrstva is None:
            continue
        st_barva[vrstva][barva] += 1
        st_ltyp[vrstva][ltyp] += 1
        st_lw[vrstva][lw] += 1

    # Soubor už jednou zpracovaný (entity s barvou DleHlad) -> neměnit,
    # jinak by se hladinám přepočítaly barvy jen z výjimek
    for e, s in oznaceni:
        if s == 'ENTITIES' and e.typ() not in ('SECTION', 'ENDSEC'):
            aci = e.ziskej('62', 1, e.konec_spolecne_casti())
            if aci is not None and int(aci) == BYLAYER_ACI:
                print("Hladiny: soubor už má atributy DleHlad, ponechávám")
                return text

    def nejcastejsi(counter):
        # None = vlastnost u entity není (např. typ čáry u šrafy) -> nehlasuje
        kandidati = [(n, v) for v, n in counter.items() if v is not None]
        return max(kandidati, key=lambda x: x[0])[1] if kandidati else None

    hladiny = {}
    for vrstva in set(st_barva) | set(st_ltyp) | set(st_lw):
        hladiny[vrstva] = (
            nejcastejsi(st_barva[vrstva]),
            nejcastejsi(st_ltyp[vrstva]),
            nejcastejsi(st_lw[vrstva]),
        )

    # --- 2. průchod: entity
    zmen = Counter()
    for e, s in oznaceni:
        if s != 'ENTITIES' or e.typ() in ('SECTION', 'ENDSEC'):
            continue
        vrstva, barva, ltyp, lw = e.vlastnosti(scale, sirka_jako_tloustka)
        if vrstva not in hladiny:
            continue
        h_barva, h_ltyp, h_lw = hladiny[vrstva]
        k = e.konec_spolecne_casti()

        if barva is not None and barva == h_barva:
            e.odstran('420', 1, e.konec_spolecne_casti())
            e.nastav('62', f"{BYLAYER_ACI:>6}", eol)
            zmen['barva'] += 1

        if ltyp is not None and ltyp == h_ltyp:
            e.odstran('6', 1, e.konec_spolecne_casti())
            zmen['typ čáry'] += 1

        if sirka_jako_tloustka and e.typ() == 'LWPOLYLINE':
            k = e.konec_spolecne_casti()
            i43 = e.najdi('43', k)
            if i43 is not None:
                e.pary[i43] = _fmt('43', '0.0', eol)
        k = e.konec_spolecne_casti()
        if lw is not None and lw == h_lw:
            e.odstran('370', 1, k)
            zmen['tloušťka'] += 1
        elif lw is not None:
            e.nastav('370', f"{lw:>6}", eol)

    # --- tabulka LAYER
    nastaveno = 0
    for e, s in oznaceni:
        if s != 'TABLES' or e.typ() != 'LAYER':
            continue
        nazev = e.ziskej('2')
        h_barva, h_ltyp, h_lw = hladiny.get(nazev, (None, None, None))

        # barva
        if h_barva is None and barvy and nazev in barvy:
            rgb = barvy[nazev]
            h_barva = (_nejblizsi_aci(rgb), (rgb[0] << 16) | (rgb[1] << 8) | rgb[2])
        aci, rgb = h_barva if h_barva else (7, None)
        i62 = e.najdi('62')
        vypnuta = i62 is not None and e.hodnota(e.pary[i62]).startswith('-')
        if vypnuta:
            aci = -abs(aci)
        e.odstran('420', 1)
        if i62 is not None:
            e.pary[i62] = _fmt('62', f"{aci:>6}", eol)
        else:
            i62 = len(e.pary)
            e.pary.append(_fmt('62', f"{aci:>6}", eol))
        if rgb is not None:
            e.pary.insert(i62 + 1, _fmt('420', rgb, eol))

        # typ čáry
        if h_ltyp:
            i6 = e.najdi('6')
            if i6 is not None:
                e.pary[i6] = _fmt('6', h_ltyp, eol)
            else:
                e.pary.append(_fmt('6', h_ltyp, eol))

        # tloušťka
        if h_lw is not None:
            i370 = e.najdi('370')
            if i370 is not None:
                e.pary[i370] = _fmt('370', f"{h_lw:>6}", eol)
            else:
                i6 = e.najdi('6')
                pozice = i6 + 1 if i6 is not None else len(e.pary)
                e.pary.insert(pozice, _fmt('370', f"{h_lw:>6}", eol))
        nastaveno += 1

    print(f"Hladiny: nastaveno {nastaveno}; entity převedené na DleHlad - "
          + ", ".join(f"{k}: {v}" for k, v in zmen.items()))

    vystup = []
    for e in entity:
        for p in e.pary:
            vystup.extend(p)
    vystup.extend(zbytek)
    return '\n'.join(vystup)


# ---------------------------------------------------------------------------
# Úprava výsledného DXF
# ---------------------------------------------------------------------------

_ACADVER_RE = re.compile(r'(\$ACADVER[ \t]*\r?\n[ \t]*1[ \t]*\r?\n)AC\d{4}')


def uprav_dxf(output_dxf, barvy=None, scale=500, sirka_jako_tloustka=True):
    """
    Nastaví verzi DXF na AC1021 (AutoCAD 2007) a převede soubor do UTF-8.

    Od AC1021 je DXF vždy v UTF-8. Starší verze (AC1015 z QGIS 3, AC1018 z QGIS 4)
    se čtou podle $DWGCODEPAGE (ANSI_1250), takže UTF-8 obsah bez změny verze
    AutoCAD odmítne otevřít.
    """
    print("Modifikuji DXF soubor - nastavení verze AC1021 a konverze do UTF-8...")
    try:
        with open(output_dxf, 'rb') as f:
            content = f.read()

        # Nejdřív UTF-8 (soubor už mohl být převeden), jinak cp1250 z QGIS
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            text = content.decode('cp1250')

        text, n = _ACADVER_RE.subn(r'\1AC1021', text, count=1)
        if n == 0:
            print("  - $ACADVER v hlavičce nenalezen, soubor ponechávám beze změny!")
            return False

        text = odstran_prazdne_hladiny(text)
        text = atributy_dle_vrstvy(text, barvy, scale, sirka_jako_tloustka)

        with open(output_dxf, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        print("Soubor převeden do UTF-8 a nastaven na AC1021")
        return True
    except Exception as e:
        print(f"Chyba při úpravě DXF souboru: {e}")
        return False


def pocet_entit(output_dxf):
    """Vrátí počet entit v sekci ENTITIES (pro kontrolu prázdného exportu)."""
    with open(output_dxf, encoding='utf-8', errors='replace') as f:
        lines = [l.strip() for l in f.read().splitlines()]
    pocet, v_entities = 0, False
    for i in range(0, len(lines) - 1, 2):
        code, value = lines[i], lines[i + 1]
        if code != '0':
            if v_entities is None and code == '2':
                v_entities = (value == 'ENTITIES')
            continue
        if value == 'SECTION':
            v_entities = None
        elif value == 'ENDSEC':
            if v_entities:
                break
            v_entities = False
        elif v_entities:
            pocet += 1
    return pocet


# ---------------------------------------------------------------------------
# Export přes QgsDxfExport API (stejná cesta jako Projekt > Exportovat do DXF)
# ---------------------------------------------------------------------------

def _enum(*kandidati):
    """Vrátí první existující hodnotu enumu (QGIS 4 scoped / QGIS 3 unscoped)."""
    for obj, cesta in kandidati:
        try:
            for cast in cesta.split('.'):
                obj = getattr(obj, cast)
            return obj
        except AttributeError:
            continue
    raise AttributeError(f"Žádný z enumů nenalezen: {[c for _, c in kandidati]}")


def export_dxf_api(vector_layers, output_dxf, crs, symbology_scale=500, encoding='cp1250'):
    """
    Export přímo přes QgsDxfExport nad vrstvami z projektu.
    Na rozdíl od native:dxfexport se vrstvy neklonují, takže funguje
    i s dočasnými (memory) vrstvami a s upravenou symbologií.
    """
    from qgis.core import Qgis, QgsDxfExport, QgsMapSettings, QgsRectangle, QgsCoordinateTransform
    from qgis.PyQt.QtCore import QFile, QIODevice

    project = QgsProject.instance()

    # Rozsah = sjednocení rozsahů vrstev v cílovém CRS
    extent = QgsRectangle()
    extent.setNull()
    for l in vector_layers:
        e = l.extent()
        if e.isNull() or l.featureCount() == 0:
            continue
        if l.crs() != crs:
            e = QgsCoordinateTransform(l.crs(), crs, project).transformBoundingBox(e)
        extent.combineExtentWith(e)

    ms = QgsMapSettings()
    ms.setLayers(vector_layers)
    ms.setDestinationCrs(crs)
    ms.setTransformContext(project.transformContext())
    if not extent.isNull():
        ms.setExtent(extent)

    dxf = QgsDxfExport()
    dxf.setMapSettings(ms)
    dxf.setDestinationCrs(crs)
    dxf.setSymbologyScale(symbology_scale)
    dxf.setSymbologyExport(_enum(
        (Qgis, 'FeatureSymbologyExport.PerSymbolLayer'),
        (QgsDxfExport, 'SymbolLayerSymbology'),
    ))
    dxf.setForce2d(False)
    dxf.setLayerTitleAsName(False)
    dxf.addLayers([QgsDxfExport.DxfLayer(l) for l in vector_layers])

    mode = _enum((QIODevice, 'OpenModeFlag.WriteOnly'), (QIODevice, 'WriteOnly')) | \
           _enum((QIODevice, 'OpenModeFlag.Truncate'), (QIODevice, 'Truncate'))
    f = QFile(output_dxf)
    if not f.open(mode):
        raise IOError(f"Nelze otevřít {output_dxf} pro zápis")
    try:
        res = dxf.writeToFile(f, encoding)
    finally:
        f.close()

    success = _enum((QgsDxfExport, 'ExportResult.Success'), (QgsDxfExport, 'Success'))
    if res != success:
        raise RuntimeError(f"QgsDxfExport skončil s výsledkem {res}")


def export_dxf_processing(vector_layers, output_dxf, crs, symbology_scale=500, encoding='cp1250'):
    """Záložní export přes algoritmus native:dxfexport."""
    layer_params = [{
        'layer': l.id(),
        'attributeIndex': -1,
        'overriddenLayerName': '',
        'buildDataDefinedBlocks': False,
        'dataDefinedBlocksMaximumNumberOfClasses': -1,
    } for l in vector_layers]

    parameters = priprav_parametry({
        'LAYERS': layer_params,
        'SYMBOLOGY_MODE': 2,              # 0 = bez symbologie, 1 = feature, 2 = symbol layer
        'SYMBOLOGY_SCALE': symbology_scale,
        'ENCODING': encoding,
        'CRS': crs,
        'SELECTED_FEATURES_ONLY': False,
        'USE_LAYER_TITLE': False,
        'FORCE_2D': False,
        'MTEXT': True,
        'EXPORT_LINES_WITH_ZERO_WIDTH': False,
        'OUTPUT': output_dxf,
    })
    processing.run("native:dxfexport", parameters)


# ---------------------------------------------------------------------------
# Hlavní funkce
# ---------------------------------------------------------------------------

def export_layers_to_dxf_with_inverted_grayscale(output_filename, selected_layers=None,
                                                 symbology_scale=None,
                                                 doplnit_chybejici_meritka=False,
                                                 sirka_jako_tloustka=True):
    """
    Exportuje viditelné vrstvy do DXF s invertovanými odstíny šedi.
    Poté upraví formát DXF z AC1015 na AC1021 a převede soubor do UTF-8.

    Args:
        output_filename (str): Cesta a název výstupního souboru (bez přípony)
        selected_layers (list): Seznam názvů vrstev k exportu (None = všechny viditelné)
        symbology_scale (float): Měřítko, pro které se vyhodnocují styly
            (viditelnost pravidel, velikost symbolů, převod šířek na tloušťky).
            None = aktuální měřítko mapového okna (jak ho ukazuje stavový řádek).
        doplnit_chybejici_meritka (bool): Exportovat i prvky, které pro symbology_scale
            nemají styl (zobrazí se nejpodrobnějším dostupným stylem).
            False = DXF odpovídá tomu, co je vidět v mapě při symbology_scale.
        sirka_jako_tloustka (bool): Šířku polylinií převést na tloušťku čáry (370),
            aby mohla být DleHlad. False = ponechat šířku polylinie jako v QGIS.
    """

    # Měřítko exportu = aktuální měřítko mapy, pokud není zadáno
    if symbology_scale is None:
        symbology_scale = iface.mapCanvas().scale()
        print(f"Měřítko exportu podle mapy: 1:{symbology_scale:,.0f}".replace(",", " "))
    else:
        print(f"Měřítko exportu: 1:{symbology_scale:,.0f}".replace(",", " "))

    # Výstupní adresář
    output_dir = os.path.dirname(output_filename)
    if not output_dir:
        output_dir = os.getcwd()
        output_filename = os.path.join(output_dir, output_filename)
    os.makedirs(output_dir, exist_ok=True)

    project = QgsProject.instance()

    # Výběr vrstev
    layers_to_export = []
    if selected_layers:
        for layer_name in selected_layers:
            layers = project.mapLayersByName(layer_name)
            if layers:
                layers_to_export.append(layers[0])
    else:
        for node in project.layerTreeRoot().findLayers():
            if node.isVisible() and node.layer() is not None:
                layers_to_export.append(node.layer())

    if not layers_to_export:
        print("Žádné vrstvy k exportu!")
        return False

    print(f"Nalezeno {len(layers_to_export)} vrstev k exportu.")

    # Jen vektorové vrstvy (isinstance funguje v QGIS 3 i 4)
    vector_layers = [l for l in layers_to_export if isinstance(l, QgsVectorLayer) and l.isValid()]
    for l in [l for l in vector_layers if l.featureCount() == 0]:
        print(f"Vynechávám prázdnou vrstvu: {l.name()}")
    vector_layers = [l for l in vector_layers if l.featureCount() != 0]
    if not vector_layers:
        print("Žádné vektorové vrstvy ke zpracování!")
        return False

    # Záloha rendererů
    original_renderers = {l.id(): l.renderer().clone() for l in vector_layers if l.renderer()}

    export_success = False
    try:
        # Inverze šedých barev
        for layer in vector_layers:
            print(f"Zpracovávám vrstvu: {layer.name()}")
            renderer = layer.renderer()
            if renderer is None:
                continue
            invertuj_renderer(renderer)
            if doplnit_chybejici_meritka:
                rozsir_meritka(layer, symbology_scale)
            layer.triggerRepaint()

        iface.mapCanvas().refresh()
        print("Inverze šedých barev dokončena. Zahajuji export...")
        barvy = barvy_vrstev(vector_layers, symbology_scale)

        output_dxf = output_filename + ".dxf"
        if os.path.exists(output_dxf):
            os.remove(output_dxf)

        layer_crs = QgsCoordinateReferenceSystem("EPSG:5514")
        if layer_crs.isValid():
            print(f"CRS Description: {layer_crs.description()}")
        else:
            print("Invalid CRS!")

        for layer in vector_layers:
            print(f"Přidávám vrstvu: {layer.name()} ({layer.featureCount()} prvků)")

        # 1) přímo přes QgsDxfExport, 2) při chybě nebo prázdném výsledku přes processing
        try:
            export_dxf_api(vector_layers, output_dxf, layer_crs, symbology_scale)
            n = pocet_entit(output_dxf) if os.path.exists(output_dxf) else 0
            print(f"Export přes QgsDxfExport: {n} entit")
            if n == 0:
                raise RuntimeError("prázdná sekce ENTITIES")
        except Exception as e:
            print(f"  - QgsDxfExport selhal ({e}), zkouším native:dxfexport...")
            if os.path.exists(output_dxf):
                os.remove(output_dxf)
            export_dxf_processing(vector_layers, output_dxf, layer_crs, symbology_scale)

        if os.path.exists(output_dxf):
            print(f"Soubor existuje na cestě: {output_dxf}")
            print(f"Velikost souboru: {os.path.getsize(output_dxf)} bytů")
            export_success = uprav_dxf(output_dxf, barvy, symbology_scale, sirka_jako_tloustka)
            n = pocet_entit(output_dxf)
            print(f"Počet entit v ENTITIES: {n}")
            if n == 0:
                print("  - VAROVÁNÍ: sekce ENTITIES je prázdná, žádné prvky nebyly exportovány!")
                for layer in vector_layers:
                    print(f"    {layer.name()}: {layer.featureCount()} prvků, "
                          f"CRS {layer.crs().authid()}, "
                          f"scale-based: {layer.hasScaleBasedVisibility()}")
        else:
            print(f"Soubor NEBYL vytvořen na cestě: {output_dxf}")

    except Exception as e:
        print(f"Došlo k chybě během exportu: {e}")

    finally:
        # Obnovení původních rendererů proběhne vždy, i při chybě
        print("Obnovuji původní barvy vrstev...")
        for layer in vector_layers:
            if layer.id() in original_renderers:
                layer.setRenderer(original_renderers[layer.id()])
                layer.triggerRepaint()
        iface.mapCanvas().refresh()

    if export_success:
        print("Export úspěšně dokončen a původní barvy vrstev obnoveny.")
    else:
        print("Export se nezdařil, ale původní barvy vrstev byly obnoveny.")
    return export_success
