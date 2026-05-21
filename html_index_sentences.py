import os
import re
import warnings
from bs4 import BeautifulSoup, NavigableString, Tag, MarkupResemblesLocatorWarning
import wordsegment

from lazy_loader import LazyProxy
nltk = LazyProxy("nltk")

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
wordsegment.load()

SKIP_TAGS = {'pre', 'code', 'img', 'script', 'style', 'svg', 'math', 'head'}





def fix_broken_words(text: str) -> str:
    placeholders = {}
    counter = 0
    
    masking_pattern = re.compile(r'(<[^>]+>)|(&[a-zA-Z0-9#]+;)|(__\d+__)')
    
    def mask_replacer(match):
        nonlocal counter
        original = match.group(0)
        ph = f"⟦M{counter}⟧"
        placeholders[ph] = original
        counter += 1
        return ph

    masked_text = masking_pattern.sub(mask_replacer, text)
    
    repair_pattern = re.compile(r'(⟦M\d+⟧)|([a-zA-Z]+(?:\s+[a-zA-Z]+)*)')
    
    def text_replacer(matcher):
        mask = matcher.group(1)
        alpha_chunk = matcher.group(2)

        if mask:
            return mask

        if alpha_chunk:
            pure_text = alpha_chunk.replace(" ", "")
            if len(pure_text) <= 2:
                return pure_text 
            words = wordsegment.segment(pure_text)
            corrected = " ".join(words) 

            if alpha_chunk[0].isupper() and corrected:
                corrected = corrected[0].upper() + corrected[1:]
        return corrected

        
        return matcher.group(0)
    repaired_text = repair_pattern.sub(text_replacer, masked_text)

    for ph, original in placeholders.items():
        repaired_text = repaired_text.replace(ph, original)
        
    return repaired_text

def _mask_html_elements(text):
    placeholders = {}
    counter = 0
    
    # Etiketler (<...>) ve Entity'ler (&...;)
    pattern = re.compile(r'(<[^>]+>)|(&[a-zA-Z0-9#]+;)')
    
    def replacer(matcher):
        nonlocal counter
        original = matcher.group(0)
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

        if os.environ.get("FIX_BROKEN_WORDS") == "True":
            masked_html = fix_broken_words(masked_html)
        
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
            index_tag.append(" ")
            new_contents.append(index_tag)
            sentence_counter += 1
            
        tag.clear()
        for content in new_contents:
            tag.append(content)

    return str(soup)
