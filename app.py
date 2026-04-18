import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import json

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Table compteur
    c.execute('''CREATE TABLE IF NOT EXISTS compteur (id SERIAL PRIMARY KEY, total INTEGER DEFAULT 0, derniere_mise_a_jour TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute("INSERT INTO compteur (total) SELECT 0 WHERE NOT EXISTS (SELECT 1 FROM compteur)")
    
    # Table eleves
    c.execute('''
        CREATE TABLE IF NOT EXISTS eleves (
            id SERIAL PRIMARY KEY,
            matricule VARCHAR(50) UNIQUE NOT NULL,
            nom VARCHAR(100) NOT NULL,
            prenom VARCHAR(100) NOT NULL,
            sexe CHAR(1),
            classe VARCHAR(50),
            photo_path TEXT,
            parent_nom VARCHAR(200),
            parent_tel VARCHAR(20),
            parent_email VARCHAR(100),
            date_inscription DATE DEFAULT CURRENT_DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
    
    # Table evenements
    c.execute('''CREATE TABLE IF NOT EXISTS evenements (
        id SERIAL PRIMARY KEY, type VARCHAR(50) NOT NULL, personne_nom VARCHAR(200),
        personne_statut VARCHAR(50), date DATE DEFAULT CURRENT_DATE,
        heure TIME DEFAULT CURRENT_TIME, lieu VARCHAR(100), details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Table alertes
    c.execute('''CREATE TABLE IF NOT EXISTS alertes (
        id SERIAL PRIMARY KEY, type VARCHAR(50) NOT NULL, date DATE DEFAULT CURRENT_DATE,
        heure TIME DEFAULT CURRENT_TIME, lieu VARCHAR(100), details TEXT, photo TEXT,
        statut VARCHAR(20) DEFAULT 'non_traite', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Table absences (COMPLÈTE)
    c.execute('''CREATE TABLE IF NOT EXISTS absences (
        id SERIAL PRIMARY KEY, 
        eleve_id INTEGER, 
        eleve_nom VARCHAR(200), 
        classe VARCHAR(50),
        date DATE DEFAULT CURRENT_DATE, 
        heure_debut TIME, 
        heure_fin TIME,
        duree_minutes INTEGER, 
        notifie BOOLEAN DEFAULT FALSE, 
        justifie BOOLEAN DEFAULT FALSE,
        permission_accordee BOOLEAN DEFAULT NULL,
        validee_par INTEGER REFERENCES personnel(id),
        date_validation TIMESTAMP,
        lieu VARCHAR(100) DEFAULT 'Salle de classe',
        camera_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Table classes
    c.execute('''CREATE TABLE IF NOT EXISTS classes (
        id SERIAL PRIMARY KEY, nom VARCHAR(50) UNIQUE NOT NULL, salle VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Table personnel
    c.execute('''CREATE TABLE IF NOT EXISTS personnel (
        id SERIAL PRIMARY KEY, nom VARCHAR(100) NOT NULL, prenom VARCHAR(100) NOT NULL,
        role VARCHAR(50), matiere VARCHAR(100), photo TEXT, telephone VARCHAR(20),
        email VARCHAR(100), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Table parents
    c.execute('''CREATE TABLE IF NOT EXISTS parents (
        id SERIAL PRIMARY KEY, nom VARCHAR(100) NOT NULL, prenom VARCHAR(100) NOT NULL,
        lien VARCHAR(50), eleve_id INTEGER REFERENCES eleves(id) ON DELETE SET NULL,
        photo TEXT, telephone VARCHAR(20), email VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Table emploi_du_temps
    c.execute('''
        CREATE TABLE IF NOT EXISTS emploi_du_temps (
            id SERIAL PRIMARY KEY,
            classe VARCHAR(50) NOT NULL,
            professeur_id INTEGER REFERENCES personnel(id),
            jour_semaine INTEGER,
            heure_debut TIME,
            heure_fin TIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
    
    conn.commit()
    conn.close()
    print("✅ Base de données PostgreSQL initialisée")

# ============================================
# ROUTES API
# ============================================

@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({"status": "ok", "message": "API SSI Inagohi operationnelle"})

@app.route('/api/compteur', methods=['GET'])
def get_compteur():
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT total FROM compteur WHERE id = 1")
    result = c.fetchone()
    conn.close()
    return jsonify({"total": result['total'] if result else 0})

@app.route('/api/evenement', methods=['POST'])
def recevoir_evenement():
    try:
        data = request.json
        print(f"📥 Événement reçu : {data}")
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''INSERT INTO evenements (type, personne_nom, personne_statut, date, heure, lieu, details)
                     VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                  (data.get('type'), data.get('personne_nom'), data.get('personne_statut'),
                   data.get('date'), data.get('heure'), data.get('lieu'),
                   json.dumps(data.get('details')) if data.get('details') else None))
        
        if data.get('type') == 'entree':
            c.execute("UPDATE compteur SET total = total + 1 WHERE id = 1")
        elif data.get('type') == 'sortie':
            c.execute("UPDATE compteur SET total = GREATEST(total - 1, 0) WHERE id = 1")
        
        conn.commit()
        conn.close()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/evenements', methods=['GET'])
def get_evenements():
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT type, personne_nom as nom, heure FROM evenements ORDER BY id DESC LIMIT 20")
    events = c.fetchall()
    conn.close()
    for e in events:
        if e['heure']:
            e['heure'] = e['heure'].strftime('%H:%M:%S')
    return jsonify(events)

# ============================================
# ROUTES ELEVES
# ============================================

@app.route('/api/eleves', methods=['GET'])
def get_eleves():
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT id, matricule, nom, prenom, sexe, classe, photo_path FROM eleves ORDER BY nom")
    eleves = c.fetchall()
    conn.close()
    return jsonify(eleves)

@app.route('/api/eleves', methods=['POST'])
def add_eleve():
    data = request.json
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO eleves (matricule, nom, prenom, sexe, classe, photo_path, date_inscription)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            data['matricule'],
            data['nom'],
            data['prenom'],
            data.get('sexe'),
            data['classe'],
            data.get('photo_path'),
            datetime.now().date()
        ))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"}), 201
    except psycopg2.IntegrityError:
        conn.close()
        return jsonify({"error": "Ce matricule existe déjà"}), 400

@app.route('/api/eleves/<int:id>', methods=['DELETE'])
def delete_eleve(id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM eleves WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# ============================================
# ROUTES CLASSES
# ============================================

@app.route('/api/classes', methods=['GET'])
def get_classes():
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT id, nom, salle FROM classes ORDER BY nom")
    classes = c.fetchall()
    conn.close()
    return jsonify(classes)

@app.route('/api/classes', methods=['POST'])
def add_classe():
    data = request.json
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO classes (nom, salle) VALUES (%s, %s)", (data['nom'], data.get('salle')))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"}), 201
    except psycopg2.IntegrityError:
        conn.close()
        return jsonify({"error": "Cette classe existe déjà"}), 400

@app.route('/api/classes/<int:id>', methods=['DELETE'])
def delete_classe(id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM classes WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# ============================================
# ROUTES PERSONNEL
# ============================================

@app.route('/api/personnel', methods=['GET'])
def get_personnel():
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT id, nom, prenom, role, matiere, photo, telephone, email FROM personnel ORDER BY nom")
    personnel = c.fetchall()
    conn.close()
    return jsonify(personnel)

@app.route('/api/personnel', methods=['POST'])
def add_personnel():
    data = request.json
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO personnel (nom, prenom, role, matiere, photo, telephone, email)
                 VALUES (%s, %s, %s, %s, %s, %s, %s)''',
              (data['nom'], data['prenom'], data.get('role'), data.get('matiere'),
               data.get('photo'), data.get('telephone'), data.get('email')))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"}), 201

@app.route('/api/personnel/<int:id>', methods=['DELETE'])
def delete_personnel(id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM personnel WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# ============================================
# ROUTES PARENTS
# ============================================

@app.route('/api/parents', methods=['GET'])
def get_parents():
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT p.*, e.nom as eleve_nom, e.prenom as eleve_prenom FROM parents p LEFT JOIN eleves e ON p.eleve_id = e.id ORDER BY p.nom")
    parents = c.fetchall()
    conn.close()
    return jsonify(parents)

@app.route('/api/parents', methods=['POST'])
def add_parent():
    data = request.json
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO parents (nom, prenom, lien, eleve_id, photo, telephone, email)
                 VALUES (%s, %s, %s, %s, %s, %s, %s)''',
              (data['nom'], data['prenom'], data.get('lien'), data.get('eleve_id'),
               data.get('photo'), data.get('telephone'), data.get('email')))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"}), 201

@app.route('/api/parents/<int:id>', methods=['DELETE'])
def delete_parent(id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM parents WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# ============================================
# ROUTES ALERTES
# ============================================

@app.route('/api/alertes', methods=['GET'])
def get_alertes():
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT id, type, date, heure, lieu, details, photo, statut FROM alertes ORDER BY id DESC LIMIT 50")
    alertes = c.fetchall()
    conn.close()
    for a in alertes:
        if a['date']: a['date'] = a['date'].strftime('%Y-%m-%d')
        if a['heure']: a['heure'] = a['heure'].strftime('%H:%M:%S')
    return jsonify(alertes)

@app.route('/api/alertes/<int:id>/traiter', methods=['PUT'])
def traiter_alerte(id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE alertes SET statut = 'traite' WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# ============================================
# ROUTES ABSENCES
# ============================================

@app.route('/api/absences', methods=['GET'])
def get_absences():
    date = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM absences WHERE date = %s ORDER BY heure_debut DESC", (date,))
    absences = c.fetchall()
    conn.close()
    for a in absences:
        if a['date']: a['date'] = a['date'].strftime('%Y-%m-%d')
        if a['heure_debut']: a['heure_debut'] = a['heure_debut'].strftime('%H:%M:%S')
        if a['heure_fin']: a['heure_fin'] = a['heure_fin'].strftime('%H:%M:%S')
    return jsonify(absences)

@app.route('/api/absences', methods=['POST'])
def add_absence():
    data = request.json
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO absences (eleve_nom, classe, date, heure_debut, lieu, camera_id, permission_accordee)
        VALUES (%s, %s, %s, %s, %s, %s, NULL)
        RETURNING id
    ''', (
        data['eleve_nom'],
        data['classe'],
        data['date'],
        data['heure_debut'],
        data.get('lieu', 'Salle de classe'),
        data.get('camera_id')
    ))
    absence_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "id": absence_id}), 201

@app.route('/api/absences/<int:id>/fin', methods=['PUT'])
def update_absence_fin(id):
    data = request.json
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        UPDATE absences 
        SET heure_fin = %s, 
            duree_minutes = EXTRACT(EPOCH FROM (%s::time - heure_debut))/60
        WHERE id = %s
    ''', (data['heure_fin'], data['heure_fin'], id))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# ============================================
# ROUTES EMPLOI DU TEMPS
# ============================================

@app.route('/api/emploi_du_temps', methods=['GET'])
def get_emploi_du_temps():
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("""
        SELECT e.*, p.nom as prof_nom, p.prenom as prof_prenom 
        FROM emploi_du_temps e 
        LEFT JOIN personnel p ON e.professeur_id = p.id 
        ORDER BY e.jour_semaine, e.heure_debut
    """)
    emplois = c.fetchall()
    conn.close()
    return jsonify(emplois)

@app.route('/api/emploi_du_temps', methods=['POST'])
def add_emploi_du_temps():
    data = request.json
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO emploi_du_temps (classe, professeur_id, jour_semaine, heure_debut, heure_fin)
        VALUES (%s, %s, %s, %s, %s)
    ''', (data['classe'], data['professeur_id'], data['jour_semaine'], data['heure_debut'], data['heure_fin']))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"}), 201

@app.route('/api/emploi_du_temps/<int:id>', methods=['DELETE'])
def delete_emploi_du_temps(id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM emploi_du_temps WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# ============================================
# ROUTE VALIDATION ABSENCES
# ============================================

@app.route('/api/absences/valider', methods=['POST'])
def valider_absences():
    data = request.json
    professeur_id = data.get('professeur_id')
    validations = data.get('validations', [])
    
    conn = get_db_connection()
    c = conn.cursor()
    
    for v in validations:
        permission = v.get('permission_accordee')
        absence_id = v.get('absence_id')
        
        if permission:
            c.execute("""
                UPDATE absences 
                SET permission_accordee = TRUE, 
                    validee_par = %s, 
                    date_validation = %s,
                    justifie = TRUE
                WHERE id = %s
            """, (professeur_id, datetime.now(), absence_id))
        else:
            c.execute("""
                UPDATE absences 
                SET permission_accordee = FALSE, 
                    validee_par = %s, 
                    date_validation = %s
                WHERE id = %s
            """, (professeur_id, datetime.now(), absence_id))
            
            c.execute("SELECT eleve_nom, classe, heure_debut, heure_fin FROM absences WHERE id = %s", (absence_id,))
            absence = c.fetchone()
            if absence:
                c.execute("""
                    INSERT INTO alertes (type, date, heure, lieu, details, statut)
                    VALUES (%s, %s, %s, %s, %s, 'non_traite')
                """, (
                    'absence_non_justifiee',
                    datetime.now().date(),
                    datetime.now().time(),
                    'Salle de classe',
                    f"Absence non justifiée : {absence[0]} ({absence[1]}) de {absence[2]} à {absence[3]}"
                ))
    
    conn.commit()
    conn.close()
    
    return jsonify({"status": "ok"})



# ============================================
# DÉMARRAGE
# ============================================

if __name__ == '__main__':
    if DATABASE_URL:
        print("🔄 Initialisation de la base de données...")
        init_db()
        print("✅ Tables créées avec succès !")
    else:
        print("⚠️ DATABASE_URL non définie")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
