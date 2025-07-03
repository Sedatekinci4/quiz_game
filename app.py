import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

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
    name = data['name']
    players[request.sid] = {'name': name, 'score': 0}
    print(f"{name} joined.")
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
        players[sid]['last_answer'] = answer
        correct_answer = questions[current_question]['answer']
        players[sid]['correct'] = (answer == correct_answer)
        broadcast_player_list()

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
    current_question += 1
    question_active = False
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
