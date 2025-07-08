import sqlite3
from flask import Flask, render_template, request, redirect, session
from flask_session import Session
from datetime import datetime, timedelta
import bcrypt

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

def get_db():
    conn = sqlite3.connect('banco.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# AUTENTICAÇÃO
@app.route('/', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user_input = request.form['user_input']
        password = request.form['password']
        conn = get_db(); cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, hashed_password, area_estudo FROM usuarios WHERE cpf=? OR email=?",
            (user_input, user_input)
        )
        user = cur.fetchone(); conn.close()
        if user and bcrypt.checkpw(password.encode(), user['hashed_password']):
            session['usuario_id'] = user['id']
            return redirect('/verificar_questoes')
        return render_template('login.html', error='Credenciais inválidas')
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        # lógica de cadastro (nome, cpf, email, estado, area_estudo, senha hashed)
        pass
    return render_template('register.html')

# ROTA: VERIFICAR QUESTÕES (com revisão inteligente)
@app.route('/verificar_questoes')
def verificar_questoes():
    if 'usuario_id' not in session:
        return redirect('/')
    uid = session['usuario_id']
    lei = request.args.get('lei')
    artigo = request.args.get('artigo')
    modalidade = request.args.get('modalidade')
    nivel = request.args.get('nivel')
    revisar = request.args.get('revisar_erradas')
    dias = int(request.args.get('dias', 7))

    conn = get_db(); cur = conn.cursor()
    if revisar == '1':
        limite = datetime.now() - timedelta(days=dias)
        cur.execute(
            """
            SELECT DISTINCT q.* FROM respostas r
            JOIN questoes q ON q.id = r.id_questao
            WHERE r.id_usuario=? AND r.acertou=0 AND r.data_resposta>=?
            """, (uid, limite.strftime('%Y-%m-%d %H:%M:%S'))
        )
    else:
        query = 'SELECT * FROM questoes WHERE 1=1'
        params = []
        if lei:
            query += ' AND lei=?'; params.append(lei)
        if artigo:
            query += ' AND artigo=?'; params.append(artigo)
        if modalidade:
            query += ' AND modalidade=?'; params.append(modalidade)
        if nivel:
            query += ' AND nivel=?'; params.append(nivel)
        cur.execute(query, params)
    rows = cur.fetchall(); conn.close()

    questoes = []
    for q in rows:
        questoes.append({
            'id': q['id'],
            'lei': q['lei'],
            'artigo': q['artigo'],
            'nivel': q['nivel'],
            'enunciado': q['enunciado'],
            'alternativas': eval(q['alternativas']),
            'correta': q['correta'],
            'fundamento': q['fundamento']
        })
    return render_template('verificar_questoes.html', questoes=questoes)

# Demais rotas (resolver_real, comentar, favoritar, etc.) devem estar definidas aqui.

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
