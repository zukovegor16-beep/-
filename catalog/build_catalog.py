#!/usr/bin/env python3
"""Собирает Excel с фильтрами и PDF-каталог для рассылки в мессенджерах."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from offers import OFFERS

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "out"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

INK = HexColor("#111111")
MUTED = HexColor("#5C5C5C")
LINE = HexColor("#D9D9D9")
BG = HexColor("#F4F1EA")
CARD = HexColor("#FFFFFF")
ACCENT = HexColor("#C8F542")
DARK = HexColor("#1A1A1A")

TYPE_COLORS = {
    "Клиппинг / баннер": HexColor("#1F3A1F"),
    "UGC / креаторы": HexColor("#1F2F4A"),
    "Биржа блогеров": HexColor("#3A2A12"),
    "Партнёрка / CPA": HexColor("#3A1218"),
    "Официальный маркетплейс": HexColor("#12203A"),
    "Сервис подбора": HexColor("#333333"),
}


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("Sans", FONT_REG))
    pdfmetrics.registerFont(TTFont("Sans-Bold", FONT_BOLD))


def wrap(text: str, canvas: Canvas, font: str, size: int, max_w: float) -> list[str]:
    words = (text or "").split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = words[0]
    for word in words[1:]:
        trial = f"{cur} {word}"
        if canvas.stringWidth(trial, font, size) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


def build_excel() -> Path:
    wb = Workbook()
    guide = wb.active
    guide.title = "Как пользоваться"

    guide["A1"] = "Партнёрка коротких видео — как пользоваться этим файлом"
    guide["A1"].font = Font(name="Calibri", size=16, bold=True)
    guide.merge_cells("A1:B1")

    howto = [
        ("Что отправлять клиенту", "Файл PDF из папки out. Он открывается в Telegram, WhatsApp и почте."),
        ("Где фильтровать", "Лист «Каталог»: стрелки в шапке. Можно сразу отфильтровать тип, ГЕО, модель оплаты."),
        ("Где искать", "Ctrl+F по названию, городу или площадке."),
        ("Баннеры", "Не клади картинки внутрь PDF — файл станет тяжёлым. Складывай ZIP на Яндекс.Диск / Google Drive и вставляй ссылку в столбец «Баннеры»."),
        ("Цены", "Это ориентиры рынка. Перед рассылкой сверь с кабинетом оффера и поправь ячейку."),
        ("Как обновить", "Правишь catalog/offers.py и запускаешь: python3 catalog/build_catalog.py"),
        ("Word", "Не нужен. Excel фильтрует лучше, PDF лучше выглядит в чате. Если просят Word — открой Excel и «Сохранить как DOCX»."),
        ("Юридическое", "Азартка и серые офферы в РФ рискованные. Для белой рассылки фильтруй тип ≠ Партнёрка / CPA или убери такие строки."),
    ]
    guide["A3"] = "Тема"
    guide["B3"] = "Что делать"
    guide["A3"].font = Font(bold=True)
    guide["B3"].font = Font(bold=True)
    for i, (title, text) in enumerate(howto, start=4):
        guide[f"A{i}"] = title
        guide[f"B{i}"] = text
        guide[f"B{i}"].alignment = Alignment(wrap_text=True)
    guide.column_dimensions["A"].width = 28
    guide.column_dimensions["B"].width = 110
    for row in range(4, 12):
        guide.row_dimensions[row].height = 32

    ws = wb.create_sheet("Каталог", 0)
    headers = [
        "Название",
        "Тип",
        "ГЕО",
        "Площадки",
        "Модель оплаты",
        "Ставка / цена",
        "Баннеры",
        "Ссылка",
        "Комментарий",
    ]
    header_fill = PatternFill("solid", fgColor="111111")
    header_font = Font(name="Calibri", color="C8F542", bold=True, size=11)
    thin = Border(
        left=Side(style="thin", color="DDDDDD"),
        right=Side(style="thin", color="DDDDDD"),
        top=Side(style="thin", color="DDDDDD"),
        bottom=Side(style="thin", color="DDDDDD"),
    )
    for col, title in enumerate(headers, start=1):
        cell = ws.cell(1, col, title)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(vertical="center", wrap_text=True)

    keys = ["name", "type", "geo", "platforms", "model", "rate", "banners", "url", "note"]
    fills = {
        "Клиппинг / баннер": PatternFill("solid", fgColor="EAF6D6"),
        "UGC / креаторы": PatternFill("solid", fgColor="E4EEF8"),
        "Биржа блогеров": PatternFill("solid", fgColor="F8EEDD"),
        "Партнёрка / CPA": PatternFill("solid", fgColor="F8E4E6"),
        "Официальный маркетплейс": PatternFill("solid", fgColor="E4E8F8"),
        "Сервис подбора": PatternFill("solid", fgColor="EEEEEE"),
    }

    for r, offer in enumerate(OFFERS, start=2):
        for c, key in enumerate(keys, start=1):
            value = offer[key]
            cell = ws.cell(r, c, value)
            cell.alignment = Alignment(wrap_text=True, vertical="center")
            cell.border = thin
            cell.fill = fills.get(offer["type"], PatternFill("solid", fgColor="FFFFFF"))
            if key == "url":
                cell.hyperlink = value
                cell.font = Font(name="Calibri", color="1155CC", underline="single")

    widths = [22, 24, 20, 36, 20, 42, 32, 42, 48]
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.row_dimensions[1].height = 24
    ws.auto_filter.ref = f"A1:I{len(OFFERS) + 1}"
    ws.freeze_panes = "A2"
    types = sorted({o["type"] for o in OFFERS})
    dv = DataValidation(type="list", formula1='"' + ",".join(types) + '"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"B2:B{len(OFFERS) + 1}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "partnerka-katalog.xlsx"
    wb.save(path)
    return path


def draw_header(c: Canvas, page: int, total: int) -> None:
    width, height = A4
    c.setFillColor(DARK)
    c.rect(0, height - 16 * mm, width, 16 * mm, fill=1, stroke=0)
    c.setFillColor(ACCENT)
    c.setFont("Sans-Bold", 10)
    c.drawString(16 * mm, height - 10 * mm, "ПАРТНЁРКА  ·  короткие видео")
    c.setFillColor(white)
    c.setFont("Sans", 8)
    c.drawRightString(width - 16 * mm, height - 10 * mm, f"{page} / {total}")


def draw_footer(c: Canvas) -> None:
    c.setFillColor(MUTED)
    c.setFont("Sans", 7)
    c.drawString(16 * mm, 8 * mm, "Ориентиры ставок. Перед запуском сверяй кабинет оффера. Баннеры — по ссылке, не внутри файла.")


def build_pdf() -> Path:
    register_fonts()
    path = OUT_DIR / "partnerka-katalog.pdf"
    c = Canvas(str(path), pagesize=A4)
    width, height = A4
    grouped: dict[str, list] = defaultdict(list)
    order = [
        "Клиппинг / баннер",
        "Биржа блогеров",
        "UGC / креаторы",
        "Партнёрка / CPA",
        "Официальный маркетплейс",
        "Сервис подбора",
    ]
    for offer in OFFERS:
        grouped[offer["type"]].append(offer)

    total_est = 2  # обложка + первая страница карточек
    y = height - 26 * mm
    for typ in order:
        items = grouped.get(typ, [])
        if not items:
            continue
        if y < 40 * mm:
            total_est += 1
            y = height - 26 * mm
        y -= 14 * mm
        for _ in items:
            if y - 33 * mm < 14 * mm:
                total_est += 1
                y = height - 26 * mm
            y -= 36 * mm

    page = 1

    # Cover
    c.setFillColor(DARK)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setFillColor(ACCENT)
    c.rect(0, height - 8 * mm, width, 8 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Sans", 11)
    c.drawString(22 * mm, height - 42 * mm, "каталог для авторов и байеров")
    c.setFont("Sans-Bold", 28)
    c.drawString(22 * mm, height - 58 * mm, "Партнёрка")
    c.drawString(22 * mm, height - 70 * mm, "коротких видео")
    c.setFont("Sans", 11)
    c.setFillColor(HexColor("#CFCFCF"))
    lines = [
        "Офферы, где логотип или баннер ставят в TikTok / YouTube Shorts / Reels",
        "и платят за просмотры — плюс биржи и UGC-площадки.",
        "",
        f"В каталоге {len(OFFERS)} площадок. Фильтры — в Excel-файле рядом.",
        "Этот PDF можно кидать в Telegram как прайс.",
        "",
        "Как работать:",
        "1. Автор выбирает оффер по ГЕО и ставке.",
        "2. Переходит по ссылке и берёт баннеры в кабинете / у менеджера.",
        "3. Публикует ролик и сдаёт статистику.",
        "",
        "Баннерные файлы специально не вшиты: каталог весит мало",
        "и открывается с телефона.",
    ]
    y = height - 92 * mm
    for line in lines:
        c.drawString(22 * mm, y, line)
        y -= 6 * mm
    c.setFillColor(ACCENT)
    c.setFont("Sans-Bold", 9)
    c.drawString(22 * mm, 22 * mm, "Файл для чата  ·  Excel — для себя")
    c.showPage()
    page += 1

    def new_page() -> None:
        nonlocal page
        draw_footer(c)
        c.showPage()
        page += 1
        draw_header(c, page, total_est)

    draw_header(c, page, total_est)
    y = height - 26 * mm

    for typ in order:
        items = grouped.get(typ, [])
        if not items:
            continue
        if y < 40 * mm:
            new_page()
            y = height - 26 * mm
        c.setFillColor(TYPE_COLORS.get(typ, DARK))
        c.roundRect(16 * mm, y - 7 * mm, width - 32 * mm, 9 * mm, 2 * mm, fill=1, stroke=0)
        c.setFillColor(ACCENT)
        c.setFont("Sans-Bold", 9)
        c.drawString(20 * mm, y - 4.4 * mm, typ.upper())
        c.setFillColor(white)
        c.setFont("Sans", 8)
        c.drawRightString(width - 20 * mm, y - 4.4 * mm, f"{len(items)} шт.")
        y -= 14 * mm

        for offer in items:
            block_h = 33 * mm
            if y - block_h < 14 * mm:
                new_page()
                y = height - 26 * mm
            c.setFillColor(CARD)
            c.setStrokeColor(LINE)
            c.setLineWidth(0.4)
            c.roundRect(16 * mm, y - block_h, width - 32 * mm, block_h, 2.5 * mm, fill=1, stroke=1)
            c.setFillColor(TYPE_COLORS.get(typ, DARK))
            c.rect(16 * mm, y - block_h, 2.2 * mm, block_h, fill=1, stroke=0)

            c.setFillColor(INK)
            c.setFont("Sans-Bold", 11)
            c.drawString(22 * mm, y - 6 * mm, offer["name"])
            c.setFillColor(MUTED)
            c.setFont("Sans", 7.5)
            c.drawRightString(width - 20 * mm, y - 5.6 * mm, offer["geo"])

            c.setFillColor(INK)
            c.setFont("Sans-Bold", 8)
            c.drawString(22 * mm, y - 12.2 * mm, offer["rate"])
            c.setFont("Sans", 8)
            c.setFillColor(MUTED)
            c.drawString(22 * mm, y - 17.2 * mm, f"{offer['model']}  ·  {offer['platforms']}")

            note_lines = wrap(f"Баннеры: {offer['banners']}.  {offer['note']}", c, "Sans", 7.5, width - 44 * mm)
            c.setFillColor(MUTED)
            c.setFont("Sans", 7.5)
            ny = y - 22.4 * mm
            for line in note_lines[:2]:
                c.drawString(22 * mm, ny, line)
                ny -= 3.6 * mm

            c.setFillColor(HexColor("#0B57D0"))
            c.setFont("Sans", 7)
            c.drawString(22 * mm, y - block_h + 3.6 * mm, offer["url"])
            c.linkURL(offer["url"], (22 * mm, y - block_h + 2.4 * mm, width - 20 * mm, y - block_h + 7.2 * mm))
            y -= block_h + 3 * mm

    draw_footer(c)
    c.save()
    return path


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    xlsx = build_excel()
    pdf = build_pdf()
    print(f"Excel: {xlsx}")
    print(f"PDF:   {pdf}")
    print(f"Офферов: {len(OFFERS)}")


if __name__ == "__main__":
    main()
