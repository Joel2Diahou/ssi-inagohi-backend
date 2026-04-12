from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sqlite3
from datetime import datetime

app = Flask(__name__, static_folder='../site_web', static_url_path='')
CORS(app)

def init_db():
    conn = sqlite3.connect('ssi_inagohi.db')
    c = conn.cursor()
    
    # Table compteur
    c.execute('''CREATE TABLE IF NOT EXISTS compteur 
                 (id INTEGER PRIMARY KEY, total INTEGER)''')
    c.execute("INSERT OR IGNORE INTO compteur (id, total) VALUES (1, 0)")
    
    # Table evenements
    c.execute('''CREATE TABLE IF NOT EXISTS evenements 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  type TEXT, nom TEXT, heure TEXT, date TEXT)''')
    
    # Table eleves
    c.execute('''CREATE TABLE IF NOT EXISTS eleves
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  nom TEXT NOT NULL,
                  prenom TEXT NOT NULL,
                  classe TEXT,
                  photo_path TEXT,
                  parent_nom TEXT,
                  parent_tel TEXT,
                  parent_email TEXT,
                  date_inscription TEXT)''')
    
    # Table alertes
    c.execute('''CREATE TABLE IF NOT EXISTS alertes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  type TEXT NOT NULL,
                  date TEXT,
                  heure TEXT,
                  lieu TEXT,
                  details TEXT,
                  photo TEXT,
                  statut TEXT DEFAULT 'non_traite')''')
    
    # Table absences
    c.execute('''CREATE TABLE IF NOT EXISTS absences
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  eleve_id INTEGER,
                  eleve_nom TEXT,
                  classe TEXT,
                  date TEXT,
                  heure_debut TEXT,
                  heure_fin TEXT,
                  duree_minutes INTEGER,
                  notifie BOOLEAN DEFAULT 0)''')
    
    # Ajouter des élèves de test si la table est vide
    c.execute("SELECT COUNT(*) FROM eleves")
    if c.fetchone()[0] == 0:
        eleves_test = [
            ("KOUASSI", "Jean", "4ème A", "M. KOUASSI", "+225 01 23 45 67", "parent.kouassi@email.com"),
            ("TRAORE", "Awa", "4ème A", "Mme TRAORE", "+225 01 23 45 68", "parent.traore@email.com"),
            ("TOURE", "Ibrahim", "3ème B", "M. TOURE", "+225 01 23 45 69", "parent.toure@email.com"),
            ("BAMBA", "Fatou", "Tle D", "M. BAMBA", "+225 07 89 12 34", "parent.bamba@email.com"),
            ("KONE", "Moussa", "2nde C", "Mme KONE", "+225 05 67 89 01", "parent.kone@email.com"),
        ]
        for e in eleves_test:
            c.execute('''INSERT INTO eleves (nom, prenom, classe, parent_nom, parent_tel, parent_email, date_inscription)
                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                      (e[0], e[1], e[2], e[3], e[4], e[5], datetime.now().strftime("%Y-%m-%d")))
    
    # Ajouter des alertes de test
    c.execute("SELECT COUNT(*) FROM alertes")
    if c.fetchone()[0] == 0:
        alertes_test = [
            ("intrusion", "2026-04-11", "08:15:22", "Portail principal", "Personne non identifiée", None),
            ("objet_dangereux", "2026-04-11", "09:30:10", "Portail principal", "Couteau détecté", None),
            ("intrusion", "2026-04-10", "14:20:05", "Portail secondaire", "Tentative d'escalade", None),
            ("bagarre", "2026-04-10", "10:45:33", "Cour de récréation", "Attroupement suspect", None),
        ]
        for a in alertes_test:
            c.execute('''INSERT INTO alertes (type, date, heure, lieu, details, photo, statut)
                         VALUES (?, ?, ?, ?, ?, ?, 'non_traite')''', a)
    
    # Ajouter des absences de test
    c.execute("SELECT COUNT(*) FROM absences")
    if c.fetchone()[0] == 0:
        absences_test = [
            (1, "KOUASSI Jean", "4ème A", "2026-04-11", "08:00", "09:30", 90, 0),
            (2, "TRAORE Awa", "4ème A", "2026-04-11", "10:00", "10:45", 45, 0),
            (3, "TOURE Ibrahim", "3ème B", "2026-04-10", "14:00", "15:30", 90, 1),
        ]
        for a in absences_test:
            c.execute('''INSERT INTO absences (eleve_id, eleve_nom, classe, date, heure_debut, heure_fin, duree_minutes, notifie)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', a)
    
    conn.commit()
    conn.close()
    print("✅ Base de donnees OK")

# ============================================
# ROUTES SITE WEB
# ============================================

@app.route('/')
def index():
    return send_from_directory('../site_web', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('../site_web', path)

# ============================================
# ROUTES API
# ============================================

@app.route('/api/status')
def status():
    return jsonify({"status": "ok", "message": "API SSI Inagohi operationnelle"})

@app.route('/api/compteur')
def compteur():
    conn = sqlite3.connect('ssi_inagohi.db')
    c = conn.cursor()
    c.execute("SELECT total FROM compteur WHERE id=1")
    total = c.fetchone()[0]
    conn.close()
    return jsonify({"total": total})

@app.route('/api/entree', methods=['POST'])
def entree():
    data = request.json
    nom = data.get('nom', 'Inconnu')
    now = datetime.now()
    conn = sqlite3.connect('ssi_inagohi.db')
    c = conn.cursor()
    c.execute("UPDATE compteur SET total = total + 1 WHERE id=1")
    c.execute("INSERT INTO evenements (type, nom, heure, date) VALUES ('entree', ?, ?, ?)",
              (nom, now.strftime("%H:%M:%S"), now.strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()
    print(f"📥 {nom} est entre a {now.strftime('%H:%M:%S')}")
    return jsonify({"status": "ok"})

@app.route('/api/evenements')
def evenements():
    conn = sqlite3.connect('ssi_inagohi.db')
    c = conn.cursor()
    c.execute("SELECT type, nom, heure FROM evenements ORDER BY id DESC LIMIT 20")
    events = c.fetchall()
    conn.close()
    return jsonify([{"type": e[0], "nom": e[1], "heure": e[2]} for e in events])

# ============================================
# ROUTES ÉLÈVES
# ============================================

@app.route('/api/eleves', methods=['GET'])
def get_eleves():
    conn = sqlite3.connect('ssi_inagohi.db')
    c = conn.cursor()
    c.execute("SELECT id, nom, prenom, classe, photo_path, parent_nom, parent_tel, parent_email FROM eleves")
    eleves = c.fetchall()
    conn.close()
    return jsonify([{
        "id": e[0], "nom": e[1], "prenom": e[2], "classe": e[3],
        "photo_path": e[4], "parent_nom": e[5], "parent_tel": e[6], "parent_email": e[7]
    } for e in eleves])

@app.route('/api/eleves', methods=['POST'])
def add_eleve():
    data = request.json
    conn = sqlite3.connect('ssi_inagohi.db')
    c = conn.cursor()
    c.execute('''INSERT INTO eleves (nom, prenom, classe, photo_path, parent_nom, parent_tel, parent_email, date_inscription)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (data['nom'], data['prenom'], data['classe'], data.get('photo_path'),
               data.get('parent_nom'), data.get('parent_tel'), data.get('parent_email'),
               datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"}), 201

@app.route('/api/eleves/<int:id>', methods=['DELETE'])
def delete_eleve(id):
    conn = sqlite3.connect('ssi_inagohi.db')
    c = conn.cursor()
    c.execute("DELETE FROM eleves WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# ============================================
# ROUTES ALERTES
# ============================================

@app.route('/api/alertes', methods=['GET'])
def get_alertes():
    conn = sqlite3.connect('ssi_inagohi.db')
    c = conn.cursor()
    c.execute("SELECT id, type, date, heure, lieu, details, photo, statut FROM alertes ORDER BY id DESC")
    alertes = c.fetchall()
    conn.close()
    return jsonify([{
        "id": a[0], "type": a[1], "date": a[2], "heure": a[3],
        "lieu": a[4], "details": a[5], "photo": a[6], "statut": a[7]
    } for a in alertes])

@app.route('/api/alertes/<int:id>/traiter', methods=['PUT'])
def traiter_alerte(id):
    conn = sqlite3.connect('ssi_inagohi.db')
    c = conn.cursor()
    c.execute("UPDATE alertes SET statut = 'traite' WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# ============================================
# ROUTES ABSENCES
# ============================================

@app.route('/api/absences', methods=['GET'])
def get_absences():
    date = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))
    conn = sqlite3.connect('ssi_inagohi.db')
    c = conn.cursor()
    c.execute("SELECT * FROM absences WHERE date = ? ORDER BY heure_debut DESC", (date,))
    absences = c.fetchall()
    conn.close()
    return jsonify([{
        "id": a[0], "eleve_id": a[1], "eleve_nom": a[2], "classe": a[3],
        "date": a[4], "heure_debut": a[5], "heure_fin": a[6],
        "duree_minutes": a[7], "notifie": a[8]
    } for a in absences])

# ============================================
# DÉMARRAGE
# ============================================

if __name__ == '__main__':
    init_db()
    print("=" * 50)
    print("🚀 SERVEUR SSI INAGOHI")
    print("📡 http://localhost:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)