"""Text normalizer for TTS — converts numbers/dates/currency to spoken form."""
import re

def normalize_for_tts(text: str) -> str:
    text = re.sub(r'\$(\d+(?:\.\d+)?)\s*(trillion|billion|million|thousand)',
        lambda m: f"{_num_to_words(float(m.group(1)))} {m.group(2)} dollars", text, flags=re.IGNORECASE)
    text = re.sub(r'\$([\d,]+(?:\.\d+)?)',
        lambda m: f"{_num_to_words(float(m.group(1).replace(',', '')))} dollars", text)
    text = re.sub(r'(\d+(?:\.\d+)?)\s*%',
        lambda m: f"{_num_to_words(float(m.group(1)))} percent", text)
    text = re.sub(r'\b(19|20)(\d{2})\b',
        lambda m: _year_to_words(int(m.group(0))), text)
    text = re.sub(r'\b(\d+)(st|nd|rd|th)\b',
        lambda m: _ordinal_to_words(int(m.group(1))), text)
    text = re.sub(r'\b(\d{1,3}(?:,\d{3})+)\b',
        lambda m: _num_to_words(float(m.group(0).replace(',', ''))), text)
    text = re.sub(r'\b(\d+(?:\.\d+)?)\b',
        lambda m: _num_to_words(float(m.group(0))), text)
    return re.sub(r' {2,}', ' ', text).strip()

def _year_to_words(year: int) -> str:
    if 2000 <= year <= 2009:
        return f"two thousand{' ' + _tens(year % 100) if year % 100 else ''}"
    elif 2010 <= year <= 2099:
        tens = year % 100
        return f"twenty {_tens(tens)}" if tens else "twenty hundred"
    elif 1900 <= year <= 1999:
        tens = year % 100
        return f"nineteen {_tens(tens)}" if tens else "nineteen hundred"
    return str(year)

def _tens(n: int) -> str:
    ones = ["","one","two","three","four","five","six","seven","eight","nine","ten",
            "eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen","eighteen","nineteen"]
    tens = ["","","twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety"]
    if n < 20: return ones[n]
    elif n % 10 == 0: return tens[n // 10]
    else: return f"{tens[n // 10]}-{ones[n % 10]}"

def _ordinal_to_words(n: int) -> str:
    ordinals = {1:"first",2:"second",3:"third",4:"fourth",5:"fifth",6:"sixth",7:"seventh",
                8:"eighth",9:"ninth",10:"tenth",11:"eleventh",12:"twelfth",13:"thirteenth",
                14:"fourteenth",15:"fifteenth",16:"sixteenth",17:"seventeenth",18:"eighteenth",
                19:"nineteenth",20:"twentieth",21:"twenty-first",22:"twenty-second",
                23:"twenty-third",24:"twenty-fourth",25:"twenty-fifth",26:"twenty-sixth",
                27:"twenty-seventh",28:"twenty-eighth",29:"twenty-ninth",30:"thirtieth",31:"thirty-first"}
    return ordinals.get(n, f"{_num_to_words(float(n))}th")

def _num_to_words(n: float) -> str:
    ones = ["","one","two","three","four","five","six","seven","eight","nine","ten",
            "eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen","eighteen","nineteen"]
    tens_w = ["","","twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety"]
    if n != int(n):
        int_p = int(n)
        dec_s = f"{n:.2f}".split('.')[1].rstrip('0')
        return f"{_num_to_words(float(int_p))} point {_num_to_words(float(int(dec_s)))}"
    n = int(n)
    if n < 0: return f"negative {_num_to_words(float(-n))}"
    if n == 0: return "zero"
    if n < 20: return ones[n]
    if n < 100:
        return tens_w[n//10] if n%10==0 else f"{tens_w[n//10]}-{ones[n%10]}"
    if n < 1000:
        rest = n % 100
        return f"{ones[n//100]} hundred{' '+_num_to_words(float(rest)) if rest else ''}"
    if n < 1_000_000:
        k,rest = n//1000, n%1000
        return f"{_num_to_words(float(k))} thousand{' '+_num_to_words(float(rest)) if rest else ''}"
    if n < 1_000_000_000:
        m,rest = n//1_000_000, n%1_000_000
        return f"{_num_to_words(float(m))} million{' '+_num_to_words(float(rest)) if rest else ''}"
    b,rest = n//1_000_000_000, n%1_000_000_000
    return f"{_num_to_words(float(b))} billion{' '+_num_to_words(float(rest)) if rest else ''}"
