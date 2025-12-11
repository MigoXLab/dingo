import json
import os
import re
import string
import sys
import unicodedata
from collections import Counter
from typing import Callable, List, Set, Tuple

import numpy
import zhon.hanzi
from zhon.hanzi import punctuation

sys.path.append(os.path.dirname(__file__))

TRANSLATION_TABLE_PUNCTUATION_EN = str.maketrans("", "", string.punctuation)
TRANSLATION_TABLE_PUNCTUATION_ZH = str.maketrans("", "", zhon.hanzi.punctuation)

ID_CARD_PATTERN = (
    r"(?<=[^0-9a-zA-Z])"
    r"((1[1-5]|2[1-3]|3[1-7]|4[1-6]|5[0-4]|6[1-5]|71|81|82|91)"
    r"(0[0-9]|1[0-9]|2[0-9]|3[0-4]|4[0-3]|5[1-3]|90)"
    r"(0[0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-3]|5[1-7]|6[1-4]|7[1-4]|8[1-7])"
    r"(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])"
    r"\d{3}[0-9xX])"
    r"(?=[^0-9a-zA-Z])"
)
ID_CARD_CHECK_PATTERN = (
    r"^(1[1-5]|2[1-3]|3[1-7]|4[1-6]|5[0-4]|6[1-5]|71|81|82|91)"
    r"(0[0-9]|1[0-9]|2[0-9]|3[0-4]|4[0-3]|5[1-3]|90)"
    r"(0[0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-3]|5[1-7]|6[1-4]|7[1-4]|8[1-7])"
    r"(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])\d{3}[0-9xX]$"
)


class Extractor(object):
    def __init__(self):
        self.id_card_pattern = None

    @staticmethod
    def _extract_base(pattern, text, with_offset=False):
        if with_offset:
            results = [
                {
                    "text": item.group(1),
                    "offset": (item.span()[0] - 1, item.span()[1] - 1),
                }
                for item in pattern.finditer(text)
            ]
        else:
            results = [item.group(1) for item in pattern.finditer(text)]

        return results

    def extract_id_card(self, text, detail=False):
        if self.id_card_pattern is None:
            self.id_card_pattern = re.compile(ID_CARD_PATTERN)

        text = "".join(["#", text, "#"])
        return self._extract_base(self.id_card_pattern, text, with_offset=detail)


class TextSlice:
    """A slice of text from a document."""

    def __init__(self, text: str, start: int, end: int):
        self.text = text
        self.start = start
        self.end = end


def get_unsafe_words(file_path_list: List[str]) -> List:
    unsafe_words_list = []
    for file_path in file_path_list:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                j = json.loads(line)
                word = str(j["word"])
                unsafe_words_list.append(word)
    return unsafe_words_list


def split_paragraphs(
    text: str, normalizer: Callable[[str], str], remove_empty: bool = True
) -> Tuple[TextSlice]:
    """
    Split a string into paragraphs. A paragraph is defined as a sequence of zero or more characters, followed
    by a newline character, or a sequence of one or more characters, followed by the end of the string.
    """
    text_slices = tuple(
        TextSlice(
            normalizer(text[match.start() : match.end()]), match.start(), match.end()
        )
        for match in re.finditer(r"([^\n]*\n|[^\n]+$)", text)
    )

    if remove_empty is True:
        text_slices = tuple(
            text_slice for text_slice in text_slices if text_slice.text.strip()
        )

    return text_slices


def form_ngrams(sequence, n):
    history = []
    # build the first ngram, yielding only when we have a full ngram
    while n > 1:
        try:
            next_item = next(sequence)
        except StopIteration:
            # no more data, terminate the generator
            return
        history.append(next_item)
        n -= 1

    # yield each ngram we have, then add the next item and repeat
    for item in sequence:
        history.append(item)
        yield tuple(history)
        del history[0]


def normalize(
    text: str,
    remove_punct: bool = True,
    lowercase: bool = True,
    nfd_unicode: bool = True,
    white_space: bool = True,
) -> str:
    """Normalize the text by lowercasing and removing punctuation."""
    # remove punctuation
    if remove_punct:
        text = text.translate(TRANSLATION_TABLE_PUNCTUATION_EN)
        text = text.translate(TRANSLATION_TABLE_PUNCTUATION_ZH)

    # lowercase
    if lowercase:
        text = text.lower()

    if white_space:
        text = text.strip()
        text = re.sub(r"\s+", " ", text)

    # NFD unicode normalization
    if nfd_unicode:
        text = unicodedata.normalize("NFD", text)

    return text


def split_words(content: str):
    res = []
    for i in content.split():
        en_word = ""
        for j in i:
            if re.match(r"[\u4e00-\u9fff]", j):
                if en_word != "":
                    res.append(en_word)
                    en_word = ""
                res.append(j)
            else:
                en_word = en_word + j
        if en_word == i:
            res.append(i)
    return tuple(res)


def base_rps_frac_chars_in_dupe_ngrams(NGRAM_SIZE, content):
    """Base class for calculating the fraction of characters in duplicate word
    N-grams.

    This operates on the lower-cased, punctuation removed content. The function
    also ensures that characters in overlapping ngrams are only counted once.
    """
    normalized_content = normalize(content)
    normalized_words = split_words(normalized_content)
    if len(normalized_words) < NGRAM_SIZE:
        return 0

    # fetch the ngrams from the document if they exist, otherwise
    # compute them
    doc_n_grams = tuple(form_ngrams(iter(normalized_words), NGRAM_SIZE))

    # keep only ngrams which occur at least twice
    ngram_dupes = {ngram for ngram, count in Counter(doc_n_grams).items() if count > 1}
    duplicated_grams = numpy.zeros(len(normalized_words), dtype=int)

    i = 0
    for ngram in doc_n_grams:
        if ngram in ngram_dupes:
            duplicated_grams[i : i + NGRAM_SIZE] = 1

        i += 1

    word_lengths = numpy.array(list(map(len, normalized_words)))
    chars_duped = numpy.sum(word_lengths * duplicated_grams)
    total_chars = numpy.sum(word_lengths)

    if total_chars == 0:
        return 0
    score = float(chars_duped / total_chars) * 100
    return score


def get_real_text(text):
    punc = ",;.!?:'\"/\\|_@#$%^&*~`+-=<>()[]{}·，；。！？：‘’“”、《》【】「」『』〔〕〈〉《》「」『』【】〖〗〘〙〚〛-—…～·‖ _│─┐┼┤"
    pattern = "[" + re.escape(punc) + "]"
    # punctuation_regex = r"[^\w\s]"
    text = re.sub(pattern, "", text)

    chinese_pattern = re.compile(r"[^\u4e00-\u9fa5]")
    # Replace unChinese characters with empty strings
    text = chinese_pattern.sub("", text)
    return text


def delete_punc_en(str_en):
    """
    Remove English punctuation marks
    """
    punctuation_string = string.punctuation
    for i in punctuation_string:
        str_en = str_en.replace(i, "")
    return str_en


def delete_punc_ch(str_ch):
    """
    Remove Chinese punctuation marks
    """
    punctuation_str = punctuation
    for i in punctuation_str:
        str_ch = str_ch.replace(i, "")
    return str_ch


def get_tokens(content, lan):
    """
    Obtain the number of tokens in text to filter short text
    """
    if lan in ["en", "zh"]:
        num_bytes = len(content.encode("utf-8"))
        tokens_len = int(num_bytes * 0.248)
        return tokens_len
    else:
        raise TypeError("language is not supported: " + lan)


def is_sha256(s):
    if re.fullmatch(r"[A-Fa-f0-9]{64}", s):
        return True
    else:
        return False


def get_stop_words(lang) -> Set[str]:
    return stop_words[lang]


stop_words = {
    "en": {
        "a",
        "a's",
        "able",
        "about",
        "above",
        "according",
        "accordingly",
        "across",
        "actually",
        "after",
        "afterwards",
        "again",
        "against",
        "ain't",
        "all",
        "allow",
        "allows",
        "almost",
        "alone",
        "along",
        "already",
        "also",
        "although",
        "always",
        "am",
        "among",
        "amongst",
        "an",
        "and",
        "another",
        "any",
        "anybody",
        "anyhow",
        "anyone",
        "anything",
        "anyway",
        "anyways",
        "anywhere",
        "apart",
        "appear",
        "appreciate",
        "appropriate",
        "are",
        "aren't",
        "around",
        "as",
        "aside",
        "ask",
        "asking",
        "associated",
        "at",
        "available",
        "away",
        "awfully",
        "b",
        "be",
        "became",
        "because",
        "become",
        "becomes",
        "becoming",
        "been",
        "before",
        "beforehand",
        "behind",
        "being",
        "believe",
        "below",
        "beside",
        "besides",
        "best",
        "better",
        "between",
        "beyond",
        "both",
        "brief",
        "but",
        "by",
        "c",
        "c'mon",
        "c's",
        "came",
        "can",
        "can't",
        "cannot",
        "cant",
        "cause",
        "causes",
        "certain",
        "certainly",
        "changes",
        "clearly",
        "co",
        "com",
        "come",
        "comes",
        "concerning",
        "consequently",
        "consider",
        "considering",
        "contain",
        "containing",
        "contains",
        "corresponding",
        "could",
        "couldn't",
        "course",
        "currently",
        "d",
        "definitely",
        "described",
        "despite",
        "did",
        "didn't",
        "different",
        "do",
        "does",
        "doesn't",
        "doing",
        "don't",
        "done",
        "down",
        "downwards",
        "during",
        "e",
        "each",
        "edu",
        "eg",
        "eight",
        "either",
        "else",
        "elsewhere",
        "enough",
        "entirely",
        "especially",
        "et",
        "etc",
        "even",
        "ever",
        "every",
        "everybody",
        "everyone",
        "everything",
        "everywhere",
        "ex",
        "exactly",
        "example",
        "except",
        "f",
        "far",
        "few",
        "fifth",
        "first",
        "five",
        "followed",
        "following",
        "follows",
        "for",
        "former",
        "formerly",
        "forth",
        "four",
        "from",
        "further",
        "furthermore",
        "g",
        "get",
        "gets",
        "getting",
        "given",
        "gives",
        "go",
        "goes",
        "going",
        "gone",
        "got",
        "gotten",
        "greetings",
        "h",
        "had",
        "hadn't",
        "happens",
        "hardly",
        "has",
        "hasn't",
        "have",
        "haven't",
        "having",
        "he",
        "he's",
        "hello",
        "help",
        "hence",
        "her",
        "here",
        "here's",
        "hereafter",
        "hereby",
        "herein",
        "hereupon",
        "hers",
        "herself",
        "hi",
        "him",
        "himself",
        "his",
        "hither",
        "hopefully",
        "how",
        "howbeit",
        "however",
        "i",
        "i'd",
        "i'll",
        "i'm",
        "i've",
        "ie",
        "if",
        "ignored",
        "immediate",
        "in",
        "inasmuch",
        "inc",
        "indeed",
        "indicate",
        "indicated",
        "indicates",
        "inner",
        "insofar",
        "instead",
        "into",
        "inward",
        "is",
        "isn't",
        "it",
        "it'd",
        "it'll",
        "it's",
        "its",
        "itself",
        "j",
        "just",
        "k",
        "keep",
        "keeps",
        "kept",
        "know",
        "known",
        "knows",
        "l",
        "last",
        "lately",
        "later",
        "latter",
        "latterly",
        "least",
        "less",
        "lest",
        "let",
        "let's",
        "like",
        "liked",
        "likely",
        "little",
        "look",
        "looking",
        "looks",
        "ltd",
        "m",
        "mainly",
        "many",
        "may",
        "maybe",
        "me",
        "mean",
        "meanwhile",
        "merely",
        "might",
        "more",
        "moreover",
        "most",
        "mostly",
        "much",
        "must",
        "my",
        "myself",
        "n",
        "name",
        "namely",
        "nd",
        "near",
        "nearly",
        "necessary",
        "need",
        "needs",
        "neither",
        "never",
        "nevertheless",
        "new",
        "next",
        "nine",
        "no",
        "nobody",
        "non",
        "none",
        "noone",
        "nor",
        "normally",
        "not",
        "nothing",
        "novel",
        "now",
        "nowhere",
        "o",
        "obviously",
        "of",
        "off",
        "often",
        "oh",
        "ok",
        "okay",
        "old",
        "on",
        "once",
        "one",
        "ones",
        "only",
        "onto",
        "or",
        "other",
        "others",
        "otherwise",
        "ought",
        "our",
        "ours",
        "ourselves",
        "out",
        "outside",
        "over",
        "overall",
        "own",
        "p",
        "particular",
        "particularly",
        "per",
        "perhaps",
        "placed",
        "please",
        "plus",
        "possible",
        "presumably",
        "probably",
        "provides",
        "q",
        "que",
        "quite",
        "qv",
        "r",
        "rather",
        "rd",
        "re",
        "really",
        "reasonably",
        "regarding",
        "regardless",
        "regards",
        "relatively",
        "respectively",
        "right",
        "s",
        "said",
        "same",
        "saw",
        "say",
        "saying",
        "says",
        "second",
        "secondly",
        "see",
        "seeing",
        "seem",
        "seemed",
        "seeming",
        "seems",
        "seen",
        "self",
        "selves",
        "sensible",
        "sent",
        "serious",
        "seriously",
        "seven",
        "several",
        "shall",
        "she",
        "should",
        "shouldn't",
        "since",
        "six",
        "so",
        "some",
        "somebody",
        "somehow",
        "someone",
        "something",
        "sometime",
        "sometimes",
        "somewhat",
        "somewhere",
        "soon",
        "sorry",
        "specified",
        "specify",
        "specifying",
        "still",
        "sub",
        "such",
        "sup",
        "sure",
        "t",
        "t's",
        "take",
        "taken",
        "tell",
        "tends",
        "th",
        "than",
        "thank",
        "thanks",
        "thanx",
        "that",
        "that's",
        "thats",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "thence",
        "there",
        "there's",
        "thereafter",
        "thereby",
        "therefore",
        "therein",
        "theres",
        "thereupon",
        "these",
        "they",
        "they'd",
        "they'll",
        "they're",
        "they've",
        "think",
        "third",
        "this",
        "thorough",
        "thoroughly",
        "those",
        "though",
        "three",
        "through",
        "throughout",
        "thru",
        "thus",
        "to",
        "together",
        "too",
        "took",
        "toward",
        "towards",
        "tried",
        "tries",
        "truly",
        "try",
        "trying",
        "twice",
        "two",
        "u",
        "un",
        "under",
        "unfortunately",
        "unless",
        "unlikely",
        "until",
        "unto",
        "up",
        "upon",
        "us",
        "use",
        "used",
        "useful",
        "uses",
        "using",
        "usually",
        "uucp",
        "v",
        "value",
        "various",
        "very",
        "via",
        "viz",
        "vs",
        "w",
        "want",
        "wants",
        "was",
        "wasn't",
        "way",
        "we",
        "we'd",
        "we'll",
        "we're",
        "we've",
        "welcome",
        "well",
        "went",
        "were",
        "weren't",
        "what",
        "what's",
        "whatever",
        "when",
        "whence",
        "whenever",
        "where",
        "where's",
        "whereafter",
        "whereas",
        "whereby",
        "wherein",
        "whereupon",
        "wherever",
        "whether",
        "which",
        "while",
        "whither",
        "who",
        "who's",
        "whoever",
        "whole",
        "whom",
        "whose",
        "why",
        "will",
        "willing",
        "wish",
        "with",
        "within",
        "without",
        "won't",
        "wonder",
        "would",
        "wouldn't",
        "x",
        "y",
        "yes",
        "yet",
        "you",
        "you'd",
        "you'll",
        "you're",
        "you've",
        "your",
        "yours",
        "yourself",
        "yourselves",
        "z",
        "zero",
    },
}
