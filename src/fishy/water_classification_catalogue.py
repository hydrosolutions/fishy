"""SOURCE_ROWS : tuple[SourceRow, ...] = held Order 111 numerical-table transcription.

Derived catalogue of the 4 June 2025 Order 111-НҚ CAWater replica, pages 2–8.
This is not authenticated publisher-direct evidence or a current-law finding.
Cell strings retain printed operators, decimal commas, qualifications and baseline
chemical digits. Layout-only line wrapping and letter spacing are collapsed.
An empty string is an empty source field; a printed hyphen remains a hyphen.
Pages identify the numerical cells, not necessarily the start of a split name.
No numerical threshold interpretation, unit conversion or missing-unit inference
is performed here. Merged temperature cells are repeated with a layout note.
"""

from dataclasses import dataclass

SOURCE_DOCUMENT = "kz_order111_water_quality_2025_ru_cawater.pdf"
SOURCE_SHA256 = "c8e0aa22c3c2eb35269e858120ffda7d61de409b3c7e702cb2cb9b9f2c126d38"
SOURCE_URL = "https://cawater-info.net/bk/water_law/pdf/kz-p111-2025.pdf"
SOURCE_TABLE = "Единая система классификации воды в поверхностных водных объектах и (или) их частях"
SOURCE_NOTES = (
    "CAWater replica; not authenticated publisher-direct evidence. Currency is not established.",
    "* Numerical values apply to rivers, canals and in-channel reservoirs; not seas or lakes, including the Caspian Sea, Aral Sea and Lake Balkhash (p8).",
    "** Use categories are described in Table 1 and differentiated in Table 2 (p8); these do not resolve numerical cell interpretation.",
    "Table 1 permits class-4 drinking use with intensive treatment (pp9–10), while Table 2 marks it negative (p11). Neither attribution is silently preferred.",
    "Separate sanitary cross-references: Order ҚР ДСМ-138 of 24 November 2022 and Order ҚР ДСМ-44 of 16 May 2022 (pp10–11). A numerical classification is not sanitary compliance.",
)


@dataclass(frozen=True)
class SourceRow:
    """One printed indicator/form with six unparsed class cells, in source order."""

    identifier: str
    printed_row: str
    name: str
    symbol: str
    unit: str
    cells: tuple[str, ...]
    page: int
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.cells, tuple) or len(self.cells) != 6:
            raise ValueError("source row requires six immutable raw cells")
        if any(not isinstance(cell, str) for cell in self.cells):
            raise TypeError("source cells must be strings")
        if not isinstance(self.notes, tuple) or any(not isinstance(note, str) for note in self.notes):
            raise TypeError("source notes must be an immutable tuple of strings")
        if not self.identifier or not self.printed_row or not self.name:
            raise ValueError("source row identity and name are required")
        if not isinstance(self.page, int) or isinstance(self.page, bool) or not 2 <= self.page <= 8:
            raise ValueError("numerical source table occupies pages 2 through 8")


SOURCE_ROWS: tuple[SourceRow, ...] = (
    SourceRow(
        "order111:01",
        "1",
        "Температура",
        "Т воды",
        "0C",
        ("Летом 20-280C", "Летом 20-280C", "Летом 20-280C", "Летом 20-280C", "Зимой 5-80C", "Зимой 5-80C"),
        2,
        (
            "Two merged cells span classes 1–4 (summer) and 5–6 (winter); repeated text records layout, not class-specific temperature thresholds.",
            "The replica prints baseline 0C and 280C/80C; temperature typography is not repaired.",
        ),
    ),
    SourceRow(
        "order111:02",
        "2",
        "Растворенный кислород",
        "О2",
        "мг О2/л",
        ("≥6", "≥4", "≥4", "4", "4", "≤3"),
        2,
        ("Classes 4 and 5 print bare 4, unlike explicit ≥4 in classes 2 and 3; direction is not inferred.",),
    ),
    SourceRow(
        "order111:03",
        "3",
        "Насыщение кислородом",
        "О2",
        "% насыщения О2/л",
        (">90%", "≥80%", "≥60%", "≥40%", "<40%", "≤20 %"),
        2,
        (),
    ),
    SourceRow(
        "order111:04",
        "4",
        "Биохимическое потребление кислорода (5 суток)",
        "БПК5",
        "мг О2/л",
        ("2,1", "2,1", "3,0", "5,0", "6,0", ">6,0"),
        2,
        (),
    ),
    SourceRow(
        "order111:05",
        "5",
        "Биохимическое потребление кислорода (полное)",
        "БПКполн",
        "мг О2/л",
        ("3,0", "3,0", "6,0", "7,0", "8,0", ">8,0"),
        2,
        (),
    ),
    SourceRow(
        "order111:06",
        "6",
        "Химическое потребление кислорода (перманганатное)",
        "ХПК (перм)",
        "мг О2/л",
        ("<7,0", "7,0", "15,0", "20,0", "20,0", ">20,0"),
        2,
        (),
    ),
    SourceRow(
        "order111:07",
        "7",
        "Химическое потребление кислорода (бихроматное)",
        "ХПК (бихр)",
        "мг О2/л",
        ("≤15,0", "15,0", "30,0", "35,0", "40,0", ">40,0"),
        3,
        (),
    ),
    SourceRow(
        "order111:08",
        "8",
        "рН",
        "",
        "",
        ("6,5-8,5", "6,5-8,5", "6,0-9,0", "6,0-9,0", "6,0-9,0", "<6,0->9,0"),
        3,
        ("Class 6 retains the printed compound <6,0->9,0; it is not a single ordered range.",),
    ),
    SourceRow("order111:09", "9", "Запах", "", "балл", ("<2,0", "2,0", "2,0", "4,0", "4,0", "5,0"), 3, ()),
    SourceRow("order111:10", "10", "Цветность", "", "градус", ("<20", "20", "30", "40", "80", ">80"), 3, ()),
    SourceRow("order111:11", "11", "Прозрачность", "", "см", (">20", "20", "3-10", "2,0", "2,0", "<2,0"), 3, ()),
    SourceRow(
        "order111:12",
        "12",
        "Взвешенные вещества",
        "",
        "мг/л",
        ("Сфон.+ 0,25", "Сфон.+ 0,75", "Сфон.+ 1,0", "Сфон.+ 5,0", "Сфон.+ 10,0", ">Сфон. 10,0"),
        3,
        (
            "Сфон means background concentration (abbreviations, p12). Class 6 lacks the plus sign printed in classes 1–5.",
        ),
    ),
    SourceRow(
        "order111:13",
        "13",
        "Минерализация общая; Сумма ионов; Сухой остаток; Соленость",
        "Минобщ",
        "мг/л",
        ("≤1000", "1000", "1300", "1500", "≤2000", ">2000"),
        3,
        (),
    ),
    SourceRow(
        "order111:14",
        "14",
        "Удельная электропроводность",
        "",
        "мкСм/см",
        ("50", "500", "1000", "1500", "1500", ">1500"),
        3,
        (),
    ),
    SourceRow(
        "order111:15",
        "15",
        "Окислительно восстановительный потенциал2",
        "ОВП1",
        "Eh, мВ",
        ("400", "500", "600", "700", "700", ">700"),
        3,
        (
            "Trailing numeric markers 2 in the name and 1 in the symbol have no explanatory footnotes in the held replica.",
        ),
    ),
    SourceRow(
        "order111:16", "16", "Сульфаты", "SO42-", "мг/л", ("<100", "100", "500", "≤600", "≤1500", ">1500"), 3, ()
    ),
    SourceRow("order111:17", "17", "Хлориды", "Cl-", "мг/л", ("300", "350", "350", "400", "400", ">400"), 3, ()),
    SourceRow(
        "order111:18",
        "18",
        "Кальций",
        "Ca2+",
        "мг/л",
        ("180", "180", "170", "150", "150", "180 (150 ***)"),
        3,
        (
            "*** 150 мг/л распространяется к содержанию кальция при использовании воды в промышленных целях (риск образования накипи в промышленных установках). (p8)",
        ),
    ),
    SourceRow("order111:19", "19", "Магний", "Mg2+", "мг/л", ("≤20,0", "20,0", "60,0", "≤100,0", "100", ">100"), 3, ()),
    SourceRow(
        "order111:20", "20", "Натрий", "Na+", "мг/л", ("120,0", "200,0", "200,0", "200,0", "200,0", ">200,0"), 3, ()
    ),
    SourceRow("order111:21", "21", "Калий", "K+", "мг/л", ("50,0", "50,0", "50,0", "<100,0", "100,0", ">100,0"), 3, ()),
    SourceRow(
        "order111:22",
        "22",
        "Щелочность2",
        "HCO3-",
        "мг CaCO3/л",
        ("<40,0", "40,0-<50,0", "50,0-<100,0", "100,0-<200,0", "200,0", ">200"),
        3,
        ("The trailing marker 2 has no explanatory footnote in the held replica.",),
    ),
    SourceRow(
        "order111:23",
        "23",
        "Жесткость3",
        "",
        "мг-экв/л",
        ("<4,0", "6", "9", "10", "13", "≥15"),
        4,
        ("The trailing marker 3 has no explanatory footnote in the held replica.",),
    ),
    SourceRow(
        "order111:24", "24", "Двуокись углерода", "CO2", "мг/л", ("0,2", "0,4", "1,0", "2,0", "3,0", "≥4,0"), 4, ()
    ),
    SourceRow(
        "order111:25", "25", "Общий азот", "Nобщ", "мг N/л", ("1,5", "4,0", "8,0", "20,0", "20,0", ">20,0"), 4, ()
    ),
    SourceRow(
        "order111:26", "26", "Нитрат ион", "NO3-", "мг/л", ("≤40,0", "40,0", "45,0", "45,0", "45,0", ">45,0"), 4, ()
    ),
    SourceRow("order111:27", "27", "Нитрит ион", "NO2-", "мг/л", ("0,1", "3,3", "3,3", "3,3", "5,0", ">5,0"), 4, ()),
    SourceRow("order111:28", "28", "Аммоний ион", "NH4+", "мг/л", ("≤0,5", "0,5", "1,0", "2,0", "2,6", ">2,6"), 4, ()),
    SourceRow(
        "order111:29", "29", "Аммиак", "NH3·nH2O", "мг/л", ("0,05", "0,05", "0,10", "0,20", "0,26", ">0,26"), 4, ()
    ),
    SourceRow("order111:30", "30", "Аммиак по азоту", "", "мг/л", ("<2,0", "2,0", "2,0", "2,3", "2,7", ">2,7"), 4, ()),
    SourceRow(
        "order111:31", "31", "Фосфор общий", "Робщ", "мг Р/л", ("0,1", "0,2", "0,4", "1,0", "1,0", ">1,0"), 4, ()
    ),
    SourceRow(
        "order111:32",
        "32",
        "Фосфаты",
        "РО43-",
        "мг/л",
        ("0,2", "0,4", "0,7 (3,5)****", "1,0", "≤3,5", ">3,5"),
        4,
        ("**** для показателей поверхностных вод в пределах города Астана (p8)",),
    ),
    SourceRow(
        "order111:33",
        "33",
        "Фосфор треххлористый",
        "PCl3",
        "мг/л",
        ("0,01", "0,01", "0,25", "0,60", ">0,60", ">0,60"),
        4,
        ("Classes 5 and 6 both print >0,60; no unique class separation is supplied.",),
    ),
    SourceRow("order111:34", "34", "Бор", "В", "мг/л", ("≤0,5", "0,5", "0,7", "1,3", "2,0", ">2,0"), 4, ()),
    SourceRow("order111:35", "35", "Кремний", "Si", "мг/л", ("10,0", "10,0", "12,0", "12,0", "12,0", ">12,0"), 4, ()),
    SourceRow("order111:36", "36", "Алюминий", "Al", "мг/л", ("0,04", "0,04", "0,50", "0,50", "0,50", ">0,50"), 4, ()),
    SourceRow(
        "order111:37", "37", "Бериллий", "Ве", "мг/л", ("0,0001", "0,0002", "0,0002", "0,002", "0,004", ">0,004"), 4, ()
    ),
    SourceRow(
        "order111:38-total", "38", "Железо общее", "Feобщ", "мг/л", ("0,1", "0,1", "0,3", "0,5", "0,5", ">0,5"), 4, ()
    ),
    SourceRow(
        "order111:38-2",
        "38",
        "Железо (2+)",
        "Fe2+",
        "мг/л",
        ("≤0,005", "0,005", "0,01", "0,02", "0,02", ">0,02"),
        4,
        (),
    ),
    SourceRow(
        "order111:38-3", "38", "Железо (3+)", "Fe3+", "мг/л", ("≤0,01", "0,01", "0,02", "0,04", "0,05", ">0,05"), 4, ()
    ),
    SourceRow(
        "order111:39", "39", "Марганец (2+)", "Mn2+", "мг/л", ("0,01", "0,01", "0,10", "0,20", "0,30", ">0,30"), 4, ()
    ),
    SourceRow(
        "order111:40-total",
        "40",
        "Кадмий общий",
        "Cdобщ",
        "мг/л",
        ("0,005", "0,005", "0,025", "0,125", "0,125", ">0,125"),
        4,
        (),
    ),
    SourceRow(
        "order111:40-dissolved",
        "40",
        "Кадмий растворенный",
        "Cdраст",
        "мг/л",
        ("0,001", "0,001", "0,005", "0,025", "0,025", ">0,025"),
        4,
        (),
    ),
    SourceRow(
        "order111:41-pb-total",
        "41",
        "Свинец общий",
        "Pbобщ",
        "мг/л",
        ("0,12", "0,60", "0,60", "1,00", "1,00", ">1,00"),
        4,
        ("Printed row 41 is reused for mercury on p5; it is not silently renumbered. Lead row continues onto p5.",),
    ),
    SourceRow(
        "order111:41-pb-dissolved",
        "41",
        "Свинец растворенный",
        "Pbраст",
        "мг/л",
        ("0,006", "0,03", "0,03", "0,05", "0,05", ">0,05"),
        5,
        ("Continuation of the lead row printed 41 on p4; mercury independently repeats printed 41 on p5.",),
    ),
    SourceRow(
        "order111:41-hg-total",
        "41",
        "Ртуть общая",
        "Hgобщ",
        "мг/л",
        ("0,0001", "0,0005", "0,001", "0,001", "0,001", ">0,001"),
        5,
        ("The source repeats printed 41 for mercury after lead; printed 42 is absent.",),
    ),
    SourceRow(
        "order111:41-hg-dissolved",
        "41",
        "Ртуть растворенная",
        "Hgраст",
        "мг/л",
        ("0,00002", "0,0001", "0,0002", "0,0002", "0,0002", ">0,0002"),
        5,
        ("The source repeats printed 41 for mercury after lead; printed 42 is absent.",),
    ),
    SourceRow(
        "order111:43-total",
        "43",
        "Никель общий",
        "Niобщ",
        "мг/л",
        ("0,01", "0,025", "0,05", "0,10", "0,10", ">0,10"),
        5,
        (),
    ),
    SourceRow(
        "order111:43-dissolved",
        "43",
        "Никель растворенный",
        "Niраст",
        "мг/л",
        ("0,008", "0,020", "0,04", "0,08", "0,08", ">0,08"),
        5,
        (),
    ),
    SourceRow(
        "order111:44-total", "44", "Медь общая", "Cuобщ", "мг/л", ("0,002", "0,002", "2,0", "2,0", "2,4", ">2,4"), 5, ()
    ),
    SourceRow(
        "order111:44-dissolved",
        "44",
        "Медь растворенная",
        "Cuраст",
        "мг/л",
        ("0,001", "0,001", "1,0", "1,0", "1,2", ">1,2"),
        5,
        (),
    ),
    SourceRow(
        "order111:45-total",
        "45",
        "Цинк общий",
        "Znобщ",
        "мг/л",
        ("0,04", "0,04", "0,04", "0,12", "0,20", ">0,20"),
        5,
        (),
    ),
    SourceRow(
        "order111:45-dissolved",
        "45",
        "Цинк растворенный",
        "Znраст",
        "мг/л",
        ("0,01", "0,01", "0,01", "0,03", "0,05", ">0,05"),
        5,
        (),
    ),
    SourceRow(
        "order111:46-total",
        "46",
        "Кобальт общий",
        "Coобщ",
        "мг/л",
        ("0,01", "0,01", "0,1", "0,1", "0,1", ">0,1"),
        5,
        (),
    ),
    SourceRow(
        "order111:46-dissolved",
        "46",
        "Кобальт растворенный",
        "Coраст",
        "мг/л",
        ("0,005", "0,005", "0,05", "0,05", "0,05", ">0,05"),
        5,
        (),
    ),
    SourceRow(
        "order111:47-total",
        "47",
        "Молибден общий",
        "Мообщ",
        "мг/л",
        ("0,002", "0,002", "0,0040", "0,0050", "0,0050", ">0,0050"),
        5,
        (),
    ),
    SourceRow(
        "order111:47-dissolved",
        "47",
        "Молибден растворенный",
        "Мораст",
        "мг/л",
        ("0,001", "0,001", "0,0020", "0,0025", "0,0025", ">0,0025"),
        5,
        (),
    ),
    SourceRow(
        "order111:48-total", "48", "Хром общий", "Сrобщ", "мг/л", ("0,1", "0,1", "0,55", "0,55", "0,55", ">0,55"), 5, ()
    ),
    SourceRow(
        "order111:48-3", "48", "Хром (3+)", "Сr3+", "мг/л", ("0,07", "0,07", "0,15", "0,15", "0,30", ">0,30"), 5, ()
    ),
    SourceRow(
        "order111:48-6", "48", "Хром (6+)", "Сr6+", "мг/л", ("≤0,02", "0,02", "0,05", "0,10", "0,25", ">0,25"), 5, ()
    ),
    SourceRow(
        "order111:49",
        "49",
        "Фенолы (летучие)",
        "-",
        "мг/л",
        ("0,001", "0,001", "0,001", "0,002", "0,005", ">0,005"),
        5,
        (),
    ),
    SourceRow("order111:50", "50", "Фенолы", "-", "мг/л", ("0,001", "0,001", "0,005", "0,10", "0,10", ">0,10"), 5, ()),
    SourceRow(
        "order111:51", "51", "Нефтепродукты", "-", "мг/л", ("0,05", "0,05", "0,10", "0,20", "0,30", ">0,30"), 5, ()
    ),
    SourceRow(
        "order111:52",
        "52",
        "Нефть и нефтепродукты в растворенном и эмульсированном состоянии",
        "-",
        "мг/л",
        ("0,05", "0,05", "0,10", "0,50", "1,0", ">1,0"),
        6,
        ("The name starts on p5; numerical cells are on p6.",),
    ),
    SourceRow(
        "order111:53", "53", "СПАВ, ПАВ, АСПАВ", "-", "мг/л", ("≤0,1", "0,1", "0,5", "0,5", "0,7", ">0,7"), 6, ()
    ),
    SourceRow("order111:54", "54", "Фториды", "F-", "мг/л", ("0,75", "0,75", "1,5", "2,0", "2,1", ">2,1"), 6, ()),
    SourceRow(
        "order111:55",
        "55",
        "Сероводород",
        "H2S",
        "мг/л",
        ("0,003", "0,003", "0,003", "0,003", "0,003", ">0,003"),
        6,
        (),
    ),
    SourceRow(
        "order111:56",
        "56",
        "ПАУ и их метаболиты (по бенз(а)пирену)4",
        "-",
        "мг/л",
        ("0,00001", "0,00001", "0,00001", "0,00001", "0,00001", ">0,00001"),
        6,
        ("The trailing marker 4 has no explanatory footnote in the held replica.",),
    ),
    SourceRow(
        "order111:57", "57", "Цианиды", "CN-", "мг/л", ("0,03", "0,035", "0,035", "0,05", "0,10", ">0,10"), 6, ()
    ),
    SourceRow(
        "order111:58-total",
        "58",
        "Мышьяк общий",
        "As",
        "мг/л",
        ("0,05", "0,05", "0,08", "0,10", "0,10", ">0,10"),
        6,
        (),
    ),
    SourceRow(
        "order111:58-dissolved",
        "58",
        "Мышьяк растворенный",
        "-",
        "-",
        ("0,002", "0,002", "0,04", "0,05", "0,05", ">0,05"),
        6,
        (
            "The source explicitly prints hyphens for both symbol and unit; mg/л is not inferred from the total-arsenic row.",
        ),
    ),
    SourceRow(
        "order111:59", "59", "Роданиды", "SCN-", "мг/л", ("0,10", "0,10", "0,10", "0,15", "0,20", ">0,20"), 6, ()
    ),
    SourceRow(
        "order111:60",
        "60",
        "гамма-ГХЦГ (линдан)",
        "-",
        "мг/л",
        ("0,00001", "0,00001", "0,0001", "0,0002", "0,0003", ">0,0003"),
        6,
        (),
    ),
    SourceRow(
        "order111:61",
        "61",
        "1, 2, 3, 4, 5, 6 - Гексахлорцикло-гексан5",
        "-",
        "мг/л",
        ("0,00001", "0,00001", "0,00001", "0,00001", "0,00001", ">0,00001"),
        6,
        ("The trailing marker 5 has no explanatory footnote in the held replica.",),
    ),
    SourceRow(
        "order111:62",
        "62",
        "ДДТ (сумма изомеров)6",
        "-",
        "мг/л",
        ("0,000025", "0,000050", "0,000065", "0,000075", "0,000075", ">0,000075"),
        6,
        ("The trailing marker 6 has no explanatory footnote in the held replica.",),
    ),
    SourceRow(
        "order111:63",
        "63",
        "По фитопланктон, зоопланктону, перифитону: Индекс сапробности по Палтле и Букку (в модификации Сладечека)",
        "-",
        "-",
        ("<1,0", "1,00-1,50", "1,51-2,50", "2,51-3,50", "3,51-4,00", "> 4,00"),
        7,
        ("The organism-group heading starts on p6; the numerical cells are on p7.",),
    ),
    SourceRow(
        "order111:64-ratio",
        "64",
        "По зообентосу: отношение общей численности олигохет к общей численности донных организмов",
        "-",
        "%",
        ("1-20", "21-35", "36-50", "51-65", "66-85", "86-100 или макробентос отсутствует"),
        7,
        ("The ratio description occupies a continuation below the numerical cells inside printed row 64.",),
    ),
    SourceRow(
        "order111:64-index",
        "64",
        "По зообентосу: биотический индекс по Вудивиссу",
        "-",
        "баллы",
        ("10", "7-9", "5-6", "4", "2-3", "0-1"),
        7,
        (),
    ),
    SourceRow(
        "order111:65",
        "65",
        "Лактозоположительные кишечные палочки",
        "ЛКА",
        "в дм3",
        ("1000", "1000", "1000", "5000", "5000", ">5000-<5500"),
        7,
        (),
    ),
    SourceRow(
        "order111:66",
        "66",
        "Коли-фаги",
        "-",
        "бляшкообразующие ед.",
        ("отс.", "отс.", "<100", "100", "100", ">100-<120"),
        7,
        (),
    ),
    SourceRow(
        "order111:67",
        "67",
        "Возбудители заболеваний",
        "-",
        "",
        ("отс.", "отс.", "отс.", "отс.", "следы", "следы"),
        7,
        (),
    ),
    SourceRow(
        "order111:68",
        "68",
        "Общее количество бактерий",
        "-",
        "106 кл/см3, кл/мл",
        ("<0,5", "0,5-1,0", "1,1-3,0", "3,1-5,0", "5,1-10,0", ">10,0-<10,5"),
        7,
        (
            "Unit digits 106 and см3 are baseline in the replica; a power-of-ten interpretation is not silently applied. The p12 abbreviation expansion of кл as килолитр is retained as a source inconsistency, not a validated bacterial unit.",
        ),
    ),
    SourceRow(
        "order111:69",
        "69",
        "Количество сапрофитных бактерий",
        "-",
        "103 кл/см3 кл/мл",
        ("<0,5", "0,5-5,0", "5,1-10,0", "10,1-50,0", "50,1-100", ">100-<120"),
        8,
        (
            "Unit digits 103 and см3 are baseline in the replica; a power-of-ten interpretation is not silently applied. The p12 abbreviation expansion of кл as килолитр is retained as a source inconsistency, not a validated bacterial unit.",
        ),
    ),
    SourceRow(
        "order111:70",
        "70",
        "Отношение общего количества бактерий к количеству сапрофитных бактерий",
        "-",
        "",
        ("<103", ">103", "103-102", "<102", "<102", "<102"),
        8,
        (
            "Unresolved transcription: visual 240-dpi inspection and PDF word coordinates show baseline 103 and 102, not raised exponents. The secondary HTML is not authority to repair them.",
            "The first two inequalities are opposite in direction and the third cell has descending endpoints under either literal-digit or power-of-ten readings. No automatic numerical interpretation is supplied.",
        ),
    ),
)
