"""Build fake registry zips in the official Receita layout, for testing only.

Every company below is invented. Usage: python tests/make_sample.py OUT_DIR PORT
"""
import csv
import io
import os
import sys
import zipfile

OUT = sys.argv[1]
PORT = sys.argv[2] if len(sys.argv) > 2 else "8765"
os.makedirs(OUT, exist_ok=True)
LOCAL = f"127.0.0.1:{PORT}"


def write_zip(name, member, rows):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", quotechar='"', quoting=csv.QUOTE_ALL, lineterminator="\n")
    for r in rows:
        w.writerow(r)
    with zipfile.ZipFile(os.path.join(OUT, name), "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(member, buf.getvalue().encode("latin-1"))


def est(basico, fantasia, opened, cnae, cnae2, uf, mun, email, matriz="1", situ="02"):
    row = [basico, "0001", "90", matriz, fantasia, situ, opened, "00", "", "", opened, cnae,
           ",".join(cnae2), "RUA", "EXEMPLO", "10", "", "CENTRO", "01000000", uf, mun,
           "11", "999999999", "", "", "", "", email, "", ""]
    return row


# basico: (estabelecimento kwargs, (razao, natureza, capital, porte), mei)
C = {
    "11111111": (dict(fantasia="MODAFLUX", opened="20260915", cnae="6203100", cnae2=["1412601"],
                      uf="SP", mun="7107", email=f"contato@{LOCAL}/modaflux"),
                 ("MODAFLUX TECNOLOGIA LTDA", "2062", "50000,00", "01"), False),
    "22222222": (dict(fantasia="", opened="20261003", cnae="6203100", cnae2=[], uf="SC",
                      mun="8105", email=""),
                 ("22.222.222 INOVA SIMPLES (I.S.)", "2062", "1000,00", "01"), False),
    "33333333": (dict(fantasia="GEMA DIGITAL", opened="20260820", cnae="3211602", cnae2=[],
                      uf="MG", mun="4123", email=f"oi@{LOCAL}/gemadigital"),
                 ("GEMA DIGITAL JOIAS LTDA", "2062", "20000,00", "01"), False),
    "44444444": (dict(fantasia="", opened="20260610", cnae="6201501", cnae2=[], uf="RJ",
                      mun="6001", email=f"hello@{LOCAL}/spa"),
                 ("BEAUTYTECH SOLUCOES EM SOFTWARE LTDA", "2062", "10000,00", "01"), False),
    "55555555": (dict(fantasia="", opened="20260901", cnae="6203100", cnae2=["1412601"],
                      uf="SP", mun="7107", email="fulano@gmail.com"),
                 ("JOAO MODA APP", "2062", "1000,00", "01"), True),        # MEI -> out
    "66666666": (dict(fantasia="", opened="20260901", cnae="6203100", cnae2=["7410203"],
                      uf="SP", mun="7107", email=""),
                 ("MARIA SILVA DESIGN", "2135", "0,00", "01"), False),      # individual -> out
    "77777777": (dict(fantasia="ANTIGA", opened="20190101", cnae="6203100", cnae2=["1412601"],
                      uf="SP", mun="7107", email=""),
                 ("ANTIGA MODA TECH LTDA", "2062", "1000,00", "01"), False),  # too old -> out
    "88888888": (dict(fantasia="", opened="20260901", cnae="6203100", cnae2=["1412601"],
                      uf="SP", mun="7107", email="", situ="08"),
                 ("FECHADA MODA LTDA", "2062", "1000,00", "01"), False),    # closed -> out
    "99999999": (dict(fantasia="SABOR", opened="20260901", cnae="5611201", cnae2=[],
                      uf="SP", mun="7107", email=""),
                 ("SABOR DIGITAL RESTAURANTE LTDA", "2062", "1000,00", "01"), False),  # out
    "12121212": (dict(fantasia="ARTEFY", opened="20260705", cnae="9002701", cnae2=["6319400"],
                      uf="SP", mun="7107", email=f"time@{LOCAL}/artefy"),
                 ("ARTEFY PLATAFORMA S.A.", "2054", "100000,00", "03"), False),
    "13131313": (dict(fantasia="SOMLAB", opened="20261010", cnae="5920100", cnae2=["6203100"],
                      uf="PE", mun="2531", email=f"contato@{LOCAL}/nada"),
                 ("SOMLAB AUDIO LTDA", "2062", "5000,00", "01"), False),
    "14141414": (dict(fantasia="", opened="20260801", cnae="6203100", cnae2=["1412601"],
                      uf="SP", mun="7107", email="contato@meucontabil.com.br"),
                 ("VESTE CODE LTDA", "2062", "1000,00", "01"), False),
}
# Five new companies sharing an agency domain (should not be read as their website)
for i in range(5):
    b = f"2000000{i}"
    C[b] = (dict(fantasia="", opened="20260901", cnae="4781400", cnae2=["6319400"], uf="SP",
                 mun="7107", email=f"abertura@agenciafoo.com.br"),
            (f"LOJA {i} MODA ONLINE LTDA", "2062", "1000,00", "01"), False)

est_rows = [est(b, **kw) for b, (kw, _, _) in C.items()]
est_rows.append(est("11111111", "MODAFLUX FILIAL", "20260915", "6203100", ["1412601"], "SP",
                    "7107", "", matriz="2"))
half = len(est_rows) // 2
for i in range(10):
    rows = est_rows[:half] if i == 0 else est_rows[half:] if i == 1 else []
    write_zip(f"Estabelecimentos{i}.zip", f"K3241.K03200Y{i}.D61011.ESTABELE", rows)
emp_rows = [[b, razao, nat, "49", cap, porte, ""] for b, (_, (razao, nat, cap, porte), _)
            in C.items()]
for i in range(10):
    write_zip(f"Empresas{i}.zip", f"K3241.K03200Y{i}.D61011.EMPRECSV",
              emp_rows if i == 3 else [])
write_zip("Simples.zip", "F.K03200$W.SIMPLES.CSV.D61011",
          [[b, "S", "20260901", "00000000", "S" if mei else "N", "20260901" if mei else "00000000",
            "00000000"] for b, (_, _, mei) in C.items()])
write_zip("Cnaes.zip", "F.K03200$Z.D61011.CNAECSV", [
    ["6203100", "Desenvolvimento e licenciamento de programas de computador não-customizáveis"],
    ["6201501", "Desenvolvimento de programas de computador sob encomenda"],
    ["6319400", "Portais, provedores de conteúdo e outros serviços de informação na internet"],
    ["1412601", "Confecção de peças de vestuário, exceto roupas íntimas"],
    ["3211602", "Fabricação de artefatos de joalheria e ourivesaria"],
    ["7410203", "Design de produto"],
    ["9002701", "Atividades de artistas plásticos, jornalistas independentes e escritores"],
    ["5920100", "Atividades de gravação de som e de edição de música"],
    ["4781400", "Comércio varejista de artigos do vestuário e acessórios"],
    ["5611201", "Restaurantes e similares"]])
write_zip("Municipios.zip", "F.K03200$Z.D61011.MUNICCSV", [
    ["7107", "SAO PAULO"], ["6001", "RIO DE JANEIRO"], ["4123", "BELO HORIZONTE"],
    ["8105", "FLORIANOPOLIS"], ["2531", "RECIFE"]])
write_zip("Naturezas.zip", "F.K03200$Z.D61011.NATJUCSV", [
    ["2062", "Sociedade Empresária Limitada"], ["2054", "Sociedade Anônima Fechada"],
    ["2135", "Empresário (Individual)"]])
print("sample written to", OUT)
