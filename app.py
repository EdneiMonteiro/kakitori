from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
import requests
import json
import azure.cognitiveservices.speech as speechsdk
from bs4 import BeautifulSoup
import tempfile
import os
import random
from datetime import datetime
import io
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration from environment variables
SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "eastus2")
TRANSLATOR_KEY = os.getenv("AZURE_TRANSLATOR_KEY")
TRANSLATOR_ENDPOINT = os.getenv("AZURE_TRANSLATOR_ENDPOINT")
TRANSLATOR_REGION = os.getenv("AZURE_TRANSLATOR_REGION", "eastus2")

# Database initialization
def init_db():
    conn = sqlite3.connect('kakitori.db')
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hiragana (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kanji TEXT,
            level TEXT,
            word TEXT UNIQUE,
            meaning TEXT,
            audio1 BLOB,
            audio2 BLOB,
            audio3 BLOB
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            hiragana_id INTEGER,
            FOREIGN KEY (session_id) REFERENCES sessions (id),
            FOREIGN KEY (hiragana_id) REFERENCES hiragana (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            hiragana_id INTEGER,
            attempt_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            writing_correct BOOLEAN,
            meaning_correct BOOLEAN,
            FOREIGN KEY (session_id) REFERENCES sessions (id),
            FOREIGN KEY (hiragana_id) REFERENCES hiragana (id)
        )
    ''')
    
    conn.commit()
    conn.close()

class Meaning:
    def __init__(self, word, furigana, level, kanji, text):
        self.word = word
        self.furigana = furigana
        self.level = level
        self.kanji = kanji
        self.text = text

def get_meanings(word):
    """Scrape Jisho.org for word meanings"""
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
    }
    
    meanings = []
    try:
        response = requests.get(f"https://jisho.org/search/{word}", headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Get all concept blocks (not just exact_block)
        representations = soup.select('div.concept_light.clearfix')
        
        print(f"🔍 Encontrados {len(representations)} resultados para '{word}' no Jisho.org")
        
        for i, representation in enumerate(representations[:10]):  # Increased to 10 results
            furigana_node = representation.select_one('span.furigana')
            kanji_node = representation.select_one('span.text')
            meaning_node = representation.select_one('span.meaning-meaning')
            level_node = representation.select_one('span.concept_light-tag.label')
            
            furigana = furigana_node.get_text(strip=True) if furigana_node else ""
            kanji = kanji_node.get_text(strip=True) if kanji_node else ""
            meaning = meaning_node.get_text(strip=True) if meaning_node else ""
            level = "JLPT N0"
            
            if level_node and "JLPT" in level_node.get_text():
                level = level_node.get_text(strip=True)
            
            # Skip if no meaning found
            if not meaning:
                continue
                
            print(f"  📝 Resultado {i+1}: {furigana} | {kanji} | {meaning}")
            
            try:
                translated = translate_to_portuguese(meaning)
                final_meaning = f"{meaning}/{translated}"
            except:
                final_meaning = meaning
            
            meanings.append(Meaning(word, furigana, level, kanji, final_meaning))
    
    except Exception as e:
        print(f"❌ Erro ao buscar significados: {e}")
    
    print(f"✅ Total de {len(meanings)} significados processados para '{word}'")
    return meanings

def translate_to_portuguese(text):
    """Translate text to Portuguese using Azure Translator"""
    if not TRANSLATOR_KEY or not TRANSLATOR_ENDPOINT:
        return text
    
    route = "/translate?api-version=3.0&from=en&to=pt-br"
    url = TRANSLATOR_ENDPOINT + route
    
    headers = {
        'Ocp-Apim-Subscription-Key': TRANSLATOR_KEY,
        'Ocp-Apim-Subscription-Region': TRANSLATOR_REGION,
        'Content-Type': 'application/json'
    }
    
    body = [{'text': text}]
    
    try:
        response = requests.post(url, headers=headers, json=body)
        result = response.json()
        return result[0]['translations'][0]['text']
    except:
        return text

def generate_speech(voice, text):
    """Generate speech audio using Azure Speech Service"""
    if not SPEECH_KEY:
        print("⚠️  Azure Speech Key não configurada. Configurar no arquivo .env")
        return None
    
    speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
    speech_config.speech_synthesis_voice_name = voice
    
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
    
    try:
        result = synthesizer.speak_text_async(text).get()
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print(f"✅ Áudio gerado com sucesso para: {text} ({voice})")
            return result.audio_data
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = speechsdk.SpeechSynthesisCancellationDetails.FromResult(result)
            print(f"❌ Síntese cancelada: {cancellation.reason}")
            if cancellation.reason == speechsdk.CancellationReason.Error:
                print(f"❌ Erro: {cancellation.error_details}")
    except Exception as e:
        print(f"❌ Erro ao gerar áudio: {e}")
    
    return None

def word_exists(word):
    """Check if word already exists in database"""
    conn = sqlite3.connect('kakitori.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM hiragana WHERE word = ?", (word,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def add_word(kanji, level, word, meaning, audio1, audio2, audio3):
    """Add word to database"""
    conn = sqlite3.connect('kakitori.db')
    cursor = conn.cursor()
    
    # Extract level number (e.g., "JLPT N5" -> "N5")
    level_clean = level.split(' ')[-1] if ' ' in level else level
    
    cursor.execute('''
        INSERT INTO hiragana (kanji, level, word, meaning, audio1, audio2, audio3)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (kanji, level_clean, word, meaning, audio1, audio2, audio3))
    
    conn.commit()
    conn.close()

def get_random_words(count=5):
    """Get random words and create a new session"""
    conn = sqlite3.connect('kakitori.db')
    cursor = conn.cursor()
    
    # Create new session
    cursor.execute("INSERT INTO sessions (session_date) VALUES (datetime('now'))")
    session_id = cursor.lastrowid
    
    # Get random words
    cursor.execute("""
        SELECT id, word, audio1, audio2, audio3, meaning 
        FROM hiragana 
        ORDER BY RANDOM() 
        LIMIT ?
    """, (count,))
    
    words = cursor.fetchall()
    
    # Add words to session
    for word in words:
        cursor.execute("""
            INSERT INTO session_words (session_id, hiragana_id) 
            VALUES (?, ?)
        """, (session_id, word[0]))
    
    conn.commit()
    conn.close()
    
    # Return words with session_id
    return [(session_id, *word) for word in words]

def get_session_words(session_id, only_errors=False):
    """Get words from a specific session"""
    conn = sqlite3.connect('kakitori.db')
    cursor = conn.cursor()
    
    error_condition = ""
    if only_errors:
        error_condition = """
            AND EXISTS (
                SELECT 1 FROM session_attempts sa
                WHERE sa.session_id = sw.session_id 
                AND sa.hiragana_id = h.id
                AND (sa.writing_correct = 0 OR sa.meaning_correct = 0)
            )
        """
    
    query = f"""
        SELECT sw.session_id, h.id, h.word, h.audio1, h.audio2, h.audio3, h.meaning 
        FROM session_words sw
        JOIN hiragana h ON sw.hiragana_id = h.id
        WHERE sw.session_id = ?
        {error_condition}
        ORDER BY RANDOM()
    """
    
    cursor.execute(query, (session_id,))
    words = cursor.fetchall()
    conn.close()
    
    return words

def insert_attempt(session_id, hiragana_id, writing_correct, meaning_correct):
    """Record attempt results"""
    conn = sqlite3.connect('kakitori.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO session_attempts (session_id, hiragana_id, attempt_date, writing_correct, meaning_correct)
        VALUES (?, ?, datetime('now'), ?, ?)
    """, (session_id, hiragana_id, writing_correct, meaning_correct))
    
    conn.commit()
    conn.close()

def calculate_session_score(session_id):
    """Calculate session score"""
    conn = sqlite3.connect('kakitori.db')
    cursor = conn.cursor()
    
    # Total words in session
    cursor.execute("SELECT COUNT(*) FROM session_words WHERE session_id = ?", (session_id,))
    total_words = cursor.fetchone()[0]
    
    # Correct attempts
    cursor.execute("""
        SELECT COUNT(*) FROM session_attempts 
        WHERE session_id = ? AND writing_correct = 1 AND meaning_correct = 1
    """, (session_id,))
    correct_attempts = cursor.fetchone()[0]
    
    conn.close()
    
    if total_words == 0:
        return 0
    
    return round((correct_attempts / total_words) * 10, 2)

def delete_session_attempts(session_id):
    """Delete all attempts for a session"""
    conn = sqlite3.connect('kakitori.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM session_attempts WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add-word')
def add_word_page():
    return render_template('add_word.html')

@app.route('/practice')
def practice_page():
    return render_template('practice.html')

@app.route('/manage-words')
def manage_words_page():
    return render_template('manage_words.html')

@app.route('/api/status')
def api_status():
    """Check API configuration status"""
    status = {
        'azure_speech': bool(SPEECH_KEY),
        'azure_translator': bool(TRANSLATOR_KEY and TRANSLATOR_ENDPOINT)
    }
    return jsonify(status)

@app.route('/api/words', methods=['GET'])
def get_words():
    """Get all words with pagination and search"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '')
    
    conn = sqlite3.connect('kakitori.db')
    cursor = conn.cursor()
    
    # Build search query
    where_clause = ""
    params = []
    
    if search:
        where_clause = "WHERE word LIKE ? OR meaning LIKE ? OR kanji LIKE ?"
        search_term = f"%{search}%"
        params = [search_term, search_term, search_term]
    
    # Get total count
    count_query = f"SELECT COUNT(*) FROM hiragana {where_clause}"
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()[0]
    
    # Get paginated results
    offset = (page - 1) * per_page
    query = f"""
        SELECT id, word, kanji, level, meaning, 
               CASE WHEN audio1 IS NOT NULL THEN 1 ELSE 0 END as has_audio1,
               CASE WHEN audio2 IS NOT NULL THEN 1 ELSE 0 END as has_audio2,
               CASE WHEN audio3 IS NOT NULL THEN 1 ELSE 0 END as has_audio3
        FROM hiragana 
        {where_clause}
        ORDER BY id DESC 
        LIMIT ? OFFSET ?
    """
    
    cursor.execute(query, params + [per_page, offset])
    words = cursor.fetchall()
    conn.close()
    
    # Format results
    words_list = []
    for word in words:
        words_list.append({
            'id': word[0],
            'word': word[1],
            'kanji': word[2],
            'level': word[3],
            'meaning': word[4],
            'has_audio1': bool(word[5]),
            'has_audio2': bool(word[6]),
            'has_audio3': bool(word[7])
        })
    
    return jsonify({
        'words': words_list,
        'total': total_count,
        'page': page,
        'per_page': per_page,
        'pages': (total_count + per_page - 1) // per_page
    })

@app.route('/api/words/<int:word_id>', methods=['GET'])
def get_word(word_id):
    """Get specific word details"""
    conn = sqlite3.connect('kakitori.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, word, kanji, level, meaning,
               CASE WHEN audio1 IS NOT NULL THEN 1 ELSE 0 END as has_audio1,
               CASE WHEN audio2 IS NOT NULL THEN 1 ELSE 0 END as has_audio2,
               CASE WHEN audio3 IS NOT NULL THEN 1 ELSE 0 END as has_audio3
        FROM hiragana WHERE id = ?
    """, (word_id,))
    
    word = cursor.fetchone()
    conn.close()
    
    if not word:
        return jsonify({'error': 'Word not found'}), 404
    
    return jsonify({
        'id': word[0],
        'word': word[1],
        'kanji': word[2],
        'level': word[3],
        'meaning': word[4],
        'has_audio1': bool(word[5]),
        'has_audio2': bool(word[6]),
        'has_audio3': bool(word[7])
    })

@app.route('/api/words/<int:word_id>', methods=['PUT'])
def update_word(word_id):
    """Update word details"""
    data = request.json
    
    conn = sqlite3.connect('kakitori.db')
    cursor = conn.cursor()
    
    # Check if word exists
    cursor.execute("SELECT id FROM hiragana WHERE id = ?", (word_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Word not found'}), 404
    
    # Update word
    cursor.execute("""
        UPDATE hiragana 
        SET kanji = ?, level = ?, meaning = ?
        WHERE id = ?
    """, (data.get('kanji', ''), data.get('level', ''), data.get('meaning', ''), word_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Word updated successfully'})

@app.route('/api/words/<int:word_id>', methods=['DELETE'])
def delete_word(word_id):
    """Delete word and its related data"""
    conn = sqlite3.connect('kakitori.db')
    cursor = conn.cursor()
    
    try:
        # Check if word exists
        cursor.execute("SELECT word FROM hiragana WHERE id = ?", (word_id,))
        word_data = cursor.fetchone()
        
        if not word_data:
            return jsonify({'error': 'Word not found'}), 404
        
        word_text = word_data[0]
        
        # Delete related session attempts first
        cursor.execute("DELETE FROM session_attempts WHERE hiragana_id = ?", (word_id,))
        
        # Delete from session_words
        cursor.execute("DELETE FROM session_words WHERE hiragana_id = ?", (word_id,))
        
        # Delete the word
        cursor.execute("DELETE FROM hiragana WHERE id = ?", (word_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': f'Word "{word_text}" deleted successfully'})
        
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Error deleting word: {str(e)}'}), 500

@app.route('/api/words/<int:word_id>/regenerate-audio', methods=['POST'])
def regenerate_audio(word_id):
    """Regenerate audio for a specific word"""
    if not SPEECH_KEY:
        return jsonify({
            'error': 'Azure Speech Key not configured',
            'details': 'Configure AZURE_SPEECH_KEY in .env file'
        }), 400
    
    data = request.json
    use_kanji = data.get('use_kanji', False)
    
    conn = sqlite3.connect('kakitori.db')
    cursor = conn.cursor()
    
    # Get word details
    cursor.execute("SELECT word, kanji FROM hiragana WHERE id = ?", (word_id,))
    word_data = cursor.fetchone()
    
    if not word_data:
        conn.close()
        return jsonify({'error': 'Word not found'}), 404
    
    word_text, kanji_text = word_data
    text_to_speak = kanji_text if use_kanji and kanji_text else word_text
    
    # Generate new audio
    voices = ["ja-JP-NaokiNeural", "ja-JP-NanamiNeural", "ja-JP-AoiNeural"]
    
    audio1 = generate_speech(voices[0], text_to_speak)
    audio2 = generate_speech(voices[1], text_to_speak)
    audio3 = generate_speech(voices[2], text_to_speak)
    
    if not any([audio1, audio2, audio3]):
        conn.close()
        return jsonify({
            'error': 'Failed to generate audio',
            'details': 'Check Azure Speech Service credentials'
        }), 500
    
    # Update audio in database
    cursor.execute("""
        UPDATE hiragana 
        SET audio1 = ?, audio2 = ?, audio3 = ?
        WHERE id = ?
    """, (audio1, audio2, audio3, word_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Audio regenerated successfully'})

@app.route('/api/check-word', methods=['POST'])
def check_word():
    word = request.json.get('word', '')
    exists = word_exists(word)
    return jsonify({'exists': exists})

@app.route('/api/get-meanings', methods=['POST'])
def api_get_meanings():
    word = request.json.get('word', '')
    load_more = request.json.get('load_more', False)
    
    meanings = get_meanings_extended(word, limit=15 if load_more else 10)
    
    meanings_data = []
    for i, meaning in enumerate(meanings):
        meanings_data.append({
            'index': i,
            'word': meaning.word,
            'furigana': meaning.furigana,
            'kanji': meaning.kanji,
            'level': meaning.level,
            'text': meaning.text
        })
    
    return jsonify({
        'meanings': meanings_data,
        'has_more': len(meanings) >= (10 if not load_more else 15)
    })

def get_meanings_extended(word, limit=10):
    """Extended scraping with more results"""
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
    }
    
    meanings = []
    try:
        response = requests.get(f"https://jisho.org/search/{word}", headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Get all concept blocks from the main results area
        representations = soup.select('div.concept_light.clearfix')
        
        print(f"🔍 Encontrados {len(representations)} resultados para '{word}' no Jisho.org")
        
        for i, representation in enumerate(representations[:limit]):
            furigana_node = representation.select_one('span.furigana')
            kanji_node = representation.select_one('span.text')
            
            # Try multiple selectors for meanings
            meaning_node = (representation.select_one('span.meaning-meaning') or 
                          representation.select_one('.meaning-wrapper .meaning-meaning') or
                          representation.select_one('.meanings-wrapper .meaning-meaning'))
            
            level_nodes = representation.select('span.concept_light-tag.label')
            
            furigana = furigana_node.get_text(strip=True) if furigana_node else ""
            kanji = kanji_node.get_text(strip=True) if kanji_node else ""
            meaning = meaning_node.get_text(strip=True) if meaning_node else ""
            level = "JLPT N0"
            
            # Check all level nodes for JLPT
            for level_node in level_nodes:
                level_text = level_node.get_text(strip=True)
                if "JLPT" in level_text:
                    level = level_text
                    break
            
            # Skip if no meaning found
            if not meaning:
                print(f"  ⚠️  Pulando resultado {i+1}: sem significado")
                continue
                
            print(f"  📝 Resultado {i+1}: {furigana} | {kanji} | {meaning[:50]}...")
            
            try:
                translated = translate_to_portuguese(meaning)
                final_meaning = f"{meaning}/{translated}"
            except:
                final_meaning = meaning
            
            meanings.append(Meaning(word, furigana, level, kanji, final_meaning))
    
    except Exception as e:
        print(f"❌ Erro ao buscar significados: {e}")
    
    print(f"✅ Total de {len(meanings)} significados processados para '{word}'")
    return meanings

@app.route('/api/save-word', methods=['POST'])
def save_word():
    data = request.json
    word = data.get('word')
    meaning_index = data.get('meaning_index')
    use_kanji = data.get('use_kanji', False)
    custom_translation = data.get('custom_translation')
    
    # Get meanings again (in production, you'd cache this)
    meanings = get_meanings(word)
    
    if meaning_index >= len(meanings):
        return jsonify({'error': 'Invalid meaning index'}), 400
    
    meaning = meanings[meaning_index]
    
    if custom_translation:
        meaning.text = custom_translation
    
    # Check Azure credentials
    if not SPEECH_KEY:
        return jsonify({
            'error': 'Azure Speech Key não configurada', 
            'details': 'Configure AZURE_SPEECH_KEY no arquivo .env para gerar áudios'
        }), 400
    
    # Generate audio
    voices = ["ja-JP-NaokiNeural", "ja-JP-NanamiNeural", "ja-JP-AoiNeural"]
    text_to_speak = meaning.kanji if use_kanji else meaning.word
    
    print(f"🎵 Gerando áudios para: {text_to_speak}")
    audio1 = generate_speech(voices[0], text_to_speak)
    audio2 = generate_speech(voices[1], text_to_speak)
    audio3 = generate_speech(voices[2], text_to_speak)
    
    # Check if any audio was generated
    if not any([audio1, audio2, audio3]):
        return jsonify({
            'error': 'Falha na geração de áudio',
            'details': 'Verifique as credenciais do Azure Speech Service'
        }), 500
    
    try:
        add_word(meaning.kanji, meaning.level, meaning.word, meaning.text, audio1, audio2, audio3)
        return jsonify({'success': True, 'message': 'Palavra adicionada com sucesso!'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/start-practice', methods=['POST'])
def start_practice():
    data = request.json
    session_id = data.get('session_id')
    word_count = data.get('word_count', 5)
    
    if session_id:
        words = get_session_words(session_id)
    else:
        words = get_random_words(word_count)
    
    if not words:
        return jsonify({'error': 'No words found'}), 404
    
    # Clear previous attempts
    actual_session_id = words[0][0]
    delete_session_attempts(actual_session_id)
    
    # Format words for frontend
    formatted_words = []
    for word in words:
        formatted_words.append({
            'session_id': word[0],
            'id': word[1],
            'word': word[2],
            'meaning': word[6]
        })
    
    return jsonify({
        'session_id': actual_session_id,
        'words': formatted_words
    })

@app.route('/api/audio/<int:word_id>/<int:audio_num>')
def get_audio(word_id, audio_num):
    if audio_num not in [1, 2, 3]:
        return jsonify({'error': 'Audio number must be 1, 2, or 3'}), 400
    
    conn = sqlite3.connect('kakitori.db')
    cursor = conn.cursor()
    
    audio_column = f'audio{audio_num}'
    cursor.execute(f"SELECT {audio_column}, word FROM hiragana WHERE id = ?", (word_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        print(f"❌ Palavra com ID {word_id} não encontrada")
        return jsonify({'error': 'Word not found'}), 404
    
    audio_data, word = result
    
    if not audio_data:
        print(f"❌ Áudio {audio_num} não encontrado para palavra '{word}' (ID: {word_id})")
        return jsonify({'error': f'Audio {audio_num} not available for this word'}), 404
    
    print(f"✅ Servindo áudio {audio_num} para palavra '{word}' (ID: {word_id})")
    return send_file(
        io.BytesIO(audio_data),
        mimetype='audio/wav',
        as_attachment=False
    )

@app.route('/api/submit-attempt', methods=['POST'])
def submit_attempt():
    data = request.json
    session_id = data.get('session_id')
    word_id = data.get('word_id')
    writing_correct = data.get('writing_correct')
    meaning_correct = data.get('meaning_correct')
    
    insert_attempt(session_id, word_id, writing_correct, meaning_correct)
    
    return jsonify({'success': True})

@app.route('/api/session-score/<int:session_id>')
def get_session_score(session_id):
    score = calculate_session_score(session_id)
    return jsonify({'score': score})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)