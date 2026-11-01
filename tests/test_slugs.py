"""A slug is the stored id of a concept. These are the slugs that abhyasa 0.0.16 made, byte for byte. A new slug for an old name would
leave the rows of that concept in the vault with no concept."""
import pytest
from abhyasa.learner import slugify

SLUGS = [
    ('संधि', 'samdhi'),
    ('saṃdhi', 'samdhi'),
    ('Pāṇini’s Aṣṭādhyāyī', 'paninis-astadhyayi'),
    ('अष्टाध्यायी', 'astadhyayi'),
    ('కర్మ', 'karma'),
    ('ধর্ম', 'dharma'),
    ('ਗੁਰੂ', 'gur'),
    ('கர்மா', 'karma'),
    ('ಯೋಗ', 'yoga'),
    ('ജ്ഞാനം', 'jnanam'),
    ('ગીતા', 'gita'),
    ('Bhagavad Gītā 2.47', 'bhagavad-gita-2-47'),
    ('Ṛgveda 10.129 (Nāsadīya Sūkta)', 'rgveda-10-129-nasadiya-sukta'),
    ('Vyāpti and pramāṇa', 'vyapti-and-pramana'),
    ('Maghā', 'magha'),
    ('Śiva Sūtras', 'siva-sutras'),
    ('Kṛṣṇa', 'krsna'),
    ('C++', 'c-plus-plus'),
    ('C#', 'c-sharp'),
    ('F#', 'f-sharp'),
    ('R&D', 'r-and-d'),
    ('AT&T', 'at-and-t'),
    ('x + y', 'x-plus-y'),
    ('A/B testing', 'a-b-testing'),
    ('k-NN', 'k-nn'),
    ('Self-attention (QKᵀ/√d)', 'self-attention-qkt-d'),
    ('e^{iπ}+1=0', 'e-i-plus-1-0'),
    ('β-VAE', 'vae'),
    ('λ-calculus', 'calculus'),
    ('½ + ¼', '12-plus-14'),
    ('naïve Bayes', 'naive-bayes'),
    ('Straße', 'strae'),
    ('Æsir', 'sir'),
    ('Øresund', 'resund'),
    ('İstanbul', 'istanbul'),
    ('学习', 'c-aa89dd63'),
    ('딥러닝', 'c-f9ffca21'),
    ('Привет мир', 'c-6b49ee5b'),
    ('😀 emoji', 'emoji'),
    ('—', 'c-1b93795b'),
    ('Reciprocal rank fusion', 'reciprocal-rank-fusion'),
    ('Attention Is All You Need: Transformers', 'attention-is-all-you-need-transformers'),
    ('mixed संधि and saṃdhi C++ 学习', 'mixed-samdhi-and-samdhi-c-plus-plus'),
    ('The quick brown fox The quick brown fox The quick brown fox The quick brown fox The quick brown fox The quick brown fox ', 'the-quick-brown-fox-the-quick-brown-fox-the-quick-brown-fox-the-quick-brown-fox-the-quick-brown-fox-the-quick-brown-fox'),
]

@pytest.mark.parametrize("name,slug", SLUGS)
def test_a_slug_stays_the_same(name, slug):
    "Each name gives the slug that abhyasa made before: Indic scripts in IAST, `+ # &` as words, and a hash for a name with no Latin letter."
    assert slugify(name) == slug
