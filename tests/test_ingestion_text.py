from el_descentralizador.domain.ingestion.html import clean_html
from el_descentralizador.domain.ingestion.pipeline import are_similar, normalize_title


def test_normalize_title_strips_stopwords() -> None:
    assert "santiago" not in normalize_title("El incendio de la escuela")
    assert "incendio" in normalize_title("El incendio de la escuela")


def test_similar_titles() -> None:
    left = normalize_title("Alcalde anuncia nuevo hospital en Valdivia")
    right = normalize_title("Alcalde anuncia un nuevo hospital en Valdivia")
    assert are_similar(left, right)


def test_clean_html_strips_scripts() -> None:
    text, image = clean_html('<p>Hola</p><script>alert(1)</script><img src="https://x.test/a.jpg">')
    assert "Hola" in text
    assert "alert" not in text
    assert image == "https://x.test/a.jpg"
