from punctuation import smart_punctuation


def test_fragetecken():
    assert smart_punctuation("hur mår du frågetecken") == "hur mår du?"

def test_utropstecken():
    assert smart_punctuation("stopp utropstecken") == "stopp!"

def test_kommatecken():
    assert smart_punctuation("hej kommatecken hur mår du") == "hej, hur mår du"

def test_semikolon():
    assert smart_punctuation("först detta semikolon sedan det") == "först detta; sedan det"

def test_tre_punkter():
    assert smart_punctuation("jag vet inte tre punkter") == "jag vet inte..."

def test_ellips():
    assert smart_punctuation("hmm ellips") == "hmm..."

def test_ny_rad():
    assert smart_punctuation("rad ett ny rad rad två") == "rad ett\nrad två"

def test_citattecken():
    assert smart_punctuation("han sa citattecken hej citattecken") == 'han sa "hej"'

def test_case_insensitive():
    assert smart_punctuation("FRÅGETECKEN") == "?"

def test_cleans_spaces_before_punctuation():
    assert smart_punctuation("hej  ?") == "hej?"
