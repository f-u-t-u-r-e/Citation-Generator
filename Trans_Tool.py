import customtkinter as ctk
import requests
import re
import threading
import pyperclip
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) TransTool/1.0'}

FONT_FAMILY = "Microsoft YaHei UI"
FONT_MONO = "Consolas"

FORMAT_MAP = {
    "BibTeX": "application/x-bibtex",
    "IEEE": "text/x-bibliography; style=ieee",
    "APA": "text/x-bibliography; style=apa",
    "MLA": "text/x-bibliography; style=modern-language-association",
    "Chicago": "text/x-bibliography; style=chicago-author-date",
    "Harvard": "text/x-bibliography; style=elsevier-harvard",
    "Vancouver": "text/x-bibliography; style=vancouver",
    "RIS": "application/x-research-info-systems"
}

PLACEHOLDER_TEXT = (
    "在这里粘贴 DOI、论文页面链接或者一整段参考文献文本"
)

STATUS_STYLES = {
    "idle": {"text_color": ("#6A6F73", "#AAB1BB"), "fg_color": ("#EEE4D7", "#252A31")},
    "info": {"text_color": ("#7C4A16", "#E7B675"), "fg_color": ("#F4E5D1", "#2A231D")},
    "success": {"text_color": ("#1E6B45", "#7FD1A6"), "fg_color": ("#DCEFE5", "#1D2A24")},
    "error": {"text_color": ("#A63A2B", "#FF9D90"), "fg_color": ("#F8DFDB", "#2D1F20")},
    "accent": {"text_color": ("#6B47B8", "#B99AF6"), "fg_color": ("#E9E0F8", "#241F31")}
}

def get_citation_from_doi(doi, format_name):
    clean_doi = re.sub(r'^(https?://)?(dx\.)?doi\.org/', '', doi, flags=re.IGNORECASE)
    clean_doi = re.sub(r'^doi\s*:\s*', '', clean_doi, flags=re.IGNORECASE)
    clean_doi = clean_doi.strip().rstrip(' .;,')
    url = f"https://doi.org/{clean_doi}"
    headers = {"Accept": FORMAT_MAP.get(format_name, "application/x-bibtex")}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            response.encoding = 'utf-8' 
            return response.text.strip()
    except Exception:
        pass
    return None

def extract_doi_from_text(text):
    if not text:
        return None
    match = re.search(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', text, re.IGNORECASE)
    if match:
        return match.group(1).rstrip(' .;,')
    return None

def extract_ieee_doi_by_document_id(url):
    """Fallback for IEEE Xplore pages where DOI may not be exposed in static meta tags."""
    doc_match = re.search(r'ieeexplore\.ieee\.org/document/(\d+)', url)
    if not doc_match:
        return None

    doc_id = doc_match.group(1)
    api_url = f"https://ieeexplore.ieee.org/rest/document/{doc_id}/metadata"
    api_headers = dict(HEADERS)
    api_headers["Referer"] = "https://ieeexplore.ieee.org/"

    try:
        response = requests.get(api_url, headers=api_headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for key in ("doi", "articleDoi", "xplore-doi"):
                value = data.get(key)
                doi = extract_doi_from_text(value if isinstance(value, str) else "")
                if doi:
                    return doi
    except Exception:
        pass

    return None

def extract_doi_from_url(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        soup = BeautifulSoup(response.text, 'html.parser')

        # First pass: standard citation/meta fields.
        meta_tags = soup.find_all('meta')
        for tag in meta_tags:
            name = (tag.get('name') or tag.get('property') or tag.get('itemprop') or '').lower()
            if name in {
                'citation_doi', 'dc.identifier', 'prism.doi', 'doi',
                'citation_identifier', 'bepress_citation_doi', 'og:doi'
            }:
                doi = extract_doi_from_text(tag.get('content', ''))
                if doi:
                    return doi

        # Second pass: full-page regex (handles JSON/script embedded DOI values).
        doi = extract_doi_from_text(response.text)
        if doi:
            return doi

        # Third pass: IEEE Xplore metadata API fallback.
        doi = extract_ieee_doi_by_document_id(url)
        if doi:
            return doi
    except Exception:
        pass
    return None

def search_doi_by_text(citation_text):
    """如果输入的是纯文本引用，调用 Crossref API 模糊搜索匹配 DOI"""
    url = "https://api.crossref.org/works"
    params = {
        "query.bibliographic": citation_text,
        "rows": 1, # 我们只需要最匹配的第一条结果
        "select": "DOI,score" 
    }
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            items = data.get('message', {}).get('items', [])
            # 分数大于一定阈值才认为是匹配成功
            if items and items[0].get('score', 0) > 15: 
                return items[0].get('DOI')
    except Exception as e:
        print(f"Crossref 搜索失败: {e}")
    return None

def is_ris_text(text):
    """Detect RIS-like content exported by reference managers."""
    return bool(re.search(r'(?m)^TY\s{0,2}-\s', text)) and bool(re.search(r'(?m)^ER\s{0,2}-\s*$', text))

def parse_ris_text(ris_text):
    """Parse RIS lines into tag -> list(values)."""
    fields = {}
    for raw_line in ris_text.splitlines():
        line = raw_line.rstrip()
        match = re.match(r'^([A-Z0-9]{2})\s{0,2}-\s?(.*)$', line)
        if not match:
            continue
        tag, value = match.group(1), match.group(2).strip()
        fields.setdefault(tag, []).append(value)
    return fields

def ris_to_bibtex(ris_text):
    """Convert RIS content to a BibTeX entry without relying on external APIs."""
    fields = parse_ris_text(ris_text)
    if not fields:
        return None

    ris_type = (fields.get("TY", ["GEN"])[0] or "GEN").upper()
    type_map = {
        "JOUR": "article",
        "JFULL": "article",
        "MGZN": "article",
        "BOOK": "book",
        "CHAP": "incollection",
        "CONF": "inproceedings",
        "CPAPER": "inproceedings",
        "THES": "phdthesis",
        "RPRT": "techreport",
        "GEN": "misc"
    }
    bib_type = type_map.get(ris_type, "misc")

    authors = [a for a in fields.get("AU", []) if a]
    title = (fields.get("TI") or fields.get("T1") or [""])[0]
    journal = (fields.get("JO") or fields.get("JF") or fields.get("JA") or [""])[0]
    year = ""
    for key in ("PY", "Y1", "DA"):
        if fields.get(key):
            ym = re.search(r'(\d{4})', fields[key][0])
            if ym:
                year = ym.group(1)
                break

    volume = (fields.get("VL") or [""])[0]
    number = (fields.get("IS") or [""])[0]
    pages_start = (fields.get("SP") or [""])[0]
    pages_end = (fields.get("EP") or [""])[0]
    pages = ""
    if pages_start and pages_end:
        pages = f"{pages_start}--{pages_end}"
    elif pages_start:
        pages = pages_start

    doi = (fields.get("DO") or [""])[0]
    url = (fields.get("UR") or [""])[0]
    publisher = (fields.get("PB") or [""])[0]

    key_author = "ref"
    if authors:
        last_name = re.split(r'[;,]', authors[0])[0].strip()
        key_author = re.sub(r'[^A-Za-z0-9]+', '', last_name) or "ref"
    key_year = year or "noyear"
    cite_key = f"{key_author}{key_year}"

    bib_fields = []
    if title:
        bib_fields.append(("title", title))
    if authors:
        bib_fields.append(("author", " and ".join(authors)))
    if journal and bib_type in {"article"}:
        bib_fields.append(("journal", journal))
    if year:
        bib_fields.append(("year", year))
    if volume:
        bib_fields.append(("volume", volume))
    if number:
        bib_fields.append(("number", number))
    if pages:
        bib_fields.append(("pages", pages))
    if publisher and bib_type in {"book", "incollection"}:
        bib_fields.append(("publisher", publisher))
    if doi:
        bib_fields.append(("doi", doi))
    if url:
        bib_fields.append(("url", url))

    def esc(value):
        return value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

    body = ",\n".join([f"  {k} = {{{esc(v)}}}" for k, v in bib_fields])
    return f"@{bib_type}{{{cite_key},\n{body}\n}}"

class CitationConverterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("文献引用万能转换器")
        self.geometry("1060x720")
        self.min_window_size = (960, 660)
        self.minsize(*self.min_window_size)
        self.resizable(True, True)
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("green")
        self.theme_var = ctk.StringVar(value="System")
        self._last_theme_selection = "System"
        self.status_styles = STATUS_STYLES
        self.current_status_style = "idle"

        self.configure(fg_color=("#F3EBDD", "#13171C"))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.build_header()
        self.build_main_content()
        self.show_input_placeholder()
        self.apply_background_style(self._last_theme_selection)

        # Prevent root window from auto-resizing to child requested size on theme/layout refresh.
        self.grid_propagate(False)

        self.update_idletasks()

    def build_header(self):
        header = ctk.CTkFrame(
            self,
            corner_radius=0,
            height=110,
            fg_color=("#113530", "#0D1C1A")
        )
        self.header = header
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        self.title_label = ctk.CTkLabel(
            header,
            text="引用格式转换",
            font=(FONT_FAMILY, 30, "bold"),
            text_color="#F7F3EA"
        )
        self.title_label.grid(row=0, column=0, padx=28, pady=(22, 2), sticky="w")

        self.subtitle_label = ctk.CTkLabel(
            header,
            text="粘贴 DOI、论文链接或文本引用，快速整理成目标格式",
            font=(FONT_FAMILY, 13),
            text_color="#C7D9D0"
        )
        self.subtitle_label.grid(row=1, column=0, padx=28, pady=(0, 18), sticky="w")

        self.header_side = ctk.CTkFrame(header, fg_color="transparent")
        self.header_side.grid(row=0, column=1, rowspan=2, padx=24, pady=18, sticky="e")

        self.mode_switch = ctk.CTkSegmentedButton(
            self.header_side,
            values=["Light", "System", "Dark"],
            variable=self.theme_var,
            command=self.change_theme,
            width=220,
            height=30,
            corner_radius=999,
            fg_color=("#2B514C", "#1E3432"),
            selected_color="#C97B2D",
            selected_hover_color="#B06A25",
            unselected_color=("#1F3F3A", "#182A28"),
            unselected_hover_color=("#2B514C", "#233C39"),
            font=(FONT_FAMILY, 12, "bold")
        )
        self.mode_switch.pack(anchor="e")

        self.badge_row = ctk.CTkFrame(self.header_side, fg_color="transparent")
        self.badge_row.pack(anchor="e", pady=(10, 0))

        self.live_badge = ctk.CTkLabel(
            self.badge_row,
            text="READY",
            font=(FONT_FAMILY, 11, "bold"),
            text_color="#F4EFE6",
            fg_color="#2D6A4F",
            corner_radius=999,
            padx=12,
            pady=5
        )
        self.live_badge.pack(side="left", padx=(0, 8))

        self.auto_badge = ctk.CTkLabel(
            self.badge_row,
            text="AUTO COPY",
            font=(FONT_FAMILY, 11, "bold"),
            text_color="#F7F3EA",
            fg_color=("#8A5A2B", "#6B4826"),
            corner_radius=999,
            padx=12,
            pady=5
        )
        self.auto_badge.pack(side="left")

    def build_main_content(self):
        content = ctk.CTkFrame(self, fg_color="transparent")
        self.content = content
        content.grid(row=1, column=0, sticky="nsew", padx=24, pady=24)
        content.grid_columnconfigure(0, weight=5)
        content.grid_columnconfigure(1, weight=3)
        content.grid_rowconfigure(0, weight=1)
        content.grid_propagate(False)

        self.input_card = ctk.CTkFrame(
            content,
            corner_radius=22,
            fg_color=("#FAF5EC", "#1A1F25"),
            border_width=1,
            border_color=("#D8CDBD", "#30363F")
        )
        self.input_card.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self.input_card.grid_columnconfigure(0, weight=1)
        self.input_card.grid_columnconfigure(1, weight=0)
        self.input_card.grid_rowconfigure(2, weight=1)
        self.input_card.grid_propagate(False)

        self.input_label = ctk.CTkLabel(
            self.input_card,
            text="源文献输入",
            font=(FONT_FAMILY, 21, "bold"),
            text_color=("#1E2A27", "#F3F4F6")
        )
        self.input_label.grid(row=0, column=0, columnspan=2, padx=22, pady=(20, 4), sticky="w")

        self.input_hint = ctk.CTkLabel(
            self.input_card,
            text="支持网页链接、DOI和纯文本引用",
            font=(FONT_FAMILY, 12),
            text_color=("#6A6F73", "#A1A7B3")
        )
        self.input_hint.grid(row=1, column=0, padx=(22, 10), pady=(0, 12), sticky="w")

        self.input_toolbar = ctk.CTkFrame(self.input_card, fg_color="transparent")
        self.input_toolbar.grid(row=1, column=1, padx=(0, 22), pady=(0, 12), sticky="e")

        self.paste_btn = ctk.CTkButton(
            self.input_toolbar,
            text="粘贴",
            width=72,
            height=32,
            corner_radius=12,
            font=(FONT_FAMILY, 12, "bold"),
            fg_color=("#EADFCF", "#2A3037"),
            text_color=("#31423E", "#E6E8EB"),
            hover_color=("#D9C6A9", "#353B44"),
            command=self.paste_from_clipboard
        )
        self.paste_btn.pack(side="left", padx=(0, 8))

        self.clear_input_btn = ctk.CTkButton(
            self.input_toolbar,
            text="清空",
            width=72,
            height=32,
            corner_radius=12,
            font=(FONT_FAMILY, 12, "bold"),
            fg_color=("#EADFCF", "#2A3037"),
            text_color=("#31423E", "#E6E8EB"),
            hover_color=("#D9C6A9", "#353B44"),
            command=self.clear_input
        )
        self.clear_input_btn.pack(side="left")

        self.input_box = ctk.CTkTextbox(
            self.input_card,
            height=220,
            font=(FONT_FAMILY, 14),
            corner_radius=18,
            border_width=1,
            border_color=("#D8CCBB", "#30353D"),
            fg_color=("#FFFDF9", "#15181D"),
            wrap="word"
        )
        self.input_box.grid(row=2, column=0, columnspan=2, padx=22, pady=(0, 18), sticky="nsew")
        self.input_box.bind("<FocusIn>", self.on_input_focus_in)
        self.input_box.bind("<FocusOut>", self.on_input_focus_out)
        self.input_box.bind("<KeyRelease>", self.on_input_change)

        self.result_card = ctk.CTkFrame(
            content,
            corner_radius=22,
            fg_color=("#FAF5EC", "#1A1F25"),
            border_width=1,
            border_color=("#D8CDBD", "#30363F")
        )
        self.result_card.grid(row=0, column=1, sticky="nsew")
        self.result_card.grid_columnconfigure(0, weight=1)
        self.result_card.grid_rowconfigure(7, weight=1)
        self.result_card.grid_propagate(False)

        self.format_caption = ctk.CTkLabel(
            self.result_card,
            text="目标格式",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=("#6C4D24", "#CDAA6A")
        )
        self.format_caption.grid(row=0, column=0, padx=22, pady=(20, 6), sticky="w")

        self.format_var = ctk.StringVar(value="APA")
        self.format_menu = ctk.CTkOptionMenu(
            self.result_card,
            values=list(FORMAT_MAP.keys()),
            variable=self.format_var,
            width=180,
            height=42,
            corner_radius=14,
            fg_color="#2D745A",
            button_color="#225745",
            button_hover_color="#1A4435",
            dropdown_fg_color=("#F7F1E6", "#20242A"),
            font=(FONT_FAMILY, 12, "bold")
        )
        self.format_menu.grid(row=1, column=0, padx=22, sticky="w")

        self.format_summary = ctk.CTkLabel(
            self.result_card,
            text="当前输出会按学术引用规范进行整理",
            font=(FONT_FAMILY, 12),
            text_color=("#7A7F84", "#A0A8B3")
        )
        self.format_summary.grid(row=2, column=0, padx=22, pady=(8, 0), sticky="w")

        self.convert_btn = ctk.CTkButton(
            self.result_card,
            text="开始转换",
            command=self.start_convert_thread,
            height=46,
            corner_radius=16,
            font=(FONT_FAMILY, 15, "bold"),
            fg_color="#C7742E",
            hover_color="#AC6324"
        )
        self.convert_btn.grid(row=3, column=0, padx=22, pady=(14, 10), sticky="ew")

        self.progress_bar = ctk.CTkProgressBar(
            self.result_card,
            mode="indeterminate",
            height=8,
            corner_radius=999,
            progress_color="#2D745A",
            fg_color=("#E8DCCB", "#262C34")
        )
        self.progress_bar.grid(row=4, column=0, padx=22, pady=(0, 10), sticky="ew")
        self.progress_bar.grid_remove()

        self.status_label = ctk.CTkLabel(
            self.result_card,
            text="等待输入...",
            font=(FONT_FAMILY, 12),
            corner_radius=12,
            fg_color=("#EEE4D7", "#252A31"),
            text_color=("#6A6F73", "#AAB1BB"),
            anchor="w",
            justify="left",
            wraplength=360,
            padx=12,
            pady=8
        )
        self.status_label.grid(row=5, column=0, padx=22, sticky="ew")

        self.output_header = ctk.CTkFrame(self.result_card, fg_color="transparent")
        self.output_header.grid(row=6, column=0, padx=22, pady=(18, 8), sticky="ew")
        self.output_header.grid_columnconfigure(0, weight=1)
        self.output_header.grid_columnconfigure(1, weight=0)

        self.output_label = ctk.CTkLabel(
            self.output_header,
            text="生成结果",
            font=(FONT_FAMILY, 18, "bold"),
            text_color=("#1E2A27", "#F3F4F6")
        )
        self.output_label.grid(row=0, column=0, sticky="w")

        self.output_toolbar = ctk.CTkFrame(self.output_header, fg_color="transparent")
        self.output_toolbar.grid(row=0, column=1, sticky="e")

        self.clear_output_btn = ctk.CTkButton(
            self.output_toolbar,
            text="清空结果",
            width=96,
            height=30,
            corner_radius=12,
            font=(FONT_FAMILY, 12, "bold"),
            fg_color=("#EADFCF", "#2A3037"),
            text_color=("#31423E", "#E6E8EB"),
            hover_color=("#D9C6A9", "#353B44"),
            command=self.clear_output
        )
        self.clear_output_btn.pack(side="left")

        self.output_box = ctk.CTkTextbox(
            self.result_card,
            font=(FONT_MONO, 13),
            corner_radius=18,
            border_width=1,
            border_color=("#D8CCBB", "#30353D"),
            fg_color=("#FFFCF6", "#10151B"),
            wrap="word"
        )
        self.output_box.grid(row=7, column=0, padx=22, pady=(0, 14), sticky="nsew")

        self.copy_btn = ctk.CTkButton(
            self.result_card,
            text="复制结果",
            command=self.copy_to_clipboard,
            height=42,
            corner_radius=16,
            font=(FONT_FAMILY, 14, "bold"),
            fg_color="#2E7B5A",
            hover_color="#246449"
        )
        self.copy_btn.grid(row=8, column=0, padx=22, pady=(0, 20), sticky="ew")

        self.info_strip = ctk.CTkFrame(
            self.input_card,
            fg_color=("#F2E8D9", "#20252B"),
            corner_radius=18
        )
        self.info_strip.grid(row=3, column=0, columnspan=2, padx=22, pady=(0, 20), sticky="ew")
        self.info_strip.grid_columnconfigure((0, 1, 2), weight=1)

        self.source_value_label = self.build_info_item(self.info_strip, 0, "输入来源", "DOI / URL / BibTeX / RIS / 纯文本")
        self.length_value_label = self.build_info_item(self.info_strip, 1, "当前长度", "0 字")
        self.output_value_label = self.build_info_item(self.info_strip, 2, "输出格式", self.format_var.get())

        self.result_info = ctk.CTkFrame(
            self.result_card,
            fg_color=("#F3E8D9", "#20252D"),
            corner_radius=18
        )
        self.result_info.grid(row=9, column=0, padx=22, pady=(0, 20), sticky="ew")
        self.result_info.grid_columnconfigure((0, 1), weight=1)

        self.result_meta_label = self.build_meta_item(self.result_info, 0, "结果状态", "等待生成")
        self.result_format_label = self.build_meta_item(self.result_info, 1, "格式预设", self.format_var.get())
        self.format_var.trace_add("write", self.on_format_change)

    def build_info_item(self, parent, column, label, value):
        item = ctk.CTkFrame(parent, fg_color="transparent")
        item.grid(row=0, column=column, padx=12, pady=12, sticky="ew")

        ctk.CTkLabel(
            item,
            text=label,
            font=(FONT_FAMILY, 11),
            text_color=("#7B6B59", "#97A0AA")
        ).pack(anchor="w")

        value_label = ctk.CTkLabel(
            item,
            text=value,
            font=(FONT_FAMILY, 14, "bold"),
            text_color=("#21322F", "#F3F4F6")
        )
        value_label.pack(anchor="w", pady=(2, 0))
        return value_label

    def build_meta_item(self, parent, column, label, value):
        item = ctk.CTkFrame(parent, fg_color="transparent")
        item.grid(row=0, column=column, padx=14, pady=12, sticky="ew")

        ctk.CTkLabel(
            item,
            text=label,
            font=(FONT_FAMILY, 11),
            text_color=("#7B6B59", "#97A0AA")
        ).pack(anchor="w")

        value_label = ctk.CTkLabel(
            item,
            text=value,
            font=(FONT_FAMILY, 13, "bold"),
            text_color=("#21322F", "#F3F4F6")
        )
        value_label.pack(anchor="w", pady=(2, 0))
        return value_label

    def get_resolved_style_mode(self, mode):
        if mode == "System":
            return ctk.get_appearance_mode()
        return mode

    def apply_background_style(self, mode):
        resolved = self.get_resolved_style_mode(mode)

        palettes = {
            "Light": {
                "root": "#F3EBDD",
                "header": "#113530",
                "header_title": "#F7F3EA",
                "header_subtitle": "#C7D9D0",
                "card": "#FAF5EC",
                "card_border": "#D8CDBD",
                "text_main": "#1E2A27",
                "text_sub": "#6A6F73",
                "accent_text": "#6C4D24",
                "textbox": "#FFFDF9",
                "output_box": "#FFFCF6",
                "status_fg": "#EEE4D7",
                "status_text": "#6A6F73",
                "info_strip": "#F2E8D9",
                "result_info": "#F3E8D9",
                "neutral_btn_fg": "#EADFCF",
                "neutral_btn_hover": "#D9C6A9",
                "neutral_btn_text": "#31423E",
                "convert_btn_fg": "#C7742E",
                "convert_btn_hover": "#AC6324",
                "copy_btn_fg": "#2E7B5A",
                "copy_btn_hover": "#246449",
                "menu_fg": "#2D745A",
                "menu_btn": "#225745",
                "menu_btn_hover": "#1A4435",
                "menu_dropdown": "#F7F1E6",
                "progress_fg": "#E8DCCB",
                "progress_color": "#2D745A",
                "live_badge_fg": "#2D6A4F",
                "auto_badge_fg": "#8A5A2B",
                "value_text": "#21322F"
            },
            "Dark": {
                "root": "#13171C",
                "header": "#0D1C1A",
                "header_title": "#F1F5F3",
                "header_subtitle": "#B7C8C3",
                "card": "#1A1F25",
                "card_border": "#30363F",
                "text_main": "#F3F4F6",
                "text_sub": "#A1A7B3",
                "accent_text": "#D8B37A",
                "textbox": "#15181D",
                "output_box": "#10151B",
                "status_fg": "#252A31",
                "status_text": "#AAB1BB",
                "info_strip": "#20252B",
                "result_info": "#20252D",
                "neutral_btn_fg": "#2A3037",
                "neutral_btn_hover": "#353B44",
                "neutral_btn_text": "#E6E8EB",
                "convert_btn_fg": "#6E3A16",
                "convert_btn_hover": "#552C10",
                "copy_btn_fg": "#1A4A36",
                "copy_btn_hover": "#133829",
                "menu_fg": "#1B3B34",
                "menu_btn": "#153029",
                "menu_btn_hover": "#102720",
                "menu_dropdown": "#20242A",
                "progress_fg": "#262C34",
                "progress_color": "#2A7A5B",
                "live_badge_fg": "#245C43",
                "auto_badge_fg": "#6B4826",
                "value_text": "#F3F4F6"
            }
        }
        palette = palettes.get(resolved, palettes["Light"])

        self.status_styles = {
            "idle": {"text_color": palette["status_text"], "fg_color": palette["status_fg"]},
            "info": {"text_color": "#E7B675" if resolved == "Dark" else "#7C4A16", "fg_color": "#2A231D" if resolved == "Dark" else "#F4E5D1"},
            "success": {"text_color": "#7FD1A6" if resolved == "Dark" else "#1E6B45", "fg_color": "#1D2A24" if resolved == "Dark" else "#DCEFE5"},
            "error": {"text_color": "#FF9D90" if resolved == "Dark" else "#A63A2B", "fg_color": "#2D1F20" if resolved == "Dark" else "#F8DFDB"},
            "accent": {"text_color": "#B99AF6" if resolved == "Dark" else "#6B47B8", "fg_color": "#241F31" if resolved == "Dark" else "#E9E0F8"}
        }

        self.configure(fg_color=palette["root"])
        self.header.configure(fg_color=palette["header"])
        self.title_label.configure(text_color=palette["header_title"])
        self.subtitle_label.configure(text_color=palette["header_subtitle"])

        for card in (self.input_card, self.result_card):
            card.configure(fg_color=palette["card"], border_color=palette["card_border"])

        self.input_label.configure(text_color=palette["text_main"])
        self.output_label.configure(text_color=palette["text_main"])
        self.input_hint.configure(text_color=palette["text_sub"])
        self.format_summary.configure(text_color=palette["text_sub"])
        self.format_caption.configure(text_color=palette["accent_text"])

        self.input_box.configure(fg_color=palette["textbox"], border_color=palette["card_border"])
        self.output_box.configure(fg_color=palette["output_box"], border_color=palette["card_border"])
        self.info_strip.configure(fg_color=palette["info_strip"])
        self.result_info.configure(fg_color=palette["result_info"])

        for btn in (self.paste_btn, self.clear_input_btn, self.clear_output_btn):
            btn.configure(
                fg_color=palette["neutral_btn_fg"],
                hover_color=palette["neutral_btn_hover"],
                text_color=palette["neutral_btn_text"]
            )

        self.convert_btn.configure(fg_color=palette["convert_btn_fg"], hover_color=palette["convert_btn_hover"])
        self.copy_btn.configure(fg_color=palette["copy_btn_fg"], hover_color=palette["copy_btn_hover"])
        self.format_menu.configure(
            fg_color=palette["menu_fg"],
            button_color=palette["menu_btn"],
            button_hover_color=palette["menu_btn_hover"],
            dropdown_fg_color=palette["menu_dropdown"]
        )
        self.progress_bar.configure(fg_color=palette["progress_fg"], progress_color=palette["progress_color"])
        self.live_badge.configure(fg_color=palette["live_badge_fg"])
        self.auto_badge.configure(fg_color=palette["auto_badge_fg"])
        self.source_value_label.configure(text_color=palette["value_text"])
        self.length_value_label.configure(text_color=palette["value_text"])
        self.output_value_label.configure(text_color=palette["value_text"])
        self.result_meta_label.configure(text_color=palette["value_text"])
        self.result_format_label.configure(text_color=palette["value_text"])

        # Keep current status semantics while adapting the baseline idle color to selected style.
        self.set_status(self.status_label.cget("text"), self.current_status_style)

    def change_theme(self, mode):
        if mode == self._last_theme_selection:
            return
        self._last_theme_selection = mode
        self.apply_background_style(mode)

    def detect_input_sources(self, text):
        stripped = text.strip()
        if not stripped:
            return "DOI / URL / BibTeX / RIS / 纯文本"

        detected = []
        if re.search(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', stripped, re.IGNORECASE):
            detected.append("DOI")
        if re.search(r'https?://[^\s]+', stripped, re.IGNORECASE):
            detected.append("URL")
        if re.search(r'(?m)^@\w+\s*\{', stripped):
            detected.append("BibTeX")
        if is_ris_text(stripped):
            detected.append("RIS")

        if not detected:
            detected.append("纯文本")

        return " / ".join(detected)

    def on_input_change(self, _event=None):
        if getattr(self, "input_has_placeholder", False):
            self.source_value_label.configure(text="DOI / URL / BibTeX / RIS / 纯文本")
            return
        text = self.input_box.get("1.0", "end-1c")
        stripped = text.strip()
        self.length_value_label.configure(text=f"{len(stripped)} 字")
        self.source_value_label.configure(text=self.detect_input_sources(text))

    def on_format_change(self, *_args):
        current_format = self.format_var.get()
        self.output_value_label.configure(text=current_format)
        self.result_format_label.configure(text=current_format)
        self.format_summary.configure(text=f"当前输出将转换为 {current_format} 样式")

    def show_input_placeholder(self):
        current_text = self.input_box.get("1.0", "end-1c").strip()
        if current_text:
            return
        self.input_box.delete("1.0", "end")
        self.input_box.insert("1.0", PLACEHOLDER_TEXT)
        self.input_box.configure(text_color=("#9E9588", "#7E8792"))
        self.input_has_placeholder = True
        self.length_value_label.configure(text="0 字")
        self.source_value_label.configure(text="DOI / URL / BibTeX / RIS / 纯文本")

    def hide_input_placeholder(self):
        if getattr(self, "input_has_placeholder", False):
            self.input_box.delete("1.0", "end")
            self.input_box.configure(text_color=("#1E2A27", "#F3F4F6"))
            self.input_has_placeholder = False

    def on_input_focus_in(self, _event):
        self.hide_input_placeholder()

    def on_input_focus_out(self, _event):
        if not self.input_box.get("1.0", "end-1c").strip():
            self.show_input_placeholder()

    def clear_input(self):
        self.hide_input_placeholder()
        self.input_box.delete("1.0", "end")
        self.show_input_placeholder()
        self.set_status("输入区已清空", "idle")

    def clear_output(self):
        self.output_box.delete("1.0", "end")
        self.result_meta_label.configure(text="等待生成")
        self.set_status("结果区已清空", "idle")

    def paste_from_clipboard(self):
        try:
            clipboard_text = pyperclip.paste()
        except Exception:
            clipboard_text = ""

        if clipboard_text.strip():
            self.hide_input_placeholder()
            self.input_box.delete("1.0", "end")
            self.input_box.insert("1.0", clipboard_text)
            self.on_input_change()
            self.set_status("已粘贴剪贴板内容", "success")
        else:
            self.set_status("剪贴板里没有可用文本", "error")

    def set_status(self, text, style="idle"):
        self.current_status_style = style
        style_config = self.status_styles.get(style, self.status_styles["idle"])
        self.status_label.configure(
            text=text,
            text_color=style_config["text_color"],
            fg_color=style_config["fg_color"]
        )
        compact_text = text if len(text) <= 24 else f"{text[:24]}..."
        self.live_badge.configure(
            text="RUNNING" if style in {"info", "accent"} else "READY" if style in {"idle", "success"} else "ERROR",
            fg_color="#D59B57" if style in {"info", "accent"} else "#2D6A4F" if style in {"idle", "success"} else "#A63A2B"
        )
        self.result_meta_label.configure(text=compact_text)

    def start_convert_thread(self):
        self.hide_input_placeholder()
        user_input = self.input_box.get("1.0", "end-1c").strip()
        if not user_input:
            self.show_input_placeholder()
            self.set_status("请输入源文献！", "error")
            return

        selected_format = self.format_var.get()
        self.convert_btn.configure(state="disabled", text="处理中...")
        self.progress_bar.grid()
        self.progress_bar.start()
        self.output_box.delete("1.0", "end")
        
        threading.Thread(target=self.process_request, args=(user_input, selected_format), daemon=True).start()

    def process_request(self, user_input, selected_format):
        doi = None

        # 额外支持: 直接把 RIS/AIS 风格文本转换成 BibTeX
        if is_ris_text(user_input):
            if selected_format == "BibTeX":
                bibtex = ris_to_bibtex(user_input)
                if bibtex:
                    self.output_box.insert("1.0", bibtex)
                    self.set_status("已从 RIS 文本直接转换为 BibTeX", "success")
                    pyperclip.copy(bibtex)
                else:
                    self.set_status("RIS 解析失败：请确认内容完整（含 TY/ER 标签）", "error")
                self.reset_button()
                return

            doi_match_in_ris = re.search(r'(?m)^DO\s{0,2}-\s?(.+)$', user_input)
            if doi_match_in_ris:
                doi = extract_doi_from_text(doi_match_in_ris.group(1)) or doi_match_in_ris.group(1).strip().rstrip(' .;,')
                self.set_status("已从 RIS 中提取 DOI，正在生成...", "info")
        
        # 策略 1: 直接在文本中找 DOI (通杀纯文本、URL、BibTeX)
        doi_match = re.search(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', user_input, re.IGNORECASE) if not doi else None
        url_match = re.match(r'^https?://[^\s]+', user_input) if not doi else None

        if doi_match:
            doi = extract_doi_from_text(user_input) or doi_match.group(1).rstrip(' .;,')
            self.set_status("已识别 DOI，正在生成...", "info")
        elif url_match:
            # 策略 2: 是个没有直接暴露 DOI 的网页链接
            self.set_status("正在从网页挖掘 DOI...", "info")
            doi = extract_doi_from_url(url_match.group(0))
            if doi:
                self.set_status("网页已解析出 DOI，正在生成...", "info")
        else:
            # 策略 3: 纯文本盲猜 (调用 Crossref 数据库匹配)
            self.set_status("未发现 DOI，正在启动全网文本匹配查库...", "accent")
            doi = search_doi_by_text(user_input)
            if doi:
                self.set_status("查库成功，已匹配 DOI，正在生成...", "info")
            else:
                self.set_status("匹配失败：该文本未能在数据库中找到对应的文献", "error")
                self.reset_button()
                return

        if not doi:
            self.set_status("解析失败：未能获取到有效 DOI", "error")
            self.reset_button()
            return

        # 最终步骤: 根据 DOI 请求目标格式
        citation_text = get_citation_from_doi(doi, selected_format)
        
        if citation_text:
            self.output_box.insert("1.0", citation_text)
            self.set_status(f"成功转换为 {selected_format} 格式", "success")
            pyperclip.copy(citation_text)
        else:
            self.set_status("格式拉取失败：doi.org 未返回数据", "error")
            
        self.reset_button()

    def update_status(self, text, color):
        self.set_status(text, "idle")

    def reset_button(self):
        self.convert_btn.configure(state="normal", text="开始转换")
        self.progress_bar.stop()
        self.progress_bar.grid_remove()

    def copy_to_clipboard(self):
        text = self.output_box.get("1.0", "end-1c")
        if text.strip():
            pyperclip.copy(text)
            self.set_status("已复制到剪贴板", "success")
        else:
            self.set_status("当前没有可复制的结果", "error")

if __name__ == "__main__":
    app = CitationConverterApp()
    app.mainloop()
