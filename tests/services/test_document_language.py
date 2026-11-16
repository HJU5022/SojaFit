from backend.services.document_language import language_for_pages
import pytest


EN_PAGE = (
    "Electrical characteristics and absolute maximum ratings are listed below. "
    "The reverse voltage and forward current are specified under the stated "
    "test conditions for the device and package."
)
KO_PAGE = (
    "전기적 특성 및 절대 최대 정격을 아래에 표시합니다. "
    "역전압과 순방향 전류는 소자의 시험 조건과 패키지 기준으로 규정합니다."
)


def test_accepts_english_document_with_sparse_diagram_page():
    assert language_for_pages([EN_PAGE, "Pin 1 2 3 4 5 6 7 8 · µA Ω ΔV"]) == "en"
    assert language_for_pages([EN_PAGE, "\n".join([
        "PARAMETER SYMBOL MIN TYP MAX UNIT",
        "Reverse voltage VRRM 30 V",
        "Forward current IF 200 mA",
        "Junction temperature TJ 150 °C",
    ])]) == "en"


def test_ignores_known_ti_onsemi_layout_fragments_when_english_prose_exists():
    assert language_for_pages([EN_PAGE + " TO Package Bottom View Bottom View Figure 3."]) == "en"
    assert language_for_pages([EN_PAGE + " PACKAGE OUTLINE D0008A SOIC - 1.75 mm max height SCALE 2.800 SMALL OUTLINE INTEGRATED CIRCUIT 8X (.061 ) [1.55] SYMM"]) == "en"
    assert language_for_pages([EN_PAGE + " THERMAL CHARACTERISTICS Characteristic Symbol Max Unit Total Device Dissipation FR-5 Board PD 225 mW TA = 25 C"]) == "en"
    assert language_for_pages([EN_PAGE + " Orderable part number Status Material type Package | Pins Package qty | Carrier RoHS Lead finish/ MSL rating/ Op temp (°C) Part marking"]) == "en"
    assert language_for_pages([EN_PAGE + " Publication IPC-7351 may have alternate designs."]) == "en"


def test_accepts_korean_document_with_english_manufacturer_and_part_tokens():
    assert language_for_pages([
        "Infineon BAT54-02LRH VRRM 전기적 특성과 절대 최대 정격을 표시합니다.",
        KO_PAGE,
    ]) == "ko"


def test_rejects_foreign_language_prose_after_english_page():
    assert language_for_pages([
        EN_PAGE,
        "Caracteristiques electriques et tension inverse maximale. "
        "Conditions de test et courant direct dans le tableau.",
    ]) is None


@pytest.mark.parametrize("foreign_page", [
    "Elektrische Eigenschaften und maximale Sperrspannung. Prüfbedingungen und Durchlassstrom stehen in der Tabelle.",
    "Caracteristicas electricas y tension inversa maxima. Condiciones de prueba y corriente directa en la tabla.",
    "電気的特性と最大逆電圧を示します。試験条件と電流を表に示します。",
])
def test_rejects_each_registered_foreign_language_after_english_page(foreign_page):
    assert language_for_pages([EN_PAGE, foreign_page]) is None


def test_accepts_positive_english_and_korean_prose():
    assert language_for_pages([
        EN_PAGE,
        "전기적 특성과 절대 최대 정격을 표시합니다. 역전압과 순방향 전류의 시험 조건을 확인합니다.",
    ]) == "en-ko"


def test_rejects_short_french_prose_on_same_page_without_blank_line():
    assert language_for_pages([
        EN_PAGE + " Caracteristiques electriques et tension inverse maximale."
    ]) is None


def test_rejects_unknown_natural_language_span_fail_closed():
    assert language_for_pages([
        EN_PAGE + " Nerpl vaski tulo qevra zintok moruvel.",
    ]) is None


def test_rejects_foreign_scripts_even_when_english_is_present():
    assert language_for_pages([EN_PAGE, "电气特性和最大反向电压。测试条件和电流。"]) is None


def test_allows_common_datasheet_greek_symbols():
    assert language_for_pages([
        "Electrical characteristics include µA, μA, Ω, Ω, ΔV, α, β, γ, δ, θ, π and τ.",
        EN_PAGE,
    ]) == "en"


def test_rejects_scanned_or_table_only_document():
    assert language_for_pages(["", "Pin 1 2 3 4 5 6 7 8 · 30 V · 100 mA"]) is None


def test_rejects_lowercase_technical_table_without_prose():
    assert language_for_pages(["\n".join([
        "reverse voltage vrrm 30 v",
        "forward current if 200 ma",
        "junction temperature tj 150 c",
        "package outline sot 23",
    ])]) is None
