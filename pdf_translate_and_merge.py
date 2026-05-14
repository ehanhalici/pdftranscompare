import os
import time
import re
import tempfile
from bs4 import BeautifulSoup
from translate import Translator


translator = Translator()

# ──────────────────────────────────────────────────
# SAYFA GENİŞLİĞİ (A4 @96dpi ≈ 794px)
# ──────────────────────────────────────────────────
PAGE_WIDTH = 794

TRANSLATABLE_TAGS = [
    'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'dl', 'dt', 'dd',
    'th', 'td',
    'blockquote', 'figcaption', 'caption',
    'pre', 'table',
]

def _strip_text_align(tag):
    """Tag ve tüm alt elementlerinden text-align inline stilini ve align niteliğini siler."""
    for el in [tag] + tag.find_all(True):
        style = el.get('style', '')
        if style and 'text-align' in style:
            style = re.sub(r'text-align\s*:\s*[^;]+;?', '', style).strip()
            if style:
                el['style'] = style
            else:
                del el['style']
        if el.has_attr('align'):
            del el['align']


def inject_assets(soup):
    """Stil ve script varlıklarını enjekte eder (idempotent)."""
    if not soup.find('style', id='translate-style'):
        style = soup.new_tag('style', id='translate-style')
        style.string = f"""
        * {{ box-sizing: border-box; }}

        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background: #ffffff;
            display: flex;
            justify-content: center;
        }}

        /* Orijinal HTML sarıcılarını görünmez yap */
        .book-container > .page,
        .book-container > div[class*="page"] {{
            display: contents;
        }}

        /* ANA KAPSAYICI — sayfanın ortasında */
        .book-container {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0;
            width: 100%;
        }}

        /* ══════════════════════════════════════════════════
           SERBEST İÇERİK — Henüz .row'a sarlanmamış elementler
           soldaki sayfa genişliğinde sola hizalı kalır
           ══════════════════════════════════════════════════ */
        .book-container > :not(.row) {{
            max-width: {PAGE_WIDTH * 2}px;
            width: {PAGE_WIDTH * 2}px;
            text-align: left !important;
            overflow-wrap: break-word;
            word-wrap: break-word;
            word-break: break-word;
            overflow: hidden;
        }}
        .book-container > :not(.row) * {{
            text-align: left !important;
        }}

        /* HER SATIR — [page-left | çizgi | page-right] */
        .row {{
            display: flex;
            width: fit-content;
            margin: 0;
            padding: 0;
        }}

        /* Sol sayfa — orijinal metin */
        .page-left {{
            width: {PAGE_WIDTH}px;
            min-width: {PAGE_WIDTH}px;
            max-width: {PAGE_WIDTH}px;
            padding: 10px 48px;
            background: #ffffff;
            overflow-wrap: break-word;
            word-wrap: break-word;
            word-break: break-word;
            overflow: hidden;
            text-align: left;
        }}

        /* Sağ sayfa — çeviri metni */
        .page-right {{
            width: {PAGE_WIDTH}px;
            min-width: {PAGE_WIDTH}px;
            max-width: {PAGE_WIDTH}px;
            padding: 10px 48px;
            background: #ffffff;
            overflow-wrap: break-word;
            word-wrap: break-word;
            word-break: break-word;
            overflow: hidden;
            text-align: left;
        }}

        /* Dikey ayırıcı çizgi */
        .divider {{
            width: 1px;
            min-width: 1px;
            background: #c0c0c0;
            align-self: stretch;
        }}

        /* İçerik sütunları */
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

        /* ══════════════════════════════════════════
           HER ŞEY SOLA HİZALI — inline dahil ezer
           ══════════════════════════════════════════ */
        .page-left, .page-right,
        .page-left *, .page-right *,
        .col-original, .col-translation,
        .col-original *, .col-translation * {{
            text-align: left !important;
        }}

        /* Başlıklar */
        .page-left h1, .page-right h1,
        .col-original h1, .col-translation h1 {{ font-size: 1.4em; margin: 0.6em 0 0.3em; }}
        .page-left h2, .page-right h2,
        .col-original h2, .col-translation h2 {{ font-size: 1.2em; margin: 0.5em 0 0.3em; }}
        .page-left h3, .page-right h3,
        .col-original h3, .col-translation h3 {{ font-size: 1.1em; margin: 0.4em 0 0.2em; }}

        /* Resim bloklari (sadece resim ortali) */
        .image-block {{
            text-align: center !important;
            margin-bottom: 0.8em;
        }}
        .image-block img {{
            max-width: 100%;
            height: auto;
            border-radius: 4px;
        }}

        /* Tablo bloklari — her iki sütunda kopya */
        .table-block {{
            margin-bottom: 0.8em;
            text-align: left !important;
        }}

        hr {{
            border: 0;
            border-top: 1px solid #ddd;
            margin: 16px 0;
        }}

        [data-sid] {{
            cursor: pointer;
            border-radius: 3px;
            transition: background-color 0.15s;
        }}
        .highlighted {{
            background-color: #BEDBFF !important;
            color: #000 !important;
        }}
        """
        if soup.head:
            soup.head.append(style)

    if not soup.find('div', class_='book-container'):
        container = soup.new_tag('div', attrs={'class': 'book-container'})
        elements_to_move = [
            child for child in soup.body.children
            if not (child.name in ['script', 'style', 'meta']
                    or (child.name is None and not str(child).strip()))
        ]
        for el in elements_to_move:
            container.append(el.extract())
        soup.body.insert(0, container)

    if not soup.find('script', id='translate-script'):
        script = soup.new_tag('script', id='translate-script')
        script.string = """
        /* Inline text-align stilini temizle */
        document.querySelectorAll(
            '.page-left [style*="text-align"], .page-right [style*="text-align"], ' +
            '.col-original [style*="text-align"], .col-translation [style*="text-align"]'
        ).forEach(el => {
            el.style.removeProperty('text-align');
            if (el.getAttribute('style') === '') el.removeAttribute('style');
        });

        /* align niteliğini kaldır */
        document.querySelectorAll(
            '.page-left [align], .page-right [align], ' +
            '.col-original [align], .col-translation [align]'
        ).forEach(el => {
            el.removeAttribute('align');
        });

        /* Hover highlight */
        document.addEventListener('mouseover', function(e) {
            const el = e.target.closest('[data-sid]');
            if (el) {
                const sid = el.getAttribute('data-sid');
                document.querySelectorAll('[data-sid="' + sid + '"]')
                        .forEach(x => x.classList.add('highlighted'));
            }
        });
        document.addEventListener('mouseout', function(e) {
            const el = e.target.closest('[data-sid]');
            if (el) {
                const sid = el.getAttribute('data-sid');
                document.querySelectorAll('[data-sid="' + sid + '"]')
                        .forEach(x => x.classList.remove('highlighted'));
            }
        });

        /* Scroll pozisyonu hatırlama */
        window.addEventListener('beforeunload', () =>
            sessionStorage.setItem('scrollPos', window.scrollY));
        window.addEventListener('DOMContentLoaded', () => {
            const pos = sessionStorage.getItem('scrollPos');
            if (pos) window.scrollTo({ top: parseInt(pos), behavior: 'instant' });
        });
        """
        if soup.body:
            soup.body.append(script)


# ──────────────────────────────────────────────────
# YARDIMCI FONKSİYONLAR
# ──────────────────────────────────────────────────

def _save_soup(soup, html_path):
    """Atomik kaydetme."""
    temp_dir = os.path.dirname(os.path.abspath(html_path))
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=temp_dir, delete=False) as tmp_f:
        tmp_f.write(str(soup))
    os.replace(tmp_f.name, html_path)


def _build_row(soup, col_orig, col_trans):
    """[page-left > col_orig | divider | page-right > col_trans] oluşturur."""
    row = soup.new_tag('div', attrs={'class': 'row'})
    pl = soup.new_tag('div', attrs={'class': 'page-left'})
    dv = soup.new_tag('div', attrs={'class': 'divider'})
    pr = soup.new_tag('div', attrs={'class': 'page-right'})

    pl.append(col_orig)
    pr.append(col_trans)
    row.append(pl)
    row.append(dv)
    row.append(pr)
    return row


def _clone_tag(soup, tag):
    """Tag'ın bağımsız kopyasını oluşturur."""
    clone_soup = BeautifulSoup(str(tag), 'html.parser')
    if clone_soup.body and clone_soup.body.contents:
        return list(clone_soup.body.contents)[0].extract()
    elif clone_soup.contents:
        return list(clone_soup.contents)[0].extract()
    return soup.new_tag('div')


def is_already_processed(tag):
    """Tag'ın zaten işlenip işlenmediğini kontrol eder."""
    for parent in tag.parents:
        if parent.name == 'div':
            classes = parent.get('class', [])
            if any(c in classes for c in ['col-original', 'col-translation',
                                           'image-block', 'table-block']):
                return True
        if parent.name == 'div' and 'book-container' in parent.get('class', []):
            break
    return False


def is_image_block(tag):
    """Tag bir resim içeriyor mu?"""
    return tag.find('img') is not None and not tag.find('span')


def _should_translate(tag):
    """Bu tag çevrilmeli mi? Resimler ve tablolar çevrilmez."""
    if is_image_block(tag):
        return False
    if tag.name == 'table':
        return False
    if not tag.text.strip():
        return False
    return True



def count_words_in_html(html_str):
    text_only = re.sub(r'<[^>]+>', '', html_str)
    return len(text_only.split())


ABBREVIATION_PATTERNS = re.compile(
    r'^(?:[Dd]r|[Mm]r|[Mm]rs|[Mm]ss|[Pp]rof|[Ss]r|[Jj]r|[Ss]t|[Aa]ve|[Vv]s|[Ee]tc|[Ee]\.g|[Ii]\.e|[Uu]\.s|[Nn]o)\.?$',
    re.IGNORECASE
)


def split_into_sentences(text):
    """Metni cümlelere ayırır (HTML tag takibi ile)."""
    if not text or not text.strip():
        return []

    token_pattern = re.compile(r'(<[^>]+>)|(\s+)|([^\s<]+)')
    tokens = [m.group(0) for m in token_pattern.finditer(text) if m.group(0)]

    sentences = []
    current_sentence = []
    open_tags = 0
    pending_split = False

    void_elements = {
        'br', 'hr', 'img', 'input', 'meta', 'link',
        'area', 'base', 'col', 'param', 'source', 'track', 'wbr'
    }

    def is_abbreviation(word):
        clean = word.rstrip('\'"\u201d\u2019)]').rstrip('.!?')
        if ABBREVIATION_PATTERNS.match(clean):
            return True
        if clean.isdigit():
            return True
        if re.match(r'^([A-Z\u00c7\u011e\u0130\u00d6\u015e\u00dca-z\u00e7\u011f\u0131\u00f6\u015f\u00fc]\.)*[A-Z\u00c7\u011e\u0130\u00d6\u015e\u00dca-z\u00e7\u011f\u0131\u00f6\u015f\u00fc]?$', clean) and len(clean) > 1:
            return True
        return False

    for i, token in enumerate(tokens):
        current_sentence.append(token)
        stripped = token.strip()

        if stripped.startswith('<') and stripped.endswith('>'):
            if stripped.startswith('</'):
                open_tags = max(0, open_tags - 1)
            elif not stripped.endswith('/>'):
                tag_name_match = re.match(r'<([a-zA-Z0-9]+)', stripped)
                if tag_name_match:
                    tag_name = tag_name_match.group(1).lower()
                    if tag_name not in void_elements:
                        open_tags += 1

        if stripped and not stripped.startswith('<') and stripped[-1] in '.!?':
            if not is_abbreviation(stripped):
                next_word_token = None
                next_word_idx = -1
                for j in range(i + 1, len(tokens)):
                    next_stripped = tokens[j].strip()
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
                    has_space_between = any(t.isspace() for t in tokens[i+1:next_word_idx])
                    if has_space_between or stripped[-1] in '!?':
                        pending_split = True

        if pending_split and open_tags == 0:
            sentence = "".join(current_sentence).strip()
            if sentence:
                sentences.append(sentence)
            current_sentence = []
            pending_split = False

    if current_sentence:
        sentence = "".join(current_sentence).strip()
        if sentence:
            sentences.append(sentence)

    return sentences
def protect_all_tags_for_llm(html_str):
    """İçinde data-sid olan tüm etiketleri korur."""
    pattern = re.compile(r'(<([a-zA-Z][a-zA-Z0-9]*)\s[^>]*?data-sid="([^"]+)"[^>]*>)(.*?)(</\2>)', re.DOTALL)
    placeholders = {}

    def replacer(match):
        full_open_tag = match.group(1)
        # tag_name = match.group(2) # Regex içinde \2 olarak kullanıldı
        sid = match.group(3)
        content = match.group(4)
        full_close_tag = match.group(5)

        ph_open = f"\u00a7SID{sid}\u00a7"
        ph_close = f"\u00a7/SID{sid}\u00a7"
        
        placeholders[ph_open] = full_open_tag
        placeholders[ph_close] = full_close_tag
        
        return f"{ph_open}{content}{ph_close}"

    return pattern.sub(replacer, html_str), placeholders


def restore_all_tags_after_llm(translated_str, placeholders):
    """Yer tutucuları orijinal etiketlere çevirir."""
    sorted_placeholders = sorted(placeholders.items(), key=lambda x: len(x[0]), reverse=True)
    
    for ph, original_tag in sorted_placeholders:
        translated_str = translated_str.replace(ph, original_tag)
        
    return translated_str
# ──────────────────────────────────────────────────
# ANA İŞLEM — Eski basit yöntem
# ──────────────────────────────────────────────────

def process_html_live(html_path, max_words=100):
    print(f"[*] {html_path} dosyası işleniyor...")

    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    inject_assets(soup)

    for page_div in soup.find_all('div', class_='page'):
        parent = page_div.parent
        if parent and 'book-container' in parent.get('class', []):
            page_div.unwrap()

    for col_orig in soup.find_all('div', class_='col-original'):
        parent_row = col_orig.parent
        if parent_row and parent_row.name == 'div' and 'row' in parent_row.get('class', []):
            if not parent_row.find('div', class_='col-translation'):
                print("[!] Yarım kalmış çeviri bloğu tespit edildi, onarılıyor...")
                col_orig.unwrap()
                parent_row.unwrap()

    processed_count = 0

    while True:
        target_tags = soup.find_all(TRANSLATABLE_TAGS)
        found_unprocessed = False

        for tag in target_tags:
            if is_already_processed(tag):
                continue
            if tag.parent is None:
                continue

            found_unprocessed = True

            # ──────────────────────────────────────────
            # 1) RESİM BLOKLARI
            # ──────────────────────────────────────────
            if is_image_block(tag):
                tag_clone = _clone_tag(soup, tag)
                _strip_text_align(tag)
                _strip_text_align(tag_clone)

                placeholder = soup.new_tag('div', attrs={'class': '_ph_'})
                tag.replaceWith(placeholder)

                img_left = soup.new_tag('div', attrs={'class': 'image-block'})
                img_right = soup.new_tag('div', attrs={'class': 'image-block'})
                img_left.append(tag)
                img_right.append(tag_clone)

                col_orig = soup.new_tag('div', attrs={'class': 'col-original'})
                col_orig.append(img_left)
                col_trans = soup.new_tag('div', attrs={'class': 'col-translation'})
                col_trans.append(img_right)

                row = _build_row(soup, col_orig, col_trans)
                placeholder.replaceWith(row)
                _save_soup(soup, html_path)
                break

            # ──────────────────────────────────────────
            # 2) TABLOLAR — her iki sütuna kopya
            # ──────────────────────────────────────────
            if tag.name == 'table':
                tag_clone = _clone_tag(soup, tag)

                placeholder = soup.new_tag('div', attrs={'class': '_ph_'})
                tag.replaceWith(placeholder)

                tbl_left = soup.new_tag('div', attrs={'class': 'table-block'})
                tbl_right = soup.new_tag('div', attrs={'class': 'table-block'})
                tbl_left.append(tag)
                tbl_right.append(tag_clone)

                col_orig = soup.new_tag('div', attrs={'class': 'col-original'})
                col_orig.append(tbl_left)
                col_trans = soup.new_tag('div', attrs={'class': 'col-translation'})
                col_trans.append(tbl_right)

                row = _build_row(soup, col_orig, col_trans)
                placeholder.replaceWith(row)
                _save_soup(soup, html_path)
                break

            # ──────────────────────────────────────────
            # 3) BOŞ ELEMENTLERİ ATLA
            # ──────────────────────────────────────────
            if not tag.text.strip():
                continue

            # ──────────────────────────────────────────
            # 4) ÇEVİRİ YAPILACAK METİN
            # ──────────────────────────────────────────
            if not _should_translate(tag):
                continue

            tag_name = tag.name
            inner_html_str = "".join(str(child) for child in tag.contents)

            word_count = count_words_in_html(inner_html_str)
            print(f"-> Çevriliyor: {tag.text[:60].strip()}... (Kelimeler: {word_count})")


            html_force_tag = "```html\n<!DOCTYPE HTML>"
            html_force_tag_end = "```"
            diff_time = 0.0

            if word_count <= max_words:
                batches = [inner_html_str]
            else:
                print(f"   [!] Uzun blok tespit edildi ({word_count} kelime). "
                      f"Cümleler {max_words} kelimeyi geçmeyecek şekilde paketleniyor...")
                sentences = split_into_sentences(inner_html_str)
                batches = []
                current_batch = []
                current_word_count = 0

                for sent in sentences:
                    sent_wc = count_words_in_html(sent)
                    if current_word_count + sent_wc > max_words and current_batch:
                        batches.append(" ".join(current_batch))
                        current_batch = [sent]
                        current_word_count = sent_wc
                    else:
                        current_batch.append(sent)
                        current_word_count += sent_wc

                if current_batch:
                    batches.append(" ".join(current_batch))

            translated_parts = []
            for batch in batches:
                protected_batch, placeholders = protect_all_tags_for_llm(batch)
                protected_batch = protected_batch.replace("\u2022 ", "&bull; ").replace("\u2022", "&bull;")
                batch_str = html_force_tag + protected_batch + html_force_tag_end

                if len(batches) > 1:
                    print(f"      Paket çevriliyor...")

                trans_result, t_time = translator.process(batch_str)
                diff_time += t_time

                if trans_result.startswith(html_force_tag):
                    trans_result = trans_result[len(html_force_tag): -(len(html_force_tag_end))]

                trans_result = restore_all_tags_after_llm(trans_result.strip(), placeholders)
                translated_parts.append(trans_result)

            translated_inner_html = " ".join(translated_parts)
            translated_html_str = f"<{tag_name}>{translated_inner_html}</{tag_name}>"

            placeholder = soup.new_tag('div', attrs={'class': '_ph_'})
            tag.replaceWith(placeholder)

            _strip_text_align(tag)

            col_orig = soup.new_tag('div', attrs={'class': 'col-original'})
            col_orig.append(tag)

            col_trans = soup.new_tag('div', attrs={'class': 'col-translation'})
            translated_soup = BeautifulSoup(translated_html_str, 'html.parser')
            children = (list(translated_soup.body.contents) if translated_soup.body
                        else list(translated_soup.contents))
            for child in children:
                _strip_text_align(child)
                col_trans.append(child)

            row = _build_row(soup, col_orig, col_trans)

            placeholder.replaceWith(row)

            _save_soup(soup, html_path)

            processed_count += 1
            elapsed_time = diff_time.total_seconds() if hasattr(diff_time, 'total_seconds') else diff_time
            print(f"   [OK] Kaydedildi. (Süre: {elapsed_time:.2f} sn)")
            break

        if not found_unprocessed:
            break

    print(f"\n[+] İşlem Tamamlandı! Toplam {processed_count} yeni blok çevrildi.")


if __name__ == "__main__":
    HTML_FILE = "index.html"

    if os.path.exists(HTML_FILE):
        process_html_live(HTML_FILE)
    else:
        print(f"Hata: '{HTML_FILE}' dosyası bulunamldı!")
