import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import random

app = Flask(__name__)
socketio = SocketIO(app)

players = {}  # sid: {name, score, last_answer, correct}
current_question = 0
question_active = False

questions = [
    {
        'question': 'What is the capital of France?',
        'choices': ['Paris', 'Berlin', 'Rome', 'Madrid'],
        'answer': 'Paris'
    },
    {
        'question': 'What is 5 + 7?',
        'choices': ['10', '12', '13', '14'],
        'answer': '12'
    },
    {
        'question': 'Which planet is known as the Red Planet?',
        'choices': ['Earth', 'Mars', 'Jupiter', 'Saturn'],
        'answer': 'Mars'
    },
    {
        'question': 'Who wrote "1984"?',
        'choices': ['Orwell', 'Huxley', 'Kafka', 'Camus'],
        'answer': 'Orwell'
    }
]

# questions zaten yukarıda tanımlı
original_questions = questions.copy()  # ilk tanımda kopyala
random.shuffle(questions)             # oyuna başlarken karıştır

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/host')
def host():
    return render_template('host.html')

def broadcast_player_list():
    # Gönderirken katılımcıların isim, puan, cevap durumu olsun
    status_list = []
    for p in players.values():
        status_list.append({
            'name': p['name'],
            'score': p['score'],
            'last_answer': p.get('last_answer', None),
            'answered': 'last_answer' in p
        })
    socketio.emit('player_list_update', status_list)

@socketio.on('join')
def handle_join(data):
    print(data)
    print('im hereeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee')
    name = data['name']
    sid = request.sid

    # Check if player with this name already exists (old_sid and data)
    old_sid = None
    old_data = None
    print(players)
    for s, p in players.items():
        print(p['name'])
        print(name)
        if p['name'] == name:
            old_sid = s
            old_data = p
            print(old_data)
            break

    if old_data:
        # Player existed: update players dict with new sid, keep old score
        players[sid] = old_data
        if old_sid != sid:
            del players[old_sid]
        print(f"{name} re-joined with score {old_data['score']}")
    else:
        # New player, add fresh
        players[sid] = {'name': name, 'score': 0}
        print(f"{name} joined as new player")

    # Send current question if active
    if question_active:
        emit('show_question', questions[current_question], room=sid)

    broadcast_player_list()

@socketio.on('send_question')
def send_question():
    global current_question, question_active
    if question_active:
        # Önceki soru bitmeden yeni gönderme
        return
    if current_question < len(questions):
        q = questions[current_question]
        # Her yeni soru öncesi oyuncuların cevaplarını temizle
        for p in players.values():
            p.pop('last_answer', None)
            p.pop('correct', None)
        socketio.emit('show_question', q)
        question_active = True
        broadcast_player_list()
    else:
        socketio.emit('show_question', {'question': 'Game Over!', 'choices': []})

@socketio.on('submit_answer')
def handle_answer(data):
    global question_active
    answer = data['answer']
    sid = request.sid

    if sid in players and question_active:
        # Check if player already submitted
        if 'last_answer' not in players[sid]:
            players[sid]['last_answer'] = answer
            correct_answer = questions[current_question]['answer']
            players[sid]['correct'] = (answer == correct_answer)
            broadcast_player_list()
        else:
            # Optional: emit a message saying "You already answered"
            socketio.emit('answer_locked', {'message': 'You have already submitted an answer.'}, to=sid)

@socketio.on('reveal_answers')
def reveal():
    global current_question, question_active
    if not question_active:
        return
    # Cevap vermeyenlere None ata ve doğruyu işaretle (False)
    for p in players.values():
        if 'last_answer' not in p:
            p['last_answer'] = None
            p['correct'] = False
    # Puanları güncelle
    for p in players.values():
        if p['correct']:
            p['score'] += 1

    # Sonuçları oyunculara gönder
    results = {}
    for p in players.values():
        results[p['name']] = {
            'answer': p['last_answer'] if p['last_answer'] is not None else 'None',
            'correct': p['correct'],
            'score': p['score']
        }
    socketio.emit('reveal_answers', results)


    # 💡 Emit leaderboard
    leaderboard = sorted(
        [{'name': p['name'], 'score': p['score']} for p in players.values()],
        key=lambda x: x['score'], reverse=True
    )
    socketio.emit('leaderboard', leaderboard)

    current_question += 1
    question_active = False
    broadcast_player_list()


@socketio.on('reset_game')
def reset_game():
    global current_question, question_active, questions
    current_question = 0
    question_active = False
    for p in players.values():
        p['score'] = 0
        p.pop('last_answer', None)
        p.pop('correct', None)
    questions = original_questions.copy()
    random.shuffle(questions)

    # Oyunculara da reset sinyali gönder
    socketio.emit('reset')

    # Oyunculara bilgi amaçlı boş soru gönder (ekranı temizlemek için)
    socketio.emit('show_question', {
        'question': 'Game Reset! Click Send Question to begin.',
        'choices': []
    })

    broadcast_player_list()

@socketio.on('disconnect')
def disconnect():
    if request.sid in players:
        print(f"{players[request.sid]['name']} disconnected")
        del players[request.sid]
        broadcast_player_list()

if __name__ == '__main__':
    print("Starting server...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
