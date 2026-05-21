import re
import copy
from pathlib import Path
from typing import Union, Optional

from bs4 import BeautifulSoup, Tag, NavigableString

from translate import process_translation

PAGE_WIDTH: int = 900

_RE_TEXT_ALIGN: re.Pattern = re.compile(r'text-align\s*:\s*[^;]+;?')

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
        const el = e.target.closest('index-sid');
        if (!el) return;
        
        const sid = el.getAttribute('id');
        if (sid === _hoveredSid) return;
        
        _clearHighlight();
        _hoveredSid = sid;
        
        const matches = document.querySelectorAll('index-sid[id="' + sid + '"]');
        matches.forEach(x => {
            x.classList.add('highlighted');
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

     window.addEventListener('beforeunload', () =>
         sessionStorage.setItem('scrollPos', window.scrollY));
     window.addEventListener('DOMContentLoaded', () => {
         const pos = sessionStorage.getItem('scrollPos');
         if (pos) window.scrollTo({ top: parseInt(pos), behavior: 'instant' });
     });
    """

def inject_all_assets(soup: BeautifulSoup) -> None:
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


def tag_contains_image(tag: Tag) -> bool:
    return tag.find('img') is not None and not tag.find('span')


def wrap_untranslated_block_as_row(soup: BeautifulSoup, tag: Tag, block_class: str) -> None:
    tag_clone: Tag = clone_tag_deep(soup, tag)
    strip_text_align_from_tag(tag)
    strip_text_align_from_tag(tag_clone)

    placeholder: Tag = soup.new_tag('div', attrs={'class': '_ph_'})
    tag.replaceWith(placeholder)

    left_div: Tag = soup.new_tag('div', attrs={'class': block_class})
    right_div: Tag = soup.new_tag('div', attrs={'class': block_class})
    left_div.append(tag)
    right_div.append(tag_clone)

    col_orig: Tag = soup.new_tag('div', attrs={'class': 'col-original'})
    col_orig.append(left_div)
    col_trans: Tag = soup.new_tag('div', attrs={'class': 'col-translation'})
    col_trans.append(right_div)

    row: Tag = build_row_div(soup, col_orig, col_trans)
    placeholder.replaceWith(row)


def translate_sid_batches(sids: list[Tag], max_words: int) -> float:
    if not sids: return 0.0

    batches: list[list[Tag]] = []
    current_batch: list[Tag] = []
    current_words: int = 0

    for sid in sids:
        wc: int = len(sid.get_text().split())
        # Eğer mevcut batch boş değilse ve yeni eklenecek olan limiti aşıyorsa
        # mevcut batch'i kaydet ve yenisine başla.
        if current_batch and current_words + wc > max_words:
            batches.append(current_batch)
            current_batch = []
            current_words = 0
            
        current_batch.append(sid)
        current_words += wc

    if current_batch:
        batches.append(current_batch)

    total_time: float = 0.0
    
    html_force_prefix: str = "```html\n<!DOCTYPE HTML>\n<body>\n"
    html_force_suffix: str = "\n</body>\n```"

    for batch in batches:
        batch_html: str = " ".join(str(sid) for sid in batch)
        
        full_payload: str = html_force_prefix + batch_html + html_force_suffix
        trans_result: str
        t_time: float
        
        trans_result, t_time = process_translation(full_payload)
        total_time += t_time

        trans_result = trans_result.strip()

        if trans_result.startswith(html_force_prefix.strip()):
            trans_result = trans_result[len(html_force_prefix.strip()):].strip()
        else:
            if trans_result.startswith("```html"):
                trans_result = trans_result[7:].strip()
            if trans_result.startswith("<!DOCTYPE HTML>"):
                trans_result = trans_result[15:].strip()
            if trans_result.startswith("<body>"):
                trans_result = trans_result[6:].strip()

        if trans_result.endswith(html_force_suffix.strip()):
            trans_result = trans_result[:-len(html_force_suffix.strip())].strip()
        else:
            if trans_result.endswith("```"):
                trans_result = trans_result[:-3].strip()
            if trans_result.endswith("</body>"):
                trans_result = trans_result[:-7].strip()

        trans_soup: BeautifulSoup = BeautifulSoup(trans_result, 'html.parser')
        
        for sid_tag in batch:
            sid_id: Optional[str] = sid_tag.get('id')
            if not sid_id: continue
            
            translated_sid: Optional[Tag] = trans_soup.find('index-sid', id=sid_id)
            if translated_sid:
                sid_tag.clear()
                for child in translated_sid.contents:
                    sid_tag.append(copy.copy(child))
                    sid_tag.append(" ")
                        
    return total_time


def process_tag(soup: BeautifulSoup, tag: Tag, max_words: int) -> Optional[float]:
    if tag.parent is None:
        return None

    if tag_contains_image(tag):
        wrap_untranslated_block_as_row(soup, tag, 'image-block')
        return None

    if tag.name == 'table':
        wrap_untranslated_block_as_row(soup, tag, 'table-block')
        return None

    tag_clone: Tag = clone_tag_deep(soup, tag)

    # Sadece <index-sid> olan alanları yakalıyoruz
    sids: list[Tag] = tag_clone.find_all('index-sid')
    diff_time: float = 0.0
    
    if sids:
        diff_time = translate_sid_batches(sids, max_words)

    placeholder: Tag = soup.new_tag('div', attrs={'class': '_ph_'})
    tag.replaceWith(placeholder)

    strip_text_align_from_tag(tag)
    strip_text_align_from_tag(tag_clone)

    col_orig: Tag = soup.new_tag('div', attrs={'class': 'col-original'})
    col_orig.append(tag)

    col_trans: Tag = soup.new_tag('div', attrs={'class': 'col-translation'})
    col_trans.append(tag_clone)

    row: Tag = build_row_div(soup, col_orig, col_trans)
    placeholder.replaceWith(row)

    return diff_time if sids else None


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


def collect_top_level_tags(soup: BeautifulSoup) -> list[Tag]:
    container = soup.find('div', class_='book-container')
    if not container:
        return []
        
    unprocessed: list[Tag] = []
    # book-container içindeki sadece en dış (top-level) tag'leri sırayla alıyoruz
    for child in container.find_all(True, recursive=False):
        if child.name in ['script', 'style', 'meta']:
            continue
        if child.get('class') and 'row' in child.get('class'):
            continue
        unprocessed.append(child)
    return unprocessed


def pdf_translate_and_merge(html_content: str, output_path: Path, max_words: int = 500) -> None:
    print("[*] INFO Ceviri basladi...")

    if output_path.exists():
        with open(str(output_path)) as f:
            html_content = f.read()
            
    soup: BeautifulSoup = BeautifulSoup(html_content, 'html.parser')
    inject_all_assets(soup)
    unwrap_page_divs_in_container(soup)
    repair_incomplete_translation_rows(soup)

    processed_count: int = 0
    tags_to_process: list[Tag] = collect_top_level_tags(soup)

    for tag in tags_to_process:
        diff_time: Optional[float] = process_tag(soup, tag, max_words)
        if diff_time is not None:
            processed_count += 1

        save_soup_to_file(soup, output_path)
        
    print(f"\n[+] İşlem Tamamlandı! Toplam {processed_count} yeni blok çevrildi.")
