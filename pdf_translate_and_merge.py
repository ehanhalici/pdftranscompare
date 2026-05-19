import re
import copy
from pathlib import Path
from typing import Union, Optional

from bs4 import BeautifulSoup, Tag, NavigableString

from translate import Translator


translator: Translator = Translator()

PAGE_WIDTH: int = 900

TRANSLATABLE_TAGS: list[str] = [
    'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'dl', 'dt', 'dd',
    'th', 'td',
    'blockquote', 'figcaption', 'caption',
    'pre', 'table', 'index',
]

TRANSLATABLE_TAGS_SET: set[str] = set(TRANSLATABLE_TAGS)

_RE_TEXT_ALIGN: re.Pattern = re.compile(r'text-align\s*:\s*[^;]+;?')
_RE_HTML_TAG_STRIP: re.Pattern = re.compile(r'<[^>]+>')
_RE_PROTECT_TAGS: re.Pattern = re.compile(
    r'(<([a-zA-Z][a-zA-Z0-9]*)\s[^>]*?index-sid="([^"]+)"[^>]*>)(.*?)(</\2>)',
    re.DOTALL,
)
_RE_TOKEN: re.Pattern = re.compile(r'(<[^>]+>)|(\s+)|([^\s<]+)')
_RE_ABBREV_WORDS: re.Pattern = re.compile(
    r'^(?:[Dd]r|[Mm]r|[Mm]rs|[Mm]ss|[Pp]rof|[Ss]r|[Jj]r|[Ss]t|[Aa]ve|[Vv]s|[Ee]tc|[Ee]\.g|[Ii]\.e|[Uu]\.s|[Nn]o)\.?$',
    re.IGNORECASE,
)
_RE_ABBREV_INITIALS: re.Pattern = re.compile(
    r'^([A-Z\u00c7\u011e\u0130\u00d6\u015e\u00dca-z\u00e7\u011f\u0131\u00f6\u015f\u00fc]\.)*'
    r'[A-Z\u00c7\u011e\u0130\u00d6\u015e\u00dca-z\u00e7\u011f\u0131\u00f6\u015f\u00fc]?$'
)

VOID_ELEMENTS: frozenset[str] = frozenset({
    'br', 'hr', 'img', 'input', 'meta', 'link',
    'area', 'base', 'col', 'param', 'source', 'track', 'wbr',
})


def strip_text_align_from_tag(tag_or_nav: Union[Tag, NavigableString]) -> None:
    if not isinstance(tag_or_nav, Tag):
        return
    all_elements: list[Tag] = [tag_or_nav] + tag_or_nav.find_all(True)
    for el in all_elements:
        style_str: str = el.get('style', '')
        if style_str and 'text-align' in style_str:
            style_str = _RE_TEXT_ALIGN.sub('', style_str).strip()
            if style_str:
                el['style'] = style_str
            else:
                del el['style']
        if el.has_attr('align'):
            del el['align']


def build_side_by_side_css() -> str:
    return f"""
    * {{ box-sizing: border-box; }}

    html {{
        overflow-x: auto;
    }}

    body {{
        font-family: sans-serif;
        max-width: {PAGE_WIDTH * 2 + 1}px;
        margin: 0 auto;
        padding: 20px;
        background: #ffffff;
    }}

    .book-container > .page,
    .book-container > div[class*="page"] {{
        display: contents;
    }}

    .book-container {{
        display: flex;
        flex-direction: column;
        align-items: stretch;
        gap: 0;
        width: {PAGE_WIDTH * 2 + 1}px;
        min-width: {PAGE_WIDTH * 2 + 1}px;
    }}

    .book-container > :not(.row) {{
        text-align: left !important;
        overflow-wrap: break-word;
        word-wrap: break-word;
        word-break: break-word;
        overflow: hidden;
    }}
    .book-container > :not(.row) * {{
        text-align: left !important;
    }}

    .row {{
        display: flex;
        width: 100%;
        margin: 0;
        padding: 0;
    }}

    .page-left {{
        width: {PAGE_WIDTH}px;
        min-width: {PAGE_WIDTH}px;
        max-width: {PAGE_WIDTH}px;
        flex-shrink: 0;
        padding: 10px 48px;
        background: #ffffff;
        overflow-wrap: break-word;
        word-wrap: break-word;
        word-break: break-word;
        overflow: hidden;
        text-align: left;
    }}

    .page-right {{
        width: {PAGE_WIDTH}px;
        min-width: {PAGE_WIDTH}px;
        max-width: {PAGE_WIDTH}px;
        flex-shrink: 0;
        padding: 10px 48px;
        background: #ffffff;
        overflow-wrap: break-word;
        word-wrap: break-word;
        word-break: break-word;
        overflow: hidden;
        text-align: left;
    }}

    .divider {{
        width: 1px;
        min-width: 1px;
        flex-shrink: 0;
        background: #c0c0c0;
        align-self: stretch;
    }}

    .col-original,
    .col-translation {{
        overflow-wrap: break-word;
        word-wrap: break-word;
        word-break: break-word;
        overflow: hidden;
        text-align: left;
    }}

    .col-original > *,
    .col-translation > * {{
        margin: 0 0 0.6em 0;
        padding: 0;
    }}

    .page-left, .page-right,
    .page-left *, .page-right *,
    .col-original, .col-translation,
    .col-original *, .col-translation * {{
        text-align: left !important;
    }}

    .page-left h1, .page-right h1,
    .col-original h1, .col-translation h1 {{ font-size: 1.4em; margin: 0.6em 0 0.3em; }}
    .page-left h2, .page-right h2,
    .col-original h2, .col-translation h2 {{ font-size: 1.2em; margin: 0.5em 0 0.3em; }}
    .page-left h3, .page-right h3,
    .col-original h3, .col-translation h3 {{ font-size: 1.1em; margin: 0.4em 0 0.2em; }}

    .image-block {{
        text-align: center !important;
        margin-bottom: 0.8em;
    }}
    .image-block img {{
        max-width: 100%;
        height: auto;
        border-radius: 4px;
    }}

    .table-block {{
        margin-bottom: 0.8em;
        text-align: left !important;
    }}

    hr {{
        border: 0;
        border-top: 1px solid #ddd;
        margin: 16px 0;
    }}

    index-sid {{
        cursor: pointer;
        border-radius: 3px;
        transition: background-color 0.15s;
    }}
    .highlighted {{
        background-color: #BEDBFF !important;
        color: #000 !important;
    }}
    """


def build_hover_sync_script() -> str:
    return """
    document.querySelectorAll(
        '.page-left [style*="text-align"], .page-right [style*="text-align"], ' +
        '.col-original [style*="text-align"], .col-translation [style*="text-align"]'
    ).forEach(el => {
        el.style.removeProperty('text-align');
        if (el.getAttribute('style') === '') el.removeAttribute('style');
    });

    document.querySelectorAll(
        '.page-left [align], .page-right [align], ' +
        '.col-original [align], .col-translation [align]'
    ).forEach(el => {
        el.removeAttribute('align');
    });

    let _hoveredSid = null;

    document.addEventListener('mouseover', function(e) {
        // [index-sid] (attribute) YERİNE index-sid (tag) arıyoruz
        const el = e.target.closest('index-sid');
        if (!el) return;
        
        // index-sid attribute'u YERİNE 'id' attribute'unu alıyoruz
        const sid = el.getAttribute('id');
        if (sid === _hoveredSid) return;   /* ayni sid, tekrar islem yapma */
        
        _clearHighlight();
        _hoveredSid = sid;
        
        // Seçiciyi <index-sid id="..."> olacak şekilde güncelledik
        const matches = document.querySelectorAll('index-sid[id="' + sid + '"]');
        matches.forEach(x => {
            x.classList.add('highlighted');
            /* Karsi tarafin eslesmesini gorunur kilmak icin scroll */
            if (x !== el) {
                x.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        });
    });
    document.addEventListener('mouseout', function(e) {
         const el = e.target.closest('index-sid');
         if (!el) return;
         
         const sid = el.getAttribute('id');
         const related = e.relatedTarget;
         if (related) {
             const relatedEl = related.closest ? related.closest('index-sid') : null;
             if (relatedEl && relatedEl.getAttribute('id') === sid) return;
         }
         _clearHighlight();
     });
    function _clearHighlight() {
          if (_hoveredSid) {
              document.querySelectorAll('index-sid[id="' + _hoveredSid + '"]')
                      .forEach(x => x.classList.remove('highlighted'));
              _hoveredSid = null;
          }
      }

     /* Scroll pozisyonu hatırlama */
     window.addEventListener('beforeunload', () =>
         sessionStorage.setItem('scrollPos', window.scrollY));
     window.addEventListener('DOMContentLoaded', () => {
         const pos = sessionStorage.getItem('scrollPos');
         if (pos) window.scrollTo({ top: parseInt(pos), behavior: 'instant' });
     });
    """


def inject_style_tag(soup: BeautifulSoup) -> None:
    if soup.find('style', id='translate-style'):
        return
    style_tag: Tag = soup.new_tag('style', id='translate-style')
    style_tag.string = build_side_by_side_css()
    if soup.head:
        soup.head.append(style_tag)


def inject_book_container(soup: BeautifulSoup) -> None:
    if soup.find('div', class_='book-container'):
        return
    container: Tag = soup.new_tag('div', attrs={'class': 'book-container'})
    movable_children: list[Union[Tag, NavigableString]] = [
        child for child in list(soup.body.children)
        if not (child.name in ['script', 'style', 'meta']
                or (child.name is None and not str(child).strip()))
    ]
    for child in movable_children:
        container.append(child.extract())
    soup.body.insert(0, container)


def inject_script_tag(soup: BeautifulSoup) -> None:
    if soup.find('script', id='translate-script'):
        return
    script_tag: Tag = soup.new_tag('script', id='translate-script')
    script_tag.string = build_hover_sync_script()
    if soup.body:
        soup.body.append(script_tag)


def inject_all_assets(soup: BeautifulSoup) -> None:
    inject_style_tag(soup)
    inject_book_container(soup)
    inject_script_tag(soup)


def save_soup_to_file(soup: BeautifulSoup, output_path: Path) -> None:
    with open(str(output_path), 'w+', encoding='utf-8') as f:
        f.write(str(soup))


def build_row_div(soup: BeautifulSoup, col_orig: Tag, col_trans: Tag) -> Tag:
    row: Tag = soup.new_tag('div', attrs={'class': 'row'})
    page_left: Tag = soup.new_tag('div', attrs={'class': 'page-left'})
    divider: Tag = soup.new_tag('div', attrs={'class': 'divider'})
    page_right: Tag = soup.new_tag('div', attrs={'class': 'page-right'})
    page_left.append(col_orig)
    page_right.append(col_trans)
    row.append(page_left)
    row.append(divider)
    row.append(page_right)
    return row


def clone_tag_deep(soup: BeautifulSoup, tag: Tag) -> Tag:
    clone_soup: BeautifulSoup = BeautifulSoup(str(tag), 'html.parser')
    if clone_soup.body and clone_soup.body.contents:
        return list(clone_soup.body.contents)[0].extract()
    elif clone_soup.contents:
        return list(clone_soup.contents)[0].extract()
    return soup.new_tag('div')


def has_processed_ancestor(tag: Tag) -> bool:
    for parent in tag.parents:
        if parent.name == 'div':
            parent_classes: list[str] = parent.get('class', [])
            if any(c in parent_classes for c in ('col-original', 'col-translation',
                                                   'image-block', 'table-block')):
                return True
        if parent.name == 'div' and 'book-container' in parent.get('class', []):
            break
    return False


def tag_contains_image(tag: Tag) -> bool:
    return tag.find('img') is not None and not tag.find('span')


def is_inside_table_block(tag: Tag) -> bool:
    for parent in tag.parents:
        if parent.name == 'div' and 'table-block' in parent.get('class', []):
            return True
        if parent.name == 'div' and 'book-container' in parent.get('class', []):
            break
    return False


def is_translatable_tag(tag: Tag) -> bool:
    if tag_contains_image(tag):
        return False
    if tag.name == 'table':
        return False
    if is_inside_table_block(tag):
        return False
    if not tag.text.strip():
        return False
    return True


def count_words_in_html(html_str: str) -> int:
    text_only: str = _RE_HTML_TAG_STRIP.sub('', html_str)
    return len(text_only.split())


def _is_abbreviation_word(word: str) -> bool:
    clean: str = word.rstrip('\'"\u201d\u2019)]').rstrip('.!?')
    if _RE_ABBREV_WORDS.match(clean):
        return True
    if clean.isdigit():
        return True
    if _RE_ABBREV_INITIALS.match(clean) and len(clean) > 1:
        return True
    return False


def split_html_into_sentences(text: str) -> list[str]:
    if not text or not text.strip():
        return []

    tokens: list[str] = [m.group(0) for m in _RE_TOKEN.finditer(text) if m.group(0)]
    sentences: list[str] = []
    current_sentence: list[str] = []
    open_tags: int = 0
    pending_split: bool = False

    for i, token in enumerate(tokens):
        current_sentence.append(token)
        stripped: str = token.strip()

        if stripped.startswith('<') and stripped.endswith('>'):
            if stripped.startswith('</'):
                open_tags = max(0, open_tags - 1)
            elif not stripped.endswith('/>'):
                tag_name_match: Optional[re.Match] = re.match(r'<([a-zA-Z0-9]+)', stripped)
                if tag_name_match:
                    parsed_tag_name: str = tag_name_match.group(1).lower()
                    if parsed_tag_name not in VOID_ELEMENTS:
                        open_tags += 1

        if stripped and not stripped.startswith('<') and stripped[-1] in '.!?':
            if not _is_abbreviation_word(stripped):
                next_word_token: Optional[str] = None
                next_word_idx: int = -1
                for j in range(i + 1, len(tokens)):
                    next_stripped: str = tokens[j].strip()
                    if not next_stripped or next_stripped.startswith('<'):
                        continue
                    next_word_token = next_stripped
                    next_word_idx = j
                    break

                if next_word_token is None:
                    pending_split = True
                elif next_word_token[0].isupper() or next_word_token[0].isdigit() or next_word_token[0] in '("\'\u201c\u2018':
                    pending_split = True
                else:
                    has_space_between: bool = any(t.isspace() for t in tokens[i+1:next_word_idx])
                    if has_space_between or stripped[-1] in '!?':
                        pending_split = True

        if pending_split and open_tags == 0:
            sentence: str = " ".join(current_sentence).strip()
            if sentence:
                sentences.append(sentence)
            current_sentence = []
            pending_split = False

    if current_sentence:
        final_sentence: str = " ".join(current_sentence).strip()
        if final_sentence:
            sentences.append(final_sentence)

    return sentences


def protect_index_sid_tags_for_llm(html_str: str) -> tuple[str, dict[str, str]]:
    placeholders: dict[str, str] = {}

    def replacer(match: re.Match) -> str:
        full_open_tag: str = match.group(1)
        sid: str = match.group(3)
        content: str = match.group(4)
        full_close_tag: str = match.group(5)

        ph_open: str = f"\u00a7SID{sid}\u00a7"
        ph_close: str = f"\u00a7/SID{sid}\u00a7"

        placeholders[ph_open] = full_open_tag
        placeholders[ph_close] = full_close_tag

        return f"{ph_open}{content}{ph_close}"

    result: str = _RE_PROTECT_TAGS.sub(replacer, html_str)
    return result, placeholders


def restore_protected_tags_after_llm(translated_str: str, placeholders: dict[str, str]) -> str:
    sorted_placeholders: list[tuple[str, str]] = sorted(
        placeholders.items(), key=lambda x: len(x[0]), reverse=True
    )
    for ph, original_tag in sorted_placeholders:
        translated_str = translated_str.replace(ph, original_tag)
    return translated_str


def batch_sentences_by_word_limit(inner_html: str, max_words: int) -> list[str]:
    word_count: int = count_words_in_html(inner_html)
    if word_count <= max_words:
        return [inner_html]

    sentences: list[str] = split_html_into_sentences(inner_html)
    batches: list[str] = []
    current_batch: list[str] = []
    current_word_count: int = 0

    for sent in sentences:
        sent_wc: int = count_words_in_html(sent)
        if current_word_count + sent_wc > max_words and current_batch:
            batches.append(" ".join(current_batch))
            current_batch = [sent]
            current_word_count = sent_wc
        else:
            current_batch.append(sent)
            current_word_count += sent_wc

    if current_batch:
        batches.append(" ".join(current_batch))

    return batches


def translate_batch_via_llm(batch: str) -> tuple[str, float]:
    html_force_prefix: str = "```html\n<!DOCTYPE HTML>\n<body>"
    html_force_suffix: str = "</body>\n```"

    protected_batch: str
    placeholders: dict[str, str]
    protected_batch, placeholders = protect_index_sid_tags_for_llm(batch)
    protected_batch = protected_batch.replace("\u2022 ", "&bull; ").replace("\u2022", "&bull;")

    batch_str: str = html_force_prefix + protected_batch + html_force_suffix

    trans_result: str
    t_time: float
    trans_result, t_time = translator.process(batch_str)

    if trans_result.startswith(html_force_prefix):
        trans_result = trans_result[len(html_force_prefix): -len(html_force_suffix)]

    trans_result = restore_protected_tags_after_llm(trans_result.strip(), placeholders)
    return trans_result, t_time


def translate_all_batches(batches: list[str]) -> tuple[str, float]:
    translated_parts: list[str] = []
    total_time: float = 0.0

    for batch in batches:
        translated: str
        t_time: float
        translated, t_time = translate_batch_via_llm(batch)
        total_time += t_time
        translated_parts.append(translated)

    return " ".join(translated_parts), total_time


def wrap_image_block_as_row(soup: BeautifulSoup, tag: Tag) -> None:
    tag_clone: Tag = clone_tag_deep(soup, tag)
    strip_text_align_from_tag(tag)
    strip_text_align_from_tag(tag_clone)

    placeholder: Tag = soup.new_tag('div', attrs={'class': '_ph_'})
    tag.replaceWith(placeholder)

    img_left: Tag = soup.new_tag('div', attrs={'class': 'image-block'})
    img_right: Tag = soup.new_tag('div', attrs={'class': 'image-block'})
    img_left.append(tag)
    img_right.append(tag_clone)

    col_orig: Tag = soup.new_tag('div', attrs={'class': 'col-original'})
    col_orig.append(img_left)
    col_trans: Tag = soup.new_tag('div', attrs={'class': 'col-translation'})
    col_trans.append(img_right)

    row: Tag = build_row_div(soup, col_orig, col_trans)
    placeholder.replaceWith(row)


def wrap_table_block_as_row(soup: BeautifulSoup, tag: Tag) -> None:
    tag_clone: Tag = clone_tag_deep(soup, tag)

    placeholder: Tag = soup.new_tag('div', attrs={'class': '_ph_'})
    tag.replaceWith(placeholder)

    tbl_left: Tag = soup.new_tag('div', attrs={'class': 'table-block'})
    tbl_right: Tag = soup.new_tag('div', attrs={'class': 'table-block'})
    tbl_left.append(tag)
    tbl_right.append(tag_clone)

    col_orig: Tag = soup.new_tag('div', attrs={'class': 'col-original'})
    col_orig.append(tbl_left)
    col_trans: Tag = soup.new_tag('div', attrs={'class': 'col-translation'})
    col_trans.append(tbl_right)

    row: Tag = build_row_div(soup, col_orig, col_trans)
    placeholder.replaceWith(row)


def translate_text_tag_as_row(soup: BeautifulSoup, tag: Tag, max_words: int) -> float:
    tag_name: str = tag.name
    tag_index_sid: Optional[str] = tag.get('index-sid')
    inner_html: str = " ".join(str(child) for child in tag.contents)

    batches: list[str] = batch_sentences_by_word_limit(inner_html, max_words)
    translated_html: str
    diff_time: float
    translated_html, diff_time = translate_all_batches(batches)

    translated_html_str: str = f"<{tag_name}>{translated_html}</{tag_name}>"

    placeholder: Tag = soup.new_tag('div', attrs={'class': '_ph_'})
    tag.replaceWith(placeholder)

    strip_text_align_from_tag(tag)

    col_orig: Tag = soup.new_tag('div', attrs={'class': 'col-original'})
    col_orig.append(tag)

    col_trans: Tag = soup.new_tag('div', attrs={'class': 'col-translation'})
    translated_soup: BeautifulSoup = BeautifulSoup(translated_html_str, 'html.parser')
    children: list[Union[Tag, NavigableString]] = (
        list(translated_soup.body.contents) if translated_soup.body
        else list(translated_soup.contents)
    )

    if tag_index_sid and children:
        for child in children:
            if isinstance(child, Tag) and not child.get('index-sid'):
                child['index-sid'] = tag_index_sid

    for child in children:
        strip_text_align_from_tag(child)
        col_trans.append(child)

    row: Tag = build_row_div(soup, col_orig, col_trans)
    placeholder.replaceWith(row)

    return diff_time


def unwrap_page_divs_in_container(soup: BeautifulSoup) -> None:
    for page_div in soup.find_all('div', class_='page'):
        parent = page_div.parent
        if parent and 'book-container' in parent.get('class', []):
            page_div.unwrap()


def repair_incomplete_translation_rows(soup: BeautifulSoup) -> None:
    for col_orig in soup.find_all('div', class_='col-original'):
        parent_row = col_orig.parent
        if parent_row and parent_row.name == 'div' and 'row' in parent_row.get('class', []):
            if not parent_row.find('div', class_='col-translation'):
                col_orig.unwrap()
                parent_row.unwrap()


def collect_unprocessed_translatable_tags(soup: BeautifulSoup) -> list[Tag]:
    all_tags: list[Tag] = soup.find_all(TRANSLATABLE_TAGS)
    unprocessed: list[Tag] = []
    for tag in all_tags:
        if tag.parent is None:
            continue
        if has_processed_ancestor(tag):
            continue
        unprocessed.append(tag)
    return unprocessed


def process_tag(soup: BeautifulSoup, tag: Tag, max_words: int) -> Optional[float]:
    if tag.parent is None:
        return None

    if tag_contains_image(tag):
        wrap_image_block_as_row(soup, tag)
        return None

    if tag.name == 'table':
        wrap_table_block_as_row(soup, tag)
        return None

    if not tag.text.strip():
        return None

    if not is_translatable_tag(tag):
        return None

    return translate_text_tag_as_row(soup, tag, max_words)


def pdf_translate_and_merge(html_content: str, output_path: Path, max_words: int = 100) -> None:
    print("[*] INFO Ceviri basladi...")

    if output_path.exists():
        with open(str(output_path)) as f:
            html_content = f.read()
    soup: BeautifulSoup = BeautifulSoup(html_content, 'html.parser')
    inject_all_assets(soup)
    unwrap_page_divs_in_container(soup)
    repair_incomplete_translation_rows(soup)

    processed_count: int = 0
    tags_to_process: list[Tag] = collect_unprocessed_translatable_tags(soup)

    for tag in tags_to_process:
        diff_time: Optional[float] = process_tag(soup, tag, max_words)
        if diff_time is not None:
            processed_count += 1

        save_soup_to_file(soup, output_path)
    print(f"\n[+] İşlem Tamamlandı! Toplam {processed_count} yeni blok çevrildi.")
