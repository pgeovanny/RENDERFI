

def buscar_comentarios(id_questao):
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.comentario, c.data_criacao, u.nome
        FROM comentarios c
        JOIN usuarios u ON c.id_usuario = u.id
        WHERE c.id_questao = ?
        ORDER BY c.data_criacao DESC
    """, (id_questao,))
    resultados = cursor.fetchall()
    conn.close()
    return [{"comentario": c[0], "data_criacao": c[1], "nome_usuario": c[2]} for c in resultados]

@app.route("/comentar/<int:id_questao>", methods=["POST"])
def comentar(id_questao):
    if "usuario_id" not in session:
        return redirect("/")
    comentario = request.form.get("comentario")
    if not comentario.strip():
        return redirect(f"/resolver_real?id={id_questao}")
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO comentarios (id_questao, id_usuario, comentario) VALUES (?, ?, ?)",
                   (id_questao, session["usuario_id"], comentario))
    conn.commit()
    conn.close()
    return redirect(f"/resolver_real?id={id_questao}")

@app.route("/resolver_real", methods=["GET", "POST"])
def resolver_real():
    if "usuario_id" not in session:
        return redirect("/")
    id_usuario = session["usuario_id"]
    id_questao = int(request.args.get("id", 1))

    # Obter questão
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questoes WHERE id = ?", (id_questao,))
    dados = cursor.fetchone()
    if not dados:
        return "Questão não encontrada"
    questao = {
        "id": dados[0],
        "lei": dados[1],
        "artigo": dados[2],
        "nivel": dados[3],
        "enunciado": dados[4],
        "alternativas": eval(dados[5]),
        "correta": dados[6],
        "fundamento": dados[7],
    }

    # Processar resposta
    if request.method == "POST":
        resposta = request.form.get("resposta")
        acertou = 1 if resposta == questao["correta"] else 0
        cursor.execute("INSERT INTO respostas (id_usuario, id_questao, acertou) VALUES (?, ?, ?)",
                       (id_usuario, id_questao, acertou))
        conn.commit()
        # Redireciona para próxima (exemplo: id + 1)
        return redirect(f"/resolver_real?id={id_questao + 1}")

    # Buscar comentários
    comentarios = buscar_comentarios(id_questao)

    # Buscar progresso
    cursor.execute("SELECT COUNT(*) FROM respostas WHERE id_usuario = ? AND id_questao IN (SELECT id FROM questoes WHERE lei = ?)", (id_usuario, questao["lei"]))
    resolvidas = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM questoes WHERE lei = ?", (questao["lei"],))
    total = cursor.fetchone()[0]

    # Buscar dados do usuário
    cursor.execute("SELECT nome, area_estudo FROM usuarios WHERE id = ?", (id_usuario,))
    nome, area = cursor.fetchone()

    conn.close()
    return render_template("resolver_real.html", questao=questao, comentarios=comentarios,
                           resolvidas=resolvidas, total=total,
                           usuario={"nome": nome, "area_estudo": area})

@app.route("/favoritar/<int:id_questao>", methods=["POST"])
def favoritar(id_questao):
    if "usuario_id" not in session:
        return redirect("/")
    id_usuario = session["usuario_id"]
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM favoritos WHERE id_usuario = ? AND id_questao = ?", (id_usuario, id_questao))
    existe = cursor.fetchone()
    if existe:
        cursor.execute("DELETE FROM favoritos WHERE id_usuario = ? AND id_questao = ?", (id_usuario, id_questao))
    else:
        cursor.execute("INSERT OR IGNORE INTO favoritos (id_usuario, id_questao) VALUES (?, ?)", (id_usuario, id_questao))
    conn.commit()
    conn.close()
    return redirect(f"/resolver_real?id={id_questao}")

@app.route("/favoritas")
def favoritas():
    if "usuario_id" not in session:
        return redirect("/")
    id_usuario = session["usuario_id"]
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT q.id, q.enunciado, q.lei, q.artigo
        FROM favoritos f
        JOIN questoes q ON f.id_questao = q.id
        WHERE f.id_usuario = ?
        ORDER BY f.data_favorito DESC
    """, (id_usuario,))
    lista = cursor.fetchall()
    conn.close()
    questoes = [{"id": q[0], "enunciado": q[1], "lei": q[2], "artigo": q[3]} for q in lista]
    return render_template("favoritas.html", questoes=questoes)

@app.route("/salvar_filtro", methods=["POST"])
def salvar_filtro():
    if "usuario_id" not in session:
        return redirect("/")
    nome = request.form.get("nome_filtro")
    filtro = {
        "lei": request.form.get("lei"),
        "modalidade": request.form.get("modalidade"),
        "nivel": request.form.get("nivel"),
        "artigo": request.form.get("artigo"),
    }
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO filtros_salvos (id_usuario, nome_filtro, filtros_json) VALUES (?, ?, ?)",
                   (session["usuario_id"], nome, str(filtro)))
    conn.commit()
    conn.close()
    return redirect("/meus_filtros")

@app.route("/meus_filtros")
def meus_filtros():
    if "usuario_id" not in session:
        return redirect("/")
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome_filtro, filtros_json FROM filtros_salvos WHERE id_usuario = ?", (session["usuario_id"],))
    filtros = cursor.fetchall()
    conn.close()
    lista = []
    for f in filtros:
        filtros_dict = eval(f[2])
        query = "&".join([f"{k}={v}" for k, v in filtros_dict.items() if v])
        lista.append({
            "nome": f[1],
            "link": f"/verificar_questoes?{query}"
        })
    return render_template("meus_filtros.html", filtros=lista)

@app.route("/historico")
def historico():
    if "usuario_id" not in session:
        return redirect("/")
    id_usuario = session["usuario_id"]
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT q.lei, q.artigo, q.enunciado, r.acertou, r.data_resposta
        FROM respostas r
        JOIN questoes q ON r.id_questao = q.id
        WHERE r.id_usuario = ?
        ORDER BY r.data_resposta DESC
    """, (id_usuario,))
    historico = cursor.fetchall()
    conn.close()
    lista = []
    for h in historico:
        lista.append({
            "lei": h[0],
            "artigo": h[1],
            "enunciado": h[2],
            "acertou": "✅" if h[3] else "❌",
            "data": h[4]
        })
    return render_template("historico.html", tentativas=lista)

@app.route("/anotacoes", methods=["GET", "POST"])
def anotacoes():
    if "usuario_id" not in session:
        return redirect("/")
    id_usuario = session["usuario_id"]

    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()

    if request.method == "POST":
        titulo = request.form.get("titulo")
        conteudo = request.form.get("conteudo")
        id_questao = request.form.get("id_questao")
        if not id_questao:
            id_questao = None
        cursor.execute("INSERT INTO anotacoes (id_usuario, id_questao, titulo, conteudo) VALUES (?, ?, ?, ?)",
                       (id_usuario, id_questao, titulo, conteudo))
        conn.commit()

    cursor.execute("SELECT id, titulo, conteudo, data_criacao FROM anotacoes WHERE id_usuario = ? ORDER BY data_criacao DESC", (id_usuario,))
    lista = cursor.fetchall()
    conn.close()

    anots = [{"id": a[0], "titulo": a[1], "conteudo": a[2], "data": a[3]} for a in lista]
    return render_template("anotacoes.html", anotacoes=anots)

# Revisão Inteligente - revisão de erradas
from datetime import datetime, timedelta

if request.args.get("revisar_erradas") == "1":
        dias = int(request.args.get("dias", "7"))
        data_limite = datetime.now() - timedelta(days=dias)

        cursor.execute("""
            SELECT DISTINCT q.*
            FROM respostas r
            JOIN questoes q ON q.id = r.id_questao
            WHERE r.id_usuario = ? AND r.acertou = 0 AND r.data_resposta >= ?
        """, (session["usuario_id"], data_limite.strftime("%Y-%m-%d %H:%M:%S")))
        questoes = cursor.fetchall()

        lista = []
        for q in questoes:
            lista.append({
                "id": q[0],
                "lei": q[1],
                "artigo": q[2],
                "enunciado": q[3],
                "modalidade": q[4],
                "nivel": q[5]
            })
        return render_template("verificar_questoes.html", questoes=lista)

@app.route("/etiquetar/<int:id_questao>", methods=["POST"])
def etiquetar(id_questao):
    if "usuario_id" not in session:
        return redirect("/")
    nome = request.form.get("etiqueta")
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO etiquetas (id_usuario, id_questao, nome) VALUES (?, ?, ?)",
                   (session["usuario_id"], id_questao, nome))
    conn.commit()
    conn.close()
    return redirect(f"/resolver_real?id={id_questao}")

@app.route("/minhas_tags")
def minhas_tags():
    if "usuario_id" not in session:
        return redirect("/")
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT nome FROM etiquetas WHERE id_usuario = ?", (session["usuario_id"],))
    nomes = [n[0] for n in cursor.fetchall()]
    tags = []
    for nome in nomes:
        cursor.execute("""
            SELECT q.id, q.lei, q.artigo, q.enunciado
            FROM etiquetas e
            JOIN questoes q ON e.id_questao = q.id
            WHERE e.id_usuario = ? AND e.nome = ?
        """, (session["usuario_id"], nome))
        questoes = cursor.fetchall()
        tags.append({
            "nome": nome,
            "questoes": [{"id": q[0], "lei": q[1], "artigo": q[2], "enunciado": q[3]} for q in questoes]
        })
    conn.close()
    return render_template("minhas_tags.html", tags=tags)

@app.route("/escolher_caderno/<int:id_questao>", methods=["GET", "POST"])
def escolher_caderno(id_questao):
    if "usuario_id" not in session:
        return redirect("/")
    id_usuario = session["usuario_id"]
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()

    if request.method == "POST":
        nome = request.form.get("nome")
        descricao = request.form.get("descricao", "")
        cursor.execute("INSERT INTO cadernos (id_usuario, nome, descricao) VALUES (?, ?, ?)",
                       (id_usuario, nome, descricao))
        conn.commit()

    cursor.execute("SELECT id, nome FROM cadernos WHERE id_usuario = ?", (id_usuario,))
    cadernos = cursor.fetchall()

    conn.close()
    return render_template("escolher_caderno.html", cadernos=cadernos, id_questao=id_questao)

@app.route("/adicionar_a_caderno/<int:id_caderno>/<int:id_questao>", methods=["POST"])
def adicionar_a_caderno(id_caderno, id_questao):
    if "usuario_id" not in session:
        return redirect("/")
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO caderno_questao (id_caderno, id_questao) VALUES (?, ?)", (id_caderno, id_questao))
    conn.commit()
    conn.close()
    return redirect("/resolver_real?id=" + str(id_questao))

@app.route("/meus_cadernos")
def meus_cadernos():
    if "usuario_id" not in session:
        return redirect("/")
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id, nome, descricao FROM cadernos WHERE id_usuario = ?", (session["usuario_id"],))
    cadernos = cursor.fetchall()
    resultado = []
    for c in cadernos:
        cursor.execute("""
            SELECT q.id, q.lei, q.artigo, q.enunciado
            FROM caderno_questao cq
            JOIN questoes q ON q.id = cq.id_questao
            WHERE cq.id_caderno = ?
        """, (c[0],))
        questoes = cursor.fetchall()
        resultado.append({
            "id": c[0],
            "nome": c[1],
            "descricao": c[2],
            "questoes": [{"id": q[0], "lei": q[1], "artigo": q[2], "enunciado": q[3]} for q in questoes]
        })
    conn.close()
    return render_template("meus_cadernos.html", cadernos=resultado)

@app.route("/lembretes", methods=["GET", "POST"])
def lembretes():
    if "usuario_id" not in session:
        return redirect("/")
    id_usuario = session["usuario_id"]
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()

    if request.method == "POST":
        titulo = request.form.get("titulo")
        destino = request.form.get("destino")
        data_agendada = request.form.get("data_agendada")
        cursor.execute("INSERT INTO lembretes (id_usuario, titulo, destino, data_agendada) VALUES (?, ?, ?, ?)",
                       (id_usuario, titulo, destino, data_agendada))
        conn.commit()

    cursor.execute("""
        SELECT titulo, destino, data_agendada FROM lembretes
        WHERE id_usuario = ? ORDER BY data_agendada
    """, (id_usuario,))
    lembretes = [{"titulo": l[0], "destino": l[1], "data": l[2]} for l in cursor.fetchall()]
    conn.close()
    return render_template("lembretes.html", lembretes=lembretes)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
