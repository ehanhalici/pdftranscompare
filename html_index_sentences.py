import re
import warnings
from bs4 import BeautifulSoup, NavigableString, Tag, MarkupResemblesLocatorWarning

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

from lazy_loader import LazyProxy

nltk = LazyProxy("nltk")


SKIP_TAGS = {'pre', 'code', 'img', 'script', 'style', 'svg', 'math', 'head'}

def _mask_html_elements(text):
    placeholders = {}
    counter = 0
    
    # Etiketler (<...>) ve Entity'ler (&...;)
    pattern = re.compile(r'(<[^>]+>)|(&[a-zA-Z0-9#]+;)')
    
    def replacer(match):
        nonlocal counter
        original = match.group(0)
        ph = f"⟦M{counter}⟧"
        placeholders[ph] = original
        counter += 1
        return ph

    masked_text = pattern.sub(replacer, text)
    return masked_text, placeholders

def _unmask_html_elements(text, placeholders):
    for ph, original in placeholders.items():
        text = text.replace(ph, original)
    return text

def index_sentences_in_html(html_content: str) -> str:
    soup = BeautifulSoup(html_content, 'html.parser')
    sentence_counter = 1
    
    for tag in soup.find_all(True):
        if tag.name in SKIP_TAGS:
            continue

        if any(parent.name in SKIP_TAGS for parent in tag.parents):
            continue
            
        if tag.find_parent('index-sid'):
            continue
            
        has_direct_text = any(
            isinstance(c, NavigableString) and c.strip() 
            for c in tag.contents
        )
        if not has_direct_text:
            continue
            
        inner_html = tag.decode_contents()
        if not inner_html.strip():
            continue
            
        masked_html, placeholder_map = _mask_html_elements(inner_html)
        
        sentences = nltk.sent_tokenize(masked_html)
        if not sentences:
            continue
            
        new_contents = []
        for sent in sentences:
            if not sent.strip():
                continue
                
            restored_sent = _unmask_html_elements(sent, placeholder_map)
            
            index_tag = soup.new_tag('index-sid', attrs={'id': str(sentence_counter)})
            index_tag.append(BeautifulSoup(restored_sent, 'html.parser'))
            new_contents.append(index_tag)
            sentence_counter += 1
            
        tag.clear()
        for content in new_contents:
            tag.append(content)

    return str(soup)
