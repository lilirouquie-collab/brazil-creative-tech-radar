import unittest

from pipeline import enrich, rules
from pipeline.build import display_name


class Rules(unittest.TestCase):
    def test_keywords(self):
        n = rules.normalize("BeautyTech Soluções")
        self.assertIn("Beauty", rules.creative_sectors_from_name(n))
        self.assertTrue(rules.has_tech_name(n))
        self.assertEqual(rules.creative_sectors_from_name(rules.normalize("Martelo Ferragens")), [])
        self.assertFalse(rules.has_tech_name(rules.normalize("Padaria Pão Quente")))
        self.assertIn("Fashion", rules.creative_sectors_from_name(rules.normalize("MODATECH LTDA")))

    def test_cnaes(self):
        self.assertEqual(rules.classify_cnaes(["6203100", "1412601"]), (True, ["Fashion"]))
        self.assertEqual(rules.classify_cnaes(["3211603"]), (False, []))  # coin minting
        self.assertFalse(rules.is_relevant_cnae("5611201"))


class Pages(unittest.TestCase):
    def test_parked(self):
        p = enrich.parse_page("<html><title>X</title><body>Site em construção</body></html>",
                              "https://x.com.br/")
        self.assertEqual(p["status"], "soon")

    def test_long_shop_with_em_breve_is_live(self):
        body = "Nova coleção em breve. " + "Vestidos e camisas de linho feitos à mão. " * 30
        p = enrich.parse_page(f"<html><title>Loja</title><body>{body}</body></html>",
                              "https://loja.com.br/")
        self.assertEqual(p["status"], "live")

    def test_instagram_redirect(self):
        p = enrich.parse_page("<html><title>Instagram</title></html>",
                              "https://www.instagram.com/marca.br/")
        self.assertEqual(p["status"], "social")
        self.assertEqual(p["instagram"], "https://www.instagram.com/marca.br/")

    def test_cnpj_check_and_guesses(self):
        self.assertTrue(enrich._cnpj_on_page("11111111000190", "CNPJ 11.111.111/0001-90"))
        self.assertFalse(enrich._cnpj_on_page("11111111000190", "CNPJ 22.111.111/0001-90"))
        rec = {"trade_name": "Luma Studio", "legal_name": "LUMA STUDIO DESIGN LTDA"}
        self.assertEqual(enrich.guess_domains(rec)[:2], ["lumastudio.com.br", "lumastudio.com"])


class Geo(unittest.TestCase):
    def test_locate(self):
        from pipeline import geo
        self.assertEqual(geo.locate("BR", "7107", "SAO PAULO", "SP")[2], "name")
        self.assertEqual(geo.locate("BR", "6001", "", "RJ")[2], "code")
        self.assertEqual(geo.locate("BR", "", "SANTA BARBARA D OESTE", "SP")[2], "name")
        self.assertIsNone(geo.locate("BR", "7107", "SAO PAULO", "RJ"))  # wrong state
        self.assertIsNone(geo.locate("CO", "1", "BOGOTA", "DC"))         # no data yet


class Names(unittest.TestCase):
    def test_display(self):
        self.assertEqual(display_name({"cnpj": "1" * 14, "legal_name": "ARTEFY PLATAFORMA S.A.",
                                       "trade_name": ""}), "Artefy Plataforma")
        self.assertEqual(display_name({"cnpj": "22222222000190", "inova": True, "trade_name": "",
                                       "legal_name": "22.222.222 INOVA SIMPLES (I.S.)"}),
                         "Inova Simples startup 22.222.222")


if __name__ == "__main__":
    unittest.main()
