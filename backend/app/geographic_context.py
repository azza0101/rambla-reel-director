"""Conservative place anchors from spoken text, never from generated search guesses."""
import re

# English search names with common Italian/English names and demonyms.
PLACES = {
 'Egypt': ('Egitto','Egypt','egizi','egizia','egizio','egiziano','egiziana','Egyptian'),
 'Thailand': ('Thailandia','Thailand','thailandese','Thai'),
 'Italy': ('Italia','Italy','italiano','italiana','Italian'),
 'France': ('Francia','France','francese','French'),
 'Spain': ('Spagna','Spain','spagnolo','spagnola','Spanish'),
 'Germany': ('Germania','Germany','tedesco','tedesca','German'),
 'Greece': ('Grecia','Greece','greco','greca','Greek'),
 'Turkey': ('Turchia','Turkey','Turkiye','turco','Turkish'),
 'Morocco': ('Marocco','Morocco','marocchino','Moroccan'),
 'Tunisia': ('Tunisia','tunisino','Tunisian'),
 'Japan': ('Giappone','Japan','giapponese','Japanese'),
 'China': ('Cina','China','cinese','Chinese'),
 'India': ('India','indiano','indiana','Indian'),
 'Vietnam': ('Vietnam','vietnamita','Vietnamese'),
 'Indonesia': ('Indonesia','indonesiano','Indonesian'),
 'Cambodia': ('Cambogia','Cambodia','cambogiano','Cambodian'),
 'Nepal': ('Nepal','nepalese','Nepali'),
 'Portugal': ('Portogallo','Portugal','portoghese','Portuguese'),
 'Brazil': ('Brasile','Brazil','brasiliano','Brazilian'),
 'Mexico': ('Messico','Mexico','messicano','Mexican'),
 'United States': ('Stati Uniti','United States','USA','americano','americana','American'),
 'United Kingdom': ('Regno Unito','Inghilterra','United Kingdom','England','British'),
 'Australia': ('Australia','australiano','Australian'),
 'Kenya': ('Kenya','keniota','Kenyan'),
 'Tanzania': ('Tanzania','tanzaniano','Tanzanian'),
 'South Africa': ('Sudafrica','South Africa'),
 'Iceland': ('Islanda','Iceland','islandese','Icelandic'),
 'Norway': ('Norvegia','Norway','norvegese','Norwegian'),
 'Jordan': ('Giordania','Jordan','giordano','Jordanian'),
 'Peru': ('Peru','Perù','peruviano','Peruvian'),
 'Cairo': ('Cairo','Il Cairo'), 'Luxor': ('Luxor',), 'Giza': ('Giza','Giza pyramids'),
 'Minya': ('Minya','El Minya','Al Minya','al-Minya','Elminia','Elmini','Delminia','Minia'),
 'Amarna': ('Amarna','Tell el Amarna'), 'Nile': ('Nilo','Nile'),
 'Bangkok': ('Bangkok',), 'Phuket': ('Phuket',), 'Chiang Mai': ('Chiang Mai',),
 'Rome': ('Roma','Rome'), 'Milan': ('Milano','Milan'), 'Venice': ('Venezia','Venice'),
 'Paris': ('Parigi','Paris'), 'London': ('Londra','London'), 'New York': ('New York',),
 'Tokyo': ('Tokyo',), 'Bali': ('Bali',), 'Marrakech': ('Marrakech','Marrakesh'),
 'Istanbul': ('Istanbul',), 'Athens': ('Atene','Athens'), 'Lisbon': ('Lisbona','Lisbon'),
}
COUNTRY = {'Amarna':'Egypt','Nile':'Egypt','Cairo':'Egypt','Luxor':'Egypt','Giza':'Egypt','Minya':'Egypt','Bangkok':'Thailand','Phuket':'Thailand','Chiang Mai':'Thailand','Rome':'Italy','Milan':'Italy','Venice':'Italy','Paris':'France','London':'United Kingdom','New York':'United States','Tokyo':'Japan','Bali':'Indonesia','Marrakech':'Morocco','Istanbul':'Turkey','Athens':'Greece','Lisbon':'Portugal'}

def places_in(text):
    hits=[]
    for place,aliases in PLACES.items():
        matches=[m.start() for a in aliases for m in re.finditer(r'(?<!\w)'+re.escape(a)+r'(?!\w)',str(text),re.I)]
        if matches:hits.append((min(matches),place))
    return [p for _,p in sorted(hits)]

def country_of(place):
    return COUNTRY.get(place,place)

def beat_places(text, topic, preceding=''):
    explicit=places_in(text)
    if explicit:return explicit
    prior=[(m.start(),place) for place,aliases in PLACES.items() for alias in aliases for m in re.finditer(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',preceding,re.I)]
    if prior:return [max(prior)[1]]
    global_places=places_in(topic)
    countries={country_of(p) for p in global_places}
    return global_places[:1] if len(countries)==1 else []

def anchor_queries(queries, places):
    if not places:return list(dict.fromkeys(queries))
    # A local city outranks its country; unrelated countries are never silently substituted.
    anchor=' '.join(dict.fromkeys(places))
    output=[]
    for query in queries:
        clean=query
        for place in places_in(query):
            if country_of(place) not in {country_of(p) for p in places}:
                for alias in sorted(PLACES[place],key=len,reverse=True):
                    clean=re.sub(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',' ',clean,flags=re.I)
        clean=' '.join(clean.split())
        if not clean:continue
        missing=[p for p in places if p not in places_in(clean)]
        output.append(' '.join([clean,*missing]))
    return list(dict.fromkeys(output))

def conflicting_place(text, expected):
    allowed={country_of(p) for p in expected}
    return bool(allowed and any(country_of(p) not in allowed for p in places_in(text)))


def missing_subject(target, metadata):
    """Do not let a country or tourist match substitute the requested main subject."""
    subjects = [
        (r'\b(police|polizia|poliziott\w*|cops?)\b', r'\b(police|polizia|poliziott\w*|cops?|officers?|law enforcement)\b'),
        (r'\b(military|soldiers?|militari|soldati)\b', r'\b(military|soldiers?|militari|soldati|army|troops?)\b'),
        (r'\b(sarcophag\w*|sarcofag\w*|coffins?)\b', r'\b(sarcophag\w*|sarcofag\w*|coffins?|mumm\w*)\b'),
        (r'\b(pyramids?|piramid\w*)\b', r'\b(pyramids?|piramid\w*)\b'),
    ]
    return any(re.search(asked, target, re.I) and not re.search(found, metadata, re.I)
               for asked, found in subjects)
