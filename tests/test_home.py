def test_home_muestra_titulo(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Capping de leyes · Proyecto Aurora" in response.get_data(as_text=True)


def test_home_muestra_contadores_e_inconsistencias(client):
    html = client.get("/").get_data(as_text=True)
    for texto in ("12", "174", "3", "M-4175", "M-4176", "DDH-012"):
        assert texto in html
