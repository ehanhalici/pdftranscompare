import pymupdf
import base64
import statistics
import re
import hashlib
from bs4 import BeautifulSoup, Tag, NavigableString

# ============================================================
# 1. İSTATİSTİKSEL YARDIMCI FONKSİYONLAR
# ============================================================

def jenks_natural_breaks_2(values):
    if len(values) < 2:
        return None, 0.0

    sorted_vals = sorted(values)
    n = len(sorted_vals)

    total_mean = sum(sorted_vals) / n
    total_ss = sum((v - total_mean) ** 2 for v in sorted_vals)

    if total_ss == 0:
        return None, 0.0

    best_gvf = 0.0
    best_break = None

    for i in range(1, n):
        c1 = sorted_vals[:i]
        c2 = sorted_vals[i:]
        m1 = sum(c1) / len(c1)
        m2 = sum(c2) / len(c2)
        ss1 = sum((v - m1) ** 2 for v in c1)
        ss2 = sum((v - m2) ** 2 for v in c2)
        gvf = (total_ss - ss1 - ss2) / total_ss
        if gvf > best_gvf:
            best_gvf = gvf
            best_break = (sorted_vals[i - 1] + sorted_vals[i]) / 2

    return best_break, best_gvf

def find_adaptive_threshold(values):
    if not values or len(values) < 2:
        return None

    positive = [v for v in values if v > 0]
    if len(positive) < 2:
        return None

    break_val, gvf = jenks_natural_breaks_2(positive)
    if gvf > 0.5 and break_val is not None:
        return break_val

    sorted_gaps = sorted(positive)
    if len(sorted_gaps) >= 2 and sorted_gaps[-1] > sorted_gaps[-2] * 2:
        return (sorted_gaps[-2] + sorted_gaps[-1]) / 2

    return None


# ============================================================
# 2. XY-CUT: BLOK ÇIKARMA VE SIRALAMA
# ============================================================

def extract_text_blocks_with_xy_cut(page):
    """
    PyMuPDF'ten ham metin bloklarını çıkarır ve XY-Cut ile okuma sırasına göre dizer.
    """
    raw_blocks = page.get_text("dict").get("blocks", [])
    text_blocks = []
    
    for b in raw_blocks:
        if b.get("type") == 0:  # 0 = Metin bloğu
            text_blocks.append({
                'type': 'text_block',
                'x0': b['bbox'][0],
                'y0': b['bbox'][1],
                'x1': b['bbox'][2],
                'y1': b['bbox'][3],
                'lines': b.get('lines', [])
            })
            
    return xy_cut_blocks(text_blocks)

def xy_cut_blocks(blocks):
    """XY-Cut algoritması — Sütun/bölüm ayrımını yapar."""
    if len(blocks) <= 1:
        return blocks

    sorted_by_x = sorted(blocks, key=lambda b: (b['x0'], b['y0']))
    x_gaps = []
    for i in range(len(sorted_by_x) - 1):
        gap = sorted_by_x[i + 1]['x0'] - sorted_by_x[i]['x1']
        x_gaps.append(gap)

    if x_gaps:
        x_threshold = find_adaptive_threshold(x_gaps)
        if x_threshold is not None:
            max_xgap = max(x_gaps)
            if max_xgap > x_threshold:
                cut_idx = x_gaps.index(max_xgap)
                left = sorted_by_x[:cut_idx + 1]
                right = sorted_by_x[cut_idx + 1:]
                if left and right:
                    return xy_cut_blocks(left) + xy_cut_blocks(right)

    sorted_by_y = sorted(blocks, key=lambda b: (b['y0'], b['x0']))
    y_gaps = []
    for i in range(len(sorted_by_y) - 1):
        gap = sorted_by_y[i + 1]['y0'] - sorted_by_y[i]['y1']
        y_gaps.append(gap)

    if y_gaps:
        y_threshold = find_adaptive_threshold(y_gaps)
        if y_threshold is not None:
            max_ygap = max(y_gaps)
            if max_ygap > y_threshold:
                cut_idx = y_gaps.index(max_ygap)
                top = sorted_by_y[:cut_idx + 1]
                bottom = sorted_by_y[cut_idx + 1:]
                if top and bottom:
                    return xy_cut_blocks(top) + xy_cut_blocks(bottom)

    return sorted_by_y


# ============================================================
# 3. YAKIN BLOKLARI BİRLEŞTİRME
# ============================================================

def merge_nearby_blocks(blocks):
    if len(blocks) <= 1:
        return blocks

    all_line_heights = []
    all_char_widths = []
    
    for block in blocks:
        if block.get('type') != 'text_block':
            continue
        for line in block.get('lines', []):
            lh = line["bbox"][3] - line["bbox"][1]
            if lh > 2:
                all_line_heights.append(lh)
            
            lw = line["bbox"][2] - line["bbox"][0]
            span_chars = sum(len(span.get("text", "").strip()) for span in line.get("spans", []))
            if span_chars > 0 and lw > 1:
                all_char_widths.append(lw / span_chars)

    median_line_h = statistics.median(all_line_heights) if all_line_heights else 12.0
    median_char_w = statistics.median(all_char_widths) if all_char_widths else 6.0
    merge_y_threshold = median_line_h * 0.5  

    blocks = sorted(blocks, key=lambda b: (b['y0'], b['x0']))
    merged = [blocks[0]]

    for block in blocks[1:]:
        prev = merged[-1]
        
        if prev.get('type') != 'text_block' or block.get('type') != 'text_block':
            merged.append(block)
            continue

        x_overlap = min(prev['x1'], block['x1']) - max(prev['x0'], block['x0'])
        has_x_overlap = x_overlap > 0

        y_overlap = min(prev['y1'], block['y1']) - max(prev['y0'], block['y0'])
        has_y_overlap = y_overlap > 0

        y_gap = block['y0'] - prev['y1']
        y_gap_small = -2 <= y_gap < merge_y_threshold
        
        x_gap_horizontal = block['x0'] - prev['x1']

        should_merge = False

        if has_x_overlap and y_gap_small:
            prev_lines = prev.get('lines', [])
            prev_max_x1 = max(l["bbox"][2] for l in prev_lines) if prev_lines else prev['x1']
            prev_last_x1 = prev_lines[-1]["bbox"][2] if prev_lines else prev['x1']
            
            prev_ends_early = (prev_max_x1 - prev_last_x1) > (median_char_w * 3)
            
            curr_lines = block.get('lines', [])
            curr_first_x0 = curr_lines[0]["bbox"][0] if curr_lines else block['x0']
            
            curr_is_indented = (curr_first_x0 - prev['x0']) > (median_char_w * 2)

            if prev_ends_early:
                pass 
            elif curr_is_indented:
                pass 
            else:
                should_merge = True

        elif has_y_overlap and x_gap_horizontal < (median_line_h * 2):
            should_merge = True

        if should_merge:
            merged[-1] = {
                'type': 'text_block',
                'x0': min(prev['x0'], block['x0']),
                'y0': min(prev['y0'], block['y0']),
                'x1': max(prev['x1'], block['x1']),
                'y1': max(prev['y1'], block['y1']),
                'lines': prev['lines'] + block['lines'],
            }
            y_tol = median_line_h * 0.2
            merged[-1]['lines'] = sorted(
                merged[-1]['lines'], 
                key=lambda l: (round(l['bbox'][1] / y_tol) * y_tol, l['bbox'][0])
            )
        else:
            merged.append(block)

    return merged


# ============================================================
# 4. FONT VE BLOK TİPİ TESPİTİ
# ============================================================

_CODE_FONT_FAMILIES = {
    # Klasik kod fontları
    'helvetica', 'courier', 'mono', 'consolas', 'menlo', 
    'dejavusansmono', 'liberationmono',
    # Modern programcı fontları
    'firacode', 'jetbrains', 'sourcecodepro', 'sourcecode',
    'inconsolata', 'hack', 'ubuntumono', 'ubunt',
    'robotomono', 'iosevka', 'pragmata', 'dankmono',
    'cascadia', 'victormono', 'sfmono', 'menlo',
    # LaTeX listings / minted fontları
    'lmmonolt', 'lmmono', 'txmono', 'pxmono',
    'beramono', 'dejavumono', 'txtt',
    # Genel mono keyword'leri
    'monospace', 'typewriter', 'fixed',
}

def is_code_span(span):
    """
    Bir span'ın kod fontu kullanıp kullanmadığını tespit eder.
    
    Kod fontları: Helvetica, Courier, monospace ailesi fontlar.
    LaTeX PDF'lerde kod blokları genellikle bu fontlarla yazılır.
    Ayrıca renk bilgisi de ipucu verebilir (mavi renk = kod linki).
    """
    font = span.get("font", "").lower()
    for cf in _CODE_FONT_FAMILIES:
        if cf in font:
            return True
    return False

def is_code_block(block):
    """
    Bir bloğun ağırlıklı olarak kod fontu içerip içermediğini tespit eder.
    
    Kod bloklarında >%60 karakter kod fontundaysa True döner.
    Bu bloklar <pre><code> ile sarılmalıdır.
    """
    total_chars = 0
    code_chars = 0
    
    for line in block.get('lines', []):
        for span in line.get('spans', []):
            text = span.get("text", "").strip()
            chars = len(text)
            if chars == 0:
                continue
            total_chars += chars
            if is_code_span(span):
                code_chars += chars
    
    if total_chars == 0:
        return False
    return (code_chars / total_chars) > 0.6

def calculate_body_font_size(blocks):
    """
    Verilen blok listesinden body text font boyutunun medyanını hesaplar.
    
    ÖNEMLİ: Kod fontlarını (Helvetica, Courier vb.) hariç tutar çünkü
    kod fontları genellikle body text'ten daha küçük boyutludur.
    
    Bu fonksiyon hem sayfa bazlı hem de belge bazlı kullanılabilir.
    pdf_to_clean_html içindeki belge bazlı hesaplama için tüm sayfaların
    blokları birleştirilerek bu fonksiyona gönderilir.
    """
    body_sizes = []
    
    for block in blocks:
        if block.get('type') != 'text_block':
            continue
        for line in block.get('lines', []):
            for span in line.get('spans', []):
                text = span.get('text', '').strip()
                if not text:
                    continue
                if is_code_span(span):
                    continue
                body_sizes.append(span.get('size', 12))
    
    if not body_sizes:
        all_sizes = []
        for block in blocks:
            if block.get('type') != 'text_block':
                continue
            for line in block.get('lines', []):
                for span in line.get('spans', []):
                    text = span.get('text', '').strip()
                    if text:
                        all_sizes.append(span.get('size', 12))
        return statistics.median(all_sizes) if all_sizes else 12.0
    
    return statistics.median(body_sizes)


def classify_block_heading(block, body_font_size):
    """
    Bir bloğun heading olup olmadığını tespit eder.
    
    İki kriter kullanır:
    1. Font BOYUTU oranı: Body font'tan belirgin şekilde büyükse heading
    2. Font STİLİ (bold): Aynı boyutta ama çoğunluğu bold ve satır sayısı azsa heading
    
    Kod blokları otomatik olarak hariç tutulur (asla heading olamazlar).
    """
    if is_code_block(block):
        return "p"
    
    total_chars = 0
    size_chars = {'h1': 0, 'h2': 0, 'h3': 0, 'h4': 0, 'h5': 0, 'h6': 0}
    bold_chars = 0
    non_code_chars = 0

    for line in block.get('lines', []):
        for span in line.get('spans', []):
            text = span.get("text", "").strip()
            chars = len(text)
            if chars == 0: continue

            if is_code_span(span):
                continue
            
            size = span.get("size", 0)
            font = span.get("font", "").lower()
            total_chars += chars
            non_code_chars += chars
            
            if "bold" in font or "black" in font:
                bold_chars += chars

            if body_font_size > 0:
                if size >= body_font_size * 2.0: size_chars['h1'] += chars
                elif size >= body_font_size * 1.7: size_chars['h2'] += chars
                elif size >= body_font_size * 1.4: size_chars['h3'] += chars
                elif size >= body_font_size * 1.2: size_chars['h4'] += chars
                elif size >= body_font_size * 1.1: size_chars['h5'] += chars
                elif size >= body_font_size * 1.05: size_chars['h6'] += chars

    if total_chars == 0:
        return "p"

    # Kriter 1: Font boyutu oranı (mevcut yaklaşım)
    cum_chars = 0
    for h_tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        cum_chars += size_chars[h_tag]
        if (cum_chars / total_chars) > 0.5:
            return h_tag

    # Kriter 2: Bold-based heading tespiti
    # Bazı PDF'lerde heading'ler body ile aynı boyutta ama BOLD yazılır.
    # Özellikle LaTeX kitaplarında bölüm başlıkları böyle olabilir.
    # Koşullar:
    #   - >%80 karakter bold
    #   - Blok kısa (≤3 satır)
    #   - Sadece bold text değil, anlamlı bir başlık
    num_lines = len(block.get('lines', []))
    bold_ratio = bold_chars / total_chars if total_chars > 0 else 0
    
    if bold_ratio > 0.8 and num_lines <= 3:
        # Bold ve kısa → muhtemelen heading
        # Seviyeyi belirlemek için boyut/bold kombinasyonu kullan
        # Varsayılan: h4 (daha doğru seviye belirleme için ek bağlam gerekir)
        return "h4"

    return "p"


# ============================================================
# 5. CÜMLE AYIRMA (TAG-SAFE)
# ============================================================

ABBREVIATION_PATTERNS = re.compile(
    r'^(?:[Dd]r|[Mm]r|[Mm]rs|[Mm]ss|[Pp]rof|[Ss]r|[Jj]r|[Ss]t|[Aa]ve|[Vv]s|[Ee]tc|[Ee]\.g|[Ii]\.e|[Uu]\.s|[Nn]o)\.?$', 
    re.IGNORECASE
)

def split_into_sentences(text):
    """HTML taglarını koruyarak (açılıp/kapanmasını izleyerek) güvenli cümle bölme yapar."""
    if not text or not text.strip():
        return []

    token_pattern = re.compile(r'(<[^>]+>)|(\s+)|([^\s<]+)')
    tokens = [m.group(0) for m in token_pattern.finditer(text) if m.group(0)]

    sentences = []
    current_sentence = []
    open_tags = 0
    pending_split = False
    void_elements = {'br', 'hr', 'img', 'input', 'meta', 'link'}

    def is_abbreviation(word):
        clean = word.rstrip('\'"\u201d\u2019)]').rstrip('.!?')
        if ABBREVIATION_PATTERNS.match(clean) or clean.isdigit():
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
                tag_match = re.match(r'<([a-zA-Z0-9]+)', stripped)
                if tag_match and tag_match.group(1).lower() not in void_elements:
                    open_tags += 1 

        if stripped and not stripped.startswith('<') and stripped[-1] in '.!?':
            if not is_abbreviation(stripped):
                next_word_token = None
                next_word_idx = -1
                
                for j in range(i + 1, len(tokens)):
                    if not tokens[j].strip() or tokens[j].strip().startswith('<'):
                        continue
                    next_word_token = tokens[j].strip()
                    next_word_idx = j
                    break
                
                if next_word_token is None:
                    pending_split = True
                elif next_word_token[0].isupper() or next_word_token[0].isdigit() or next_word_token[0] in '("\'\u201c\u2018':
                    pending_split = True
                else:
                    has_space = any(t.isspace() for t in tokens[i+1:next_word_idx])
                    if has_space or stripped[-1] in '!?':
                        pending_split = True

        if pending_split and open_tags == 0:
            sentence = "".join(current_sentence).strip()
            if sentence: sentences.append(sentence)
            current_sentence = []
            pending_split = False

    if current_sentence:
        sentence = "".join(current_sentence).strip()
        if sentence: sentences.append(sentence)

    return sentences


# ============================================================
# 6. RESİM ÇIKARMA (HASH KORUMALI)
# ============================================================
def extract_page_images(page, doc):
    images = []
    seen_hashes = set()
    seen_rects = []
    
    def is_rect_seen(new_rect):
        for r in seen_rects:
            if (abs(new_rect.x0 - r.x0) < 5 and abs(new_rect.y0 - r.y0) < 5 and 
                abs(new_rect.x1 - r.x1) < 5 and abs(new_rect.y1 - r.y1) < 5):
                return True
        return False

    try:
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            try:
                img_dict = doc.extract_image(xref)
                if img_dict and "image" in img_dict:
                    rects = page.get_image_rects(xref)
                    if not rects: continue
                    
                    rect = rects[0]
                    if is_rect_seen(rect): continue
                        
                    img_bytes = img_dict["image"]
                    img_hash = hashlib.md5(img_bytes).hexdigest()
                    
                    if img_hash in seen_hashes: continue
                        
                    images.append({
                        'type': 'image',
                        'x0': rect.x0, 'y0': rect.y0,
                        'x1': rect.x1, 'y1': rect.y1,
                        'data': {'image': img_bytes, 'ext': img_dict.get("ext", "png")}
                    })
                    seen_hashes.add(img_hash)
                    seen_rects.append(rect)
            except Exception:
                continue
    except Exception:
        pass

    return images


# ============================================================
# 7. HTML ÜRETİMİ (BeautifulSoup İLE)
# ============================================================


def apply_latex_to_html(text):
    """
    LaTeX komutlarını ve özel karakterlerini HTML karşılıklarına çevirir.
    """
    # ---- LaTeX biçimlendirme komutları ----
    text = re.sub(r'\\textbf\{([^}]*)\}',  r'<b>\1</b>', text)
    text = re.sub(r'\\textit\{([^}]*)\}',  r'<i>\1</i>', text)
    text = re.sub(r'\\underline\{([^}]*)\}', r'<u>\1</u>', text)
    text = re.sub(r'\\emph\{([^}]*)\}',    r'<em>\1</em>', text)
    text = re.sub(r'\\textsuperscript\{([^}]*)\}', r'<sup>\1</sup>', text)
    text = re.sub(r'\\textsubscript\{([^}]*)\}',   r'<sub>\1</sub>', text)
    text = re.sub(r'\\texttt\{([^}]*)\}',  r'<code>\1</code>', text)
    text = re.sub(r'\\textsc\{([^}]*)\}',  r'<span style="font-variant:small-caps">\1</span>', text)
    
    # ---- LaTeX tire ve tırnak işaretleri ----
    text = re.sub(r'---',  '\u2014', text)                         # Em-dash
    text = re.sub(r'--',   '\u2013', text)                         # En-dash
    text = re.sub(r"``(.*?)''", '\u201c' + r'\1' + '\u201d', text)  # LaTeX çift tırnağı
    text = re.sub(r"`(.*?)'",   '\u2018' + r'\1' + '\u2019', text)  # LaTeX tek tırnağı
    
    # ---- LaTeX özel semboller ----
    text = re.sub(r'\\ldots',                         '\u2026', text)
    text = re.sub(r'(?<!\.)\.\.\.(?!\.)',             '\u2026', text)
    text = re.sub(r'\\textregistered',                '\u00ae', text)
    text = re.sub(r'\\copyright',                     '\u00a9', text)
    text = re.sub(r'\\texttrademark',                 '\u2122', text)
    text = re.sub(r'\\textdegree',                    '\u00b0', text)
    text = re.sub(r'\\pm',                            '\u00b1', text)
    text = re.sub(r'\\times',                         '\u00d7', text)
    text = re.sub(r'\\div',                           '\u00f7', text)
    text = re.sub(r'\\leq?',                          '\u2264', text)
    text = re.sub(r'\\geq?',                          '\u2265', text)
    text = re.sub(r'\\neq?',                          '\u2260', text)
    text = re.sub(r'\\approx',                        '\u2248', text)
    text = re.sub(r'\\infty',                         '\u221e', text)
    text = re.sub(r'\\partial',                       '\u2202', text)
    text = re.sub(r'\\nabla',                         '\u2207', text)
    text = re.sub(r'\\sum',                           '\u2211', text)
    text = re.sub(r'\\prod',                          '\u220f', text)
    text = re.sub(r'\\int',                           '\u222b', text)
    text = re.sub(r'\\sqrt',                          '\u221a', text)
    text = re.sub(r'\\alpha',                         '\u03b1', text)
    text = re.sub(r'\\beta',                          '\u03b2', text)
    text = re.sub(r'\\gamma',                         '\u03b3', text)
    text = re.sub(r'\\delta',                         '\u03b4', text)
    text = re.sub(r'\\epsilon',                       '\u03b5', text)
    text = re.sub(r'\\lambda',                        '\u03bb', text)
    text = re.sub(r'\\mu',                            '\u03bc', text)
    text = re.sub(r'\\pi',                            '\u03c0', text)
    text = re.sub(r'\\sigma',                         '\u03c3', text)
    text = re.sub(r'\\theta',                         '\u03b8', text)
    text = re.sub(r'\\omega',                         '\u03c9', text)
    text = re.sub(r'\\Omega',                         '\u03a9', text)
    
    # ---- LaTeX boşluk ve kesme işaretleri ----
    text = re.sub(r'~',     '\u00a0', text)
    text = re.sub(r'\\,',   '\u2009', text)
    text = re.sub(r'\\;',   '\u2005', text)
    text = re.sub(r'\\!',   '', text)
    text = re.sub(r'\\quad', '\u2001', text)
    text = re.sub(r'\\qquad','\u2001\u2001', text)
    
    # ---- LaTeX kaçış karakterleri ----
    text = re.sub(r'\\&',  '&amp;', text)
    text = re.sub(r'\\%',  '%',     text)
    text = re.sub(r'\\\$', '$',     text)
    text = re.sub(r'\\#',  '#',     text)
    text = re.sub(r'\\_',  '_',     text)
    text = re.sub(r'\\\{', '{',     text)
    text = re.sub(r'\\\}', '}',     text)
    
    # ---- LaTeX satır sonu ve paragraf ----
    text = re.sub(r'\\\\',  '<br>',   text)
    text = re.sub(r'\\par', '</p><p>', text)
    
    # ---- LaTeX çevreleri (basit düzey) ----
    text = re.sub(r'\\begin\{itemize\}',  '<ul>',  text)
    text = re.sub(r'\\end\{itemize\}',    '</ul>', text)
    text = re.sub(r'\\begin\{enumerate\}', '<ol>',  text)
    text = re.sub(r'\\end\{enumerate\}',   '</ol>', text)
    text = re.sub(r'\\begin\{quote\}',     '<blockquote>', text)
    text = re.sub(r'\\end\{quote\}',       '</blockquote>', text)
    text = re.sub(r'\\item\s*',            '<li>',  text)
    
    # ---- Math mode (inline) ----
    text = re.sub(r'\$([^$]+)\$', r'<span class="math-inline">\1</span>', text)
    
    return text


def build_line_text(line, return_origin_x=False):
    """
    Satır metnini span'lardan derler.
    
    Font bilgisine göre:
    - Kod fontu (Helvetica, Courier) → <code> tagı
    - Bold font → <b> tagı
    - Italic font → <i> tagı
    - İkisi birden → <code><b> gibi iç içe
    
    HTML escape işlemini uygular.
    
    return_origin_x=True ise, (metin, origin_x) tuple döner.
    origin_x, satırdaki ilk görünür span'ın x-koordinatıdır.
    Kod bloğu girinti hesaplamasında kullanılır.
    """
    parts = []
    first_origin_x = None
    
    for span in line.get("spans", []):
        t = span.get("text", "").replace("<", "&lt;").replace(">", "&gt;").strip()
        if not t:
            continue

        if first_origin_x is None:
            origin = span.get("origin")
            if origin and len(origin) >= 1:
                first_origin_x = origin[0]
        
        f = span.get("font", "").lower()
        is_code = is_code_span(span)
        is_bold = "bold" in f or "black" in f
        is_italic = "italic" in f or "oblique" in f

        # Tag sırası: code en dışta, sonra bold, sonra italic
        # <code><b><i>text</i></b></code>
        open_tags = ""
        close_tags = ""
        
        if is_code:
            open_tags += "<code>"
            close_tags = "</code>" + close_tags
        if is_bold and not is_code:
            open_tags += "<b>"
            close_tags = "</b>" + close_tags
        if is_italic and not is_code:
            open_tags += "<i>"
            close_tags = "</i>" + close_tags
        
        t = open_tags + t + close_tags
        parts.append(t)
    
    if not parts:
        if return_origin_x:
            return "", None
        return ""

    result = parts[0]
    for part in parts[1:]:
        if result.endswith("-"):
            result += part
        else:
            result += " " + part
    
    if return_origin_x:
        return result, first_origin_x
    return result


def _is_bullet_only(text):
    """
    Metnin sadece bir bullet/liste işareti olup olmadığını kontrol eder.
    """
    stripped = re.sub(r'^(?:&emsp;|\s|<br>)+', '', text).strip()
    # HTML taglarını kaldır (bold/italic/code wrapper olabilir)
    stripped = re.sub(r'</?[bi]', '', stripped).strip()
    stripped = re.sub(r'</?code>', '', stripped).strip()
    return bool(re.match(r'^[\u2022\*\-\u25e6\u25aa]\s*$', stripped))


def detect_list_item(text):
    """
    Metnin bir liste öğesi olup olmadığını tespit eder.
    """
    # Öndeki &emsp;, boşluk ve <br> taglarını temizle
    stripped = re.sub(r'^[\u2003\u2002&nbsp;\s<br>]+', '', text).strip()

    clean = re.sub(r'</?[bi]>', '', stripped).strip()
    clean = re.sub(r'</?code>', '', clean).strip()
    
    # ---- Sırasız liste: •, *, -, ◦, ▪ ----
    m = re.match(r'^([\u2022\*\-\u25e6\u25aa])\s+(.*)', clean, re.DOTALL)
    if m and m.group(2).strip():
        return ('ul', m.group(2))
    
    # Bullet tek başına (metin yok)
    if re.match(r'^[\u2022\*\-\u25e6\u25aa]\s*$', clean):
        return ('ul_pending', '')
    
    # ---- Sıralı liste: 1., a), i. vb. ----
    m = re.match(r'^(\d+\.)\s+(.*)', clean, re.DOTALL)
    if m and m.group(2).strip():
        return ('ol', m.group(2))
    
    m = re.match(r'^([a-zA-Z]\))\s+(.*)', clean, re.DOTALL)
    if m and m.group(2).strip():
        return ('ol', m.group(2))
    
    m = re.match(r'^([ixvIXV]+\.)\s+(.*)', clean, re.DOTALL)
    if m and m.group(2).strip():
        return ('ol', m.group(2))
    
    # ---- Alıntı: > ----
    m = re.match(r'^>\s+(.*)', clean, re.DOTALL)
    if m and m.group(1).strip():
        return ('blockquote', m.group(1))
    
    return None


def calculate_median_line_height(blocks):
    """Bloklardaki satır yüksekliklerinin medyanını hesaplar."""
    heights = []
    for block in blocks:
        if block.get('type') != 'text_block':
            continue
        for line in block.get('lines', []):
            h = line["bbox"][3] - line["bbox"][1]
            if h > 2:
                heights.append(h)
    return statistics.median(heights) if heights else 12.0


def _is_page_number(text, x0, x1, page_width):
    """
    Bir metin parçasının sayfa numarası olup olmadığını tespit eder.
    
    Sayfa numaraları genellikle:
    - Sadece rakam içerir (1-999 arası)
    - Sayfanın çok sağında veya çok solundadır
    - Kısa metinlerdir (1-4 karakter)
    """
    clean = re.sub(r'<[^>]+>', '', text).strip()
    if re.match(r'^\d{1,4}\.?$', clean):
        if x0 > page_width * 0.85:
            return True
        if x1 < page_width * 0.15 and len(clean) <= 3:
            return True
    return False


def generate_html_from_blocks(sorted_blocks, page_width, median_height, 
                               body_font_size, start_chunk_id=1, 
                               ENABLE_LAYOUT_ANALYSIS=True,
                               carry_over_bullet=None):
    """
    Blokları HTML'e dönüştürür. BeautifulSoup kullanarak temiz ve doğru HTML üretir.
    
    Parametreler:
    - median_height: Satır yüksekliği medyanı (düzen analizi için)
    - body_font_size: Body metin font boyutu medyanı (heading tespiti için)
      Bu ikisi FARKLI olabilir! Kod blokları olan PDF'lerde median_height
      düşük olabilir ama body_font_size yüksek olmalıdır.
    
    ÖNEMLİ: body_font_size, kod fontları hariç hesaplanmalıdır.
    Aksi takdirde body text yanlışlıkla heading olarak sınıflandırılır.
    """
    chunk_id = start_chunk_id
    
    # ========================================
    # ADIM 1: Tüm satırları topla
    # ========================================
    collected = []
    
    for el in sorted_blocks:
        if el.get('type') == 'image':
            collected.append({
                'type': 'image',
                'data': el['data'],
                'x0': el['x0'], 'y0': el['y0'],
                'x1': el['x1'], 'y1': el['y1']
            })
            continue
        
        if el.get('type') != 'text_block':
            continue
        
        is_code = is_code_block(el)
        block_tag = "code_block" if is_code else classify_block_heading(el, body_font_size)
        
        for line in el.get('lines', []):
            if is_code:
                line_text, origin_x = build_line_text(line, return_origin_x=True)
            else:
                line_text = build_line_text(line)
                origin_x = None
            
            if not line_text.strip():
                continue

            if _is_page_number(line_text, line['bbox'][0], line['bbox'][2], page_width):
                continue
            
            collected.append({
                'type': 'text',
                'text': line_text,
                'x0': line['bbox'][0],
                'y0': line['bbox'][1],
                'x1': line['bbox'][2],
                'y1': line['bbox'][3],
                'block_tag': block_tag,
                'origin_x': origin_x  # Kod bloğu girinti hesaplamasında kullanılır
            })
    
    if not collected:
        return "", chunk_id
    
    # ========================================
    # ADIM 2: Aynı y-düzlemindeki satırları birleştir
    # ========================================
    text_items = [c for c in collected if c['type'] == 'text']
    image_items = [c for c in collected if c['type'] == 'image']
    
    # Önce y'ye, sonra x'e göre sırala
    text_items.sort(key=lambda l: (l['y0'], l['x0']))
    
    # y-birleştirme eşik değeri
    y_merge_threshold = median_height * 0.5
    merged = []
    
    for item in text_items:
        if merged:
            prev = merged[-1]
            y_gap = item['y0'] - prev['y0']
            
            both_code = (prev.get('block_tag') == 'code_block' and 
                         item.get('block_tag') == 'code_block')
            
            should_merge = False
            
            if both_code and y_gap < y_merge_threshold:
                should_merge = True

            elif (not both_code and 
                  y_gap < y_merge_threshold and 
                  prev.get('block_tag') == item.get('block_tag')):
                should_merge = True
            
            if should_merge:
                if item['x0'] < prev['x0']:
                    if item.get('origin_x') is not None:
                        prev['origin_x'] = item['origin_x']
                    prev['text'] = item['text'] + " " + prev['text']
                    prev['x0'] = item['x0']
                else:
                    x_gap = item['x0'] - prev['x1']
                    if both_code:
                        separator = " "
                    else:
                        separator = " " if x_gap > median_height else ""
                    prev['text'] = prev['text'] + separator + item['text']
                    prev['x1'] = max(prev['x1'], item['x1'])
                
                prev['y1'] = max(prev['y1'], item['y1'])
                
                if item.get('block_tag', 'p').startswith('h'):
                    prev['block_tag'] = item['block_tag']
                continue
        
        merged.append(item)
    
    all_items = merged + image_items
    all_items.sort(key=lambda l: (l.get('y0', 0), l.get('x0', 0)))
    
    # ========================================
    # ADIM 3: Düzen analizi (Layout Analysis)
    # ========================================
    if ENABLE_LAYOUT_ANALYSIS and merged:
        normal_items = [m for m in merged if m.get('block_tag') != 'code_block']
        
        if normal_items:
            all_starts = [m['x0'] for m in normal_items]
            all_ends = [m['x1'] for m in normal_items]
            page_x_start = statistics.median(all_starts) if all_starts else 0
            page_x_end = statistics.median(all_ends) if all_ends else page_width
        else:
            page_x_start = 0
            page_x_end = page_width

        char_widths = []
        for m in merged:
            clean_text = re.sub(r'<[^>]+>', '', m['text']).strip()
            char_count = len(clean_text)
            width = m['x1'] - m['x0']
            if char_count > 0 and width > 1:
                char_widths.append(width / char_count)
        median_char_w = statistics.median(char_widths) if char_widths else 6.0
        
        indent_threshold = max(median_char_w * 2, median_height * 0.3)
        short_line_threshold = median_height * 0.5
    else:
        page_x_start = 0
        page_x_end = page_width
        indent_threshold = 0
        short_line_threshold = 0
        median_char_w = 6.0
    
    # ========================================
    # ADIM 4: BeautifulSoup ile HTML oluştur
    # ========================================
    soup = BeautifulSoup("", "html.parser")
    
    current_list_type = None
    list_tag = None
    para_parts = []
    para_is_heading = None
    code_buffer = []
    in_code_block = False
    prev_item = None
    pending_bullet = carry_over_bullet
    
    last_li_tag = None         # Son yazdırılan <li> Tag referansı
    list_indent_x0 = None      # Son liste elemanının x0 konumu (girinti karşılaştırması için)
    
    
    def close_list():
        """Açık liste tag'ını kapatır."""
        nonlocal current_list_type, list_tag, last_li_tag, list_indent_x0
        current_list_type = None
        list_tag = None
        last_li_tag = None
        list_indent_x0 = None
    
    def open_list(ltype):
        nonlocal current_list_type, list_tag
        if ltype == current_list_type and list_tag is not None:
            return
        close_list()
        flush_para()
        flush_code()
        if ltype == 'ul':
            list_tag = soup.new_tag("ul")
            soup.append(list_tag)
        elif ltype == 'ol':
            list_tag = soup.new_tag("ol")
            soup.append(list_tag)
        current_list_type = ltype
    
    def append_html_to_tag(parent, html_str):
        """HTML string'ini parse edip bir bs4 Tag'ına çocuk olarak ekler."""
        frag = BeautifulSoup(html_str, "html.parser")
        for child in list(frag.children):
            if isinstance(child, Tag):
                child_html = str(child)
                child_frag = BeautifulSoup(child_html, "html.parser")
                for inner_child in list(child_frag.children):
                    parent.append(inner_child.extract())
            elif child is not None:
                parent.append(NavigableString(str(child)))
    
    def flush_code():
        """
        Birikmiş kod satırlarını <pre><code> olarak HTML'e yazar.
        Kod bloklarında her satır <br> ile ayrılır, cümle bölmesi yapılmaz.
        
        GIRINTİ HESAPLAMASI:
        Kod bloğundaki tüm satırların origin_x değerlerini toplayıp,
        en küçük origin_x'i baz alarak her satıra uygun sayıda boşluk ekler.
        Boşluk sayısı = (satır_origin_x - min_origin_x) / char_width
        char_width, kod fontunun ortalama karakter genişliğidir.
        """
        nonlocal code_buffer, chunk_id, in_code_block
        if not code_buffer:
            return
        
        close_list()
        
        # ---- Girinti hesaplaması ----
        # Tüm origin_x değerlerini topla (None olmayan)
        # Yorum satırlarını (// ile başlayan) girinti hesaplamasından hariç tut TODO bu sadece CPP ye ozeldir. sonradan degisecek
        # çünkü bunlar kodun sağına hizalanmış yorumlardır, girintili kod satırları değil.
        origin_xs = []
        for text, ox in code_buffer:
            if ox is None:
                continue
            clean = re.sub(r'<[^>]+>', '', text).strip()
            if clean.startswith('//') or clean.startswith('/*'):
                continue
            origin_xs.append(ox)
        
        if origin_xs:
            min_origin_x = min(origin_xs)
            
            # Benzersiz girinti seviyelerini tespit et.
            if len(set(origin_xs)) > 1:
                sorted_unique = sorted(set(origin_xs))
                diffs = [sorted_unique[i+1] - sorted_unique[i] 
                         for i in range(len(sorted_unique)-1) 
                         if sorted_unique[i+1] - sorted_unique[i] > 0.5]
                if diffs:
                    indent_unit = min(diffs)
                else:
                    indent_unit = 1.0
                indent_unit = max(indent_unit, 1.0)
            else:
                indent_unit = 1.0
            
            indented_lines = []
            last_code_indent = 0
            
            for text, ox in code_buffer:
                if ox is not None:
                    clean = re.sub(r'<[^>]+>', '', text).strip()
                    is_comment = clean.startswith('//') or clean.startswith('/*')
                    
                    if is_comment:
                        indent_spaces = "    " * last_code_indent
                        indented_lines.append(indent_spaces + text)
                    else:
                        indent_count = round((ox - min_origin_x) / indent_unit)
                        indent_count = max(0, indent_count)
                        last_code_indent = indent_count

                        indent_spaces = "    " * indent_count
                        indented_lines.append(indent_spaces + text)
                else:
                    indented_lines.append(text)
            
            code_text = "\n".join(indented_lines)
        else:
            code_text = "\n".join(text for text, _ in code_buffer)
        
        code_buffer = []
        in_code_block = False
        
        processed = apply_latex_to_html(code_text)
        
        pre = soup.new_tag("pre")
        code = soup.new_tag("code", attrs={"data-sid": str(chunk_id)})
        append_html_to_tag(code, processed)
        pre.append(code)
        soup.append(pre)
        chunk_id += 1
    
    def flush_para():
        nonlocal para_parts, para_is_heading, chunk_id
        text = "".join(para_parts).strip()
        para_parts = []
        if not text:
            para_is_heading = None
            return
        
        close_list()
        flush_code()

        processed = apply_latex_to_html(text)

        sentences = split_into_sentences(processed)
        
        tag_name = para_is_heading if para_is_heading else "p"
        p = soup.new_tag(tag_name)
        
        for i, sent in enumerate(sentences):
            s = sent.strip()
            if not s:
                continue
            span = soup.new_tag("span", attrs={"data-sid": str(chunk_id)})
            append_html_to_tag(span, s)
            p.append(span)
            if i < len(sentences) - 1:
                p.append(NavigableString(" "))
            chunk_id += 1
        
        soup.append(p)
        para_is_heading = None
    
    def add_list_item(ltype, item_text, item_x0=None):
        """
        Bir liste öğesini HTML'e yazar; gerekirse <ul>/<ol> açar.
        
        item_x0: Liste elemanının x0 konumu. Çok satırlı liste elemanlarında
        devam satırının bu konumla karşılaştırılması için saklanır.
        """
        nonlocal chunk_id, last_li_tag, list_indent_x0
        flush_para()
        flush_code()
        open_list(ltype)
        clean = apply_latex_to_html(item_text.strip())
        li = soup.new_tag("li", attrs={"data-sid": str(chunk_id)})
        append_html_to_tag(li, clean)
        if list_tag is not None:
            list_tag.append(li)
        last_li_tag = li
        list_indent_x0 = item_x0
        chunk_id += 1
    
    def add_blockquote(item_text):
        nonlocal chunk_id
        flush_para()
        flush_code()
        close_list()
        clean = apply_latex_to_html(item_text.strip())
        bq = soup.new_tag("blockquote", attrs={"data-sid": str(chunk_id)})
        append_html_to_tag(bq, clean)
        soup.append(bq)
        chunk_id += 1
    
    # ========================================
    # Ana işleme döngüsü
    # ========================================
    for item in all_items:
        
        # ---- Resim işleme ----
        if item['type'] == 'image':
            if pending_bullet is not None and current_list_type is not None:
                open_list(current_list_type)
                li = soup.new_tag("li", attrs={"data-sid": str(chunk_id)})
                append_html_to_tag(li, pending_bullet)
                if list_tag is not None:
                    list_tag.append(li)
                chunk_id += 1
                pending_bullet = None
            elif pending_bullet is not None:
                para_parts.append(pending_bullet)
                pending_bullet = None
            
            flush_para()
            flush_code()
            img_data = item['data']
            img_ext = img_data.get("ext", "png")
            b64_string = base64.b64encode(img_data["image"]).decode("utf-8")
            div = soup.new_tag("div", attrs={"class": "row image-row"})
            img = soup.new_tag("img", attrs={
                "src": f"data:image/{img_ext};base64,{b64_string}"
            })
            div.append(img)
            soup.append(div)
            prev_item = item
            pending_bullet = None
            continue
        
        # ---- Metin işleme ----
        line_text = item['text']
        block_tag = item.get('block_tag', 'p')
        is_code = block_tag == 'code_block'
        is_indented = ENABLE_LAYOUT_ANALYSIS and (item['x0'] > page_x_start + indent_threshold)
        is_short = ENABLE_LAYOUT_ANALYSIS and (item['x1'] < page_x_end - short_line_threshold)
        
        # Dikey boşluk kontrolü
        is_new_para = False
        if prev_item and prev_item['type'] == 'text':
            v_gap = item['y0'] - prev_item['y1']
            if v_gap > median_height * 0.5:
                is_new_para = True
        
        # ---- Bekleyen bullet varsa bu satırla birleştir ----
        if pending_bullet is not None:
            line_text = pending_bullet + " " + line_text
            pending_bullet = None
            is_indented = ENABLE_LAYOUT_ANALYSIS and (item['x0'] > page_x_start + indent_threshold)
        
        # ================================================
        # KOD BLOĞU İŞLEME
        # ================================================
        if is_code:
            pending_bullet = None
            last_li_tag = None
            list_indent_x0 = None

            if para_parts:
                flush_para()
            if current_list_type:
                close_list()

            code_text = line_text
            code_text = re.sub(r'</?code>', '', code_text)
            
            in_code_block = True
            code_buffer.append((code_text, item.get('origin_x')))
            prev_item = item
            continue
        else:
            if in_code_block:
                flush_code()
        
        # ================================================
        # ÇOK SATIRLI LİSTE ELEMANI DEVAMI VE ALT GİRİŞ TESPİTİ
        # ================================================
        # Bir liste açıkken ve son <li> tag'ı varken, eğer mevcut satır:
        #   - Yeni bir bullet/liste elemanı DEĞİLSE
        #   - Kod bloğu DEĞİLSE
        #   - Yeni paragraf başlatmıyorsa (küçük dikey boşluk)
        # ise iki ihtimal var:
        #   1. Aynı girinti seviyesi → devam satırı (multi-line list item)
        #   2. Daha derin girinti → alt giriş (nested list item)
        is_list_continuation = False
        is_sub_entry = False
        if (current_list_type is not None 
            and last_li_tag is not None 
            and not is_new_para):
            # Liste tespiti yap (bullet var mı?)
            list_check = detect_list_item(line_text)
            if list_check is None:
                # Bullet yok — devam satırı mı yoksa alt giriş mı?
                if list_indent_x0 is not None:
                    x_offset = item['x0'] - list_indent_x0
                    # Alt giriş eşiği: bullet→text gap'ten büyük,
                    # sub-entry gap'ten küçük bir değer
                    sub_entry_threshold = max(indent_threshold * 2.5, median_char_w * 4)
                    if abs(x_offset) <= sub_entry_threshold:
                        # Aynı veya yakın girinti — devam satırı
                        is_list_continuation = True
                    elif x_offset > sub_entry_threshold:
                        # Daha derin girinti — alt giriş (nested list item)
                        is_sub_entry = True
        
        # ---- Alt giriş işleme: iç içe <ul><li> oluştur ----
        if is_sub_entry and last_li_tag is not None:
            # Ebeveyn <li> içinde iç içe liste var mı kontrol et
            nested_list = last_li_tag.find('ul')
            if nested_list is None:
                nested_list = soup.new_tag("ul")
                last_li_tag.append(nested_list)
            nested_li = soup.new_tag("li", attrs={"data-sid": str(chunk_id)})
            append_html_to_tag(nested_li, apply_latex_to_html(line_text.strip()))
            nested_list.append(nested_li)
            chunk_id += 1
            prev_item = item
            pending_bullet = None
            continue
        
        if is_list_continuation and last_li_tag is not None:
            # Son <li>'ye boşluk + metin ekle
            clean = apply_latex_to_html(line_text.strip())
            last_li_tag.append(NavigableString(" "))
            append_html_to_tag(last_li_tag, clean)
            prev_item = item
            pending_bullet = None
            continue
        
        # ================================================
        # NORMAL METİN İŞLEME
        # ================================================
        
        # ---- Liste tespiti ----
        list_result = detect_list_item(line_text)
        if list_result:
            ltype, content = list_result
            if ltype == 'ul_pending':
                pending_bullet = '\u2022'
                prev_item = item
                continue
            elif ltype == 'blockquote':
                add_blockquote(content)
            else:
                add_list_item(ltype, content, item_x0=item['x0'])
            prev_item = item
            pending_bullet = None
            continue
        
        # ---- Heading bloğu ----
        if block_tag.startswith('h'):
            flush_para()
            para_is_heading = block_tag
        
        # ---- Yeni paragraf ----
        if is_new_para:
            flush_para()
            if not block_tag.startswith('h'):
                para_is_heading = None
        
        # ---- Paragraf buffer'a ekle ----
        if not para_parts:
            if is_indented and ENABLE_LAYOUT_ANALYSIS:
                # Girinti miktarını orantılı hesapla
                # PDF'deki piksel girintiyi em-space sayısına dönüştür
                indent_px = item['x0'] - page_x_start
                if body_font_size > 0:
                    indent_ems = max(1, round(indent_px / body_font_size))
                else:
                    indent_ems = 2
                para_parts.append("\u2003" * indent_ems)
            para_parts.append(line_text)
        else:
            # <br> veya boşluk kararı
            should_br = False
            if prev_item and prev_item['type'] == 'text' and not is_new_para:
                prev_block_tag = prev_item.get('block_tag', 'p')
                # Önceki satır kod bloğundan geliyorsa <br> ekleme
                if prev_block_tag != 'code_block':
                    prev_short = ENABLE_LAYOUT_ANALYSIS and (prev_item['x1'] < page_x_end - short_line_threshold)
                    prev_indented = ENABLE_LAYOUT_ANALYSIS and (prev_item['x0'] > page_x_start + indent_threshold)
                    prev_text = prev_item.get('text', '')
                    
                    if (prev_short 
                        and not prev_indented 
                        and not _is_bullet_only(prev_text)
                        and not detect_list_item(prev_text)):
                        should_br = True
            
            if should_br:
                para_parts.append("<br>\n" + line_text)
            else:
                para_parts.append(" " + line_text)
        
        prev_item = item
    
    # ================================================
    # SAYFA SONU TEMİZLİĞİ
    # ================================================
    if pending_bullet is not None and current_list_type is not None:
        open_list(current_list_type)
        li = soup.new_tag("li", attrs={"data-sid": str(chunk_id)})
        append_html_to_tag(li, pending_bullet)
        if list_tag is not None:
            list_tag.append(li)
        chunk_id += 1
    elif pending_bullet is not None:
        para_parts.append(pending_bullet)
    pending_bullet = None

    flush_para()
    flush_code()
    close_list()
    
    return str(soup), chunk_id, pending_bullet


# ============================================================
# 8. ANA YÜRÜTÜCÜ (ORCHESTRATOR)
# ============================================================
def pdf_to_clean_html(pdf_path, start_page: int = 0, end_page: int = 999999):
    doc = pymupdf.open(pdf_path)
    html_parts = ["<!DOCTYPE html>\n<html>\n<head>\n<meta charset='utf-8'>\n</head>\n<body>"]
    sentence_counter = 1  

    # ================================================
    # BELGE BAZLI BODY FONT BOYUTU HESAPLAMASI
    # ================================================
    all_pages_blocks = []
    for page_idx, page in enumerate(doc):
        if page_idx < start_page or page_idx > end_page:
            continue
        image_blocks = extract_page_images(page, doc) 
        text_blocks = extract_text_blocks_with_xy_cut(page)
        all_blocks = merge_nearby_blocks(image_blocks + text_blocks)
        all_pages_blocks.append((page_idx, page, all_blocks))
    
    all_blocks_flat = []
    for _, _, blocks in all_pages_blocks:
        all_blocks_flat.extend(blocks)
    doc_body_fs = calculate_body_font_size(all_blocks_flat)
    
    carry_over_bullet = None

    for page_idx, page, all_blocks in all_pages_blocks:
        median_h = calculate_median_line_height(all_blocks)

        page_html, next_id, pending_bullet_out = generate_html_from_blocks(
            sorted_blocks=all_blocks, 
            page_width=page.rect.width,
            median_height=median_h,
            body_font_size=doc_body_fs,
            start_chunk_id=sentence_counter,
            ENABLE_LAYOUT_ANALYSIS=True,
            carry_over_bullet=carry_over_bullet
        )
        
        sentence_counter = next_id 
        carry_over_bullet = pending_bullet_out
        
        html_parts.append(f'<div class="page" id="page_{page_idx+1}">')
        html_parts.append(page_html)
        html_parts.append('</div>\n<hr>')

    html_parts.append("</body></html>")
    return "\n".join(html_parts)

# ============================================================
# 9. ÇALIŞTIRMA (CLI)
# ============================================================
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Kullanım: python pdf_extract.py <pdf_dosya_yolu> [çıktı_dosya_yolu] [start_page] [end_page]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "index.html"
    start_page  = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    end_page    = int(sys.argv[4]) if len(sys.argv) > 4 else 9999999

    html_result = pdf_to_clean_html(pdf_path, start_page, end_page)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_result)
    print(f"Çıktı kaydedildi: {output_path}")
