from collections import Counter
import re
from nltk.corpus import names
import csv
from rapidfuzz import process, fuzz
from difflib import SequenceMatcher
import itertools

last_names = set()
first_names = set()
full_sports_names = set()
brands = set()
cities = set()
nicknames = set()
attributes = set()
subsets = set()


def fuzzy_last_name(word, names=last_names, threshold=90):
    result = process.extractOne(word, names, scorer=fuzz.ratio)
    if result is None:
        return None
    match, score, _ = result
    return match if score >= threshold else None

def fuzzy_city(word, city_set=cities, threshold=90):
    result = process.extractOne(word, city_set, scorer=fuzz.ratio)
    if result is None:
        return None
    match, score, _ = result
    return match if score >= threshold else None

def calculate_title_similarity(titles):

    total_score = 0
    count = 0

    for t1, t2 in itertools.combinations(titles, 2):
        ratio = SequenceMatcher(None, t1, t2).ratio()
        total_score += ratio
        count += 1

    return (total_score/count) if count > 0 else 0


def is_year(w):
    if re.fullmatch(r"\d{4}", w):
        return 1900 <= int(w) <= 2035
    if re.fullmatch(r"\d{4}\s\d{2}", w):
        main, tail = map(int, w.split())
        return 1900 <= main <= 2035 and (tail < 10 or tail > 70)
    return False

def extract_year(title, key, token_map):
    title_clean = title.lower()
    reduced = title
    normalized = None
    # First: match compound years like "1996-97", "1996 97", etc.
    compound_match = re.search(r"\b(19\d{2}|20[0-2]\d)[\s\-–](\d{2})\b", title_clean)
    if compound_match:
        main, tail = int(compound_match.group(1)), int(compound_match.group(2))
        if 1900 <= main <= 2035 and (tail < 10 or tail > 70):
            normalized = normalized = f"{main} {compound_match.group(2)}"
            token_map[key] = [normalized]
            reduced = re.sub(re.escape(compound_match.group(0)), "", title, flags=re.IGNORECASE).strip()
            return token_map, reduced
        
    # Second: match standalone 4-digit years
    single_match = re.search(r"\b(19\d{2}|20[0-2]\d)\b", title_clean)
    if single_match:
        year = single_match.group(1)
        reduced = re.sub(rf"\b{year}\b", "", title, flags=re.IGNORECASE).strip()
        token_map[key] = [year]
        return token_map, reduced

    return token_map, title

def extract_card_number(title, key, token_map):
    title_clean = title.lower()

    # Match formats like "#23", "RC-12", "A7", "23"
    pattern = r'\b#?[a-z0-9]{1,4}(?:-[a-z0-9]{1,4})?\b'
    matches = re.findall(pattern, title_clean)

    # Filter to ensure at least one digit is present
    valid = [m for m in matches if any(c.isdigit() for c in m)]

    reduced = title
    if valid:
        card_number = valid[0].lstrip("#")  # Strip leading '#' if present
        reduced = re.sub(rf'\b#?{re.escape(card_number)}\b', "", title, flags=re.IGNORECASE).strip()
        token_map[key] = [card_number]

    return token_map, reduced

def extract_serial(title, key, token_map):
    """
    Extracts a serial number like '/250' from a title string.
    Returns (serial_string, reduced_title).
    """
    match = re.search(r"/\d{1,6}\b", title)
    if match:
        serial = match.group(0)
        reduced = re.sub(re.escape(serial), "", title, flags=re.IGNORECASE).strip()
        token_map[key] = [serial]
        return token_map, reduced
    return token_map, title

def normalize_word(word):
    # Strip leading "#" if it's a card number (e.g. "#23" → "23")
    if word.startswith("#") and any(char.isdigit() for char in word):
        return word[1:]
    return word

def load_teams(path="C:\\Users\\Dan\\Documents\\ebay\\software\\lookup\\inout\\teams.csv"):
    with open(path, newline='', encoding='utf-8') as f:
        reader = list(csv.reader(f))
        name_set = set(row[0].strip().lower() for row in reader if row and len(row) > 1)
        city_set = set(row[1].strip().lower() for row in reader if row and len(row) > 1)
    
        return name_set, city_set


def load_last_names(path="C:\\Users\\Dan\\Documents\\ebay\\software\\lookup\\inout\\surnames.csv"):
    with open(path, newline='', encoding='utf-8') as f:
        return set(row[0].strip().lower() for row in csv.reader(f) if row)

def load_names(path="C:\\Users\\Dan\\Documents\\ebay\\software\\lookup\\inout\\biofile_trimmed.csv"):
    
    nfl_path = "C:\\Users\\Dan\\Documents\\ebay\\software\\lookup\\inout\\nfl.csv"
    nba_path = "C:\\Users\\Dan\\Documents\\ebay\\software\\lookup\\inout\\nba.csv"
    
    last_names = load_last_names()
    first_names = set(name.lower() for name in names.words('male.txt'))

    with open(path, newline='', encoding='utf-8') as f:
        reader = list(csv.reader(f))
        full_sports_names.update((row[3]+ " "+row[1]).strip().lower() for row in reader if row and len(row) > 1)
        full_sports_names.update((row[2]+ " "+row[1]).strip().lower() for row in reader if row and len(row) > 1)
        
        first_names.update(row[3].strip().lower() for row in reader if row and len(row) > 1)
        first_names.update(row[2].strip().lower() for row in reader if row and len(row) > 1)
        last_names.update(row[1].strip().lower() for row in reader if row and len(row) > 1)     
    
    with open(nfl_path, newline='', encoding='utf-8') as f:
        nfl_names = set(row[6].strip().lower() for row in csv.reader(f) if row)
        #print(list(nfl_names)[:10])
        full_sports_names.update(nfl_names)
    
    with open(nba_path, newline='', encoding='utf-8') as f:
        nba_names = set((row[3]+ " "+row[2]).strip().lower() for row in csv.reader(f) if row and len(row) > 1)
        #print(list(nba_names)[:10])
        full_sports_names.update(nba_names)
    
    return first_names, last_names, full_sports_names

'''def load_cities(path="C:\\Users\\Dan\\Documents\\ebay\\software\\lookup\\inout\\world-cities.csv"):
    with open(path, newline='', encoding='utf-8') as f:
        return set(row[0].strip().lower() for row in csv.reader(f) if row)'''
    
def load_brands(path="C:\\Users\\Dan\\Documents\\ebay\\software\\lookup\\inout\\brands.csv"):
    with open(path, newline='', encoding='utf-8') as f:
        reader = list(csv.reader(f))
        brand_set = set((row[1]).strip().lower() for row in reader if row and len(row) > 1)
        subset_set = set((row[0]).strip().lower() for row in reader if row and len(row) > 1)
    
    return brand_set, subset_set

def load_attributes(path="C:\\Users\\Dan\\Documents\\ebay\\software\\lookup\\inout\\attributes.csv"):
    with open(path, newline='', encoding='utf-8') as f:
        return set(row[0].strip().lower() for row in csv.reader(f) if row)

def find_brand_phrases(words, brand_set, max_len=4):
    found = []
    for n in range(max_len, 0, -1):  # Try longer phrases first
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i:i+n])
            if phrase in brand_set:
                found.append((i, n, phrase))
    return found

def extract_phrases_fast(title, key, token_map, phrase_set, max_len=4, single_match=True):
     
    tokens = re.findall(r'[a-z0-9]+', title.lower())
    
    joined_tokens = []
    for n in range(max_len, 0, -1):
        for i in range(len(tokens) - n + 1):
            phrase = " ".join(tokens[i:i+n])
            joined_tokens.append(phrase)

    #print("jt: ", joined_tokens)
    for phrase in joined_tokens:
        #print("phrase: ", phrase)
        if phrase in phrase_set:
            if key in token_map:
                token_map[key].append(phrase)
            else:
                token_map[key] = [phrase]
            # Remove it from the original title (best effort)
            pattern = rf"\b{re.escape(phrase)}\b"
            title = re.sub(pattern, "", title, flags=re.IGNORECASE).strip()
            if single_match:                
                break

    return token_map, title


def tokenize_title(title, min_word_length=3):
    token_map = {}

    # Step 1: Extract known phrases
    token_map, title = extract_year(title, "year", token_map)
    token_map, title = extract_phrases_fast(title, "brand", token_map, brands)
    token_map, title = extract_phrases_fast(title, "full_name", token_map, full_sports_names)

    if "full_name" in token_map:
        #using this awkwewardness since most of these are one element lists
        full = (token_map.get("full_name", [None])[0]).split()
        if len(full) >= 2:
            token_map["first_name"] = [full[0]]
            token_map["last_name"] = [full[1]]

    else:
        token_map, title = extract_phrases_fast(title, "first_name", token_map, first_names)
        token_map, title = extract_phrases_fast(title, "last_name", token_map, last_names)

    token_map, title = extract_card_number(title, "card_number", token_map)
    token_map, title = extract_serial(title, "serial", token_map)    
    token_map, title = extract_phrases_fast(title, "city", token_map, cities)
    token_map, title = extract_phrases_fast(title, "team", token_map, nicknames) 
    
    token_map, title = extract_phrases_fast(title, "attributes", token_map, attributes, single_match=False)
    token_map, title = extract_phrases_fast(title, "subset", token_map, subsets)
    
    # Step 2: Tokenize the rest
    unknown_tokens = re.findall(r'\b#?[a-z0-9]{2,}(?:-[a-z0-9]{2,})?\b', title.lower())
    unknown_tokens = [normalize_word(t) for t in unknown_tokens if len(t) >= min_word_length]
    token_map["unknown"] = unknown_tokens
    print(token_map)
    return token_map

def initialize_data():
    global last_names, first_names, brands, cities, nicknames, full_sports_names, subsets, attributes

    #initialize data files
    first_names, last_names, full_sports_names = load_names()
    nicknames, cities = load_teams()
    brands, subsets = load_brands()    
    attributes = load_attributes()

from collections import Counter, defaultdict

def collapse_to_most_common(token_maps, union_of_multis=False):
    """
    Given a list of token maps (dict[str, list[str]]), return a dictionary:
    key → (most common value, % of titles that had it)
    """
    attribute_counts = defaultdict(Counter)
    total = len(token_maps)

    for token_map in token_maps:
        for key, value_list in token_map.items():
            attribute_counts[key].update(set(value_list))  # use set to avoid duplicate matches per title

    collapsed = {}
    for key, counter in attribute_counts.items():
        if union_of_multis and (key == "unknown" or key == "attributes"):
            collapsed[key] = (", ".join(list(counter)), 100)
        else:
            value, count = counter.most_common(1)[0]
            percent = round((count / total) * 100, 1)
            collapsed[key] = (value, percent)

    return collapsed

def export_classified_words_to_csv(classified_words, output_path):
    """
    Writes classified_words to a CSV file.
    Each row includes: Label, Value, Percentage
    Unknown words are grouped under the 'unknown' label with blank percentages.
    """
    with open(output_path, mode="w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Label", "Value", "Percent"])

        for label, value in classified_words.items():
            if label == "unknown":
                for word in value:
                    writer.writerow([label, word, ""])
            else:
                items = value if isinstance(value, list) else [value]
                for word, pct in items:
                    writer.writerow([label, word, f"{pct}%"])


def analyze_common_tokens(title_tokens, min_word_length=3):
    """
    Analyzes word frequency in item titles and prints the most common words with % coverage.
    - titles: list of strings
    - min_word_length: optional filter to exclude short/stop words
    """
    
    token_counts = Counter()
    total_titles = len(title_tokens)
    for token_map in title_tokens:
        # Flatten the values into a list of tokens
        all_tokens = [token for tokens in token_map.values() for token in tokens]
        unique_tokens = set(all_tokens)
        token_counts.update(unique_tokens)


    
    common_words = sorted(token_counts, key=token_counts.get, reverse=True)

    print("📊 Most Common Words (% of titles in which they appear):\n")

    for word in common_words:
        count = token_counts[word]
        percent = (count / total_titles) * 100
        print(f"{str(word):<15} {percent:5.1f}%  ({count} of {total_titles})")

    return common_words

    