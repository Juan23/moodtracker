from nicegui import ui, app
import sqlite3
import hashlib
from datetime import datetime

# --- Database Setup ---
DB_FILE = 'mood_journal.db'

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                energy TEXT,
                mood TEXT,
                weather TEXT,
                sleep TEXT,
                notes TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        try:
            conn.execute('ALTER TABLE entries ADD COLUMN sleep TEXT')
        except sqlite3.OperationalError:
            pass

init_db()

# --- Helpers ---
def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def db_create_user(email, password):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute('INSERT INTO users (email, password) VALUES (?, ?)', 
                         (email, hash_pw(password)))
        return True
    except sqlite3.IntegrityError:
        return False

def db_verify_user(email, password):
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.execute('SELECT id FROM users WHERE email = ? AND password = ?', 
                           (email, hash_pw(password)))
        row = cur.fetchone()
        return row[0] if row else None

def db_add_entry(user_id, dt_str, mood, energy, weather, sleep, notes):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('INSERT INTO entries (user_id, timestamp, mood, energy, weather, sleep, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
                     (user_id, dt_str, mood, energy, weather, sleep, notes))

def db_get_entries(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute('SELECT * FROM entries WHERE user_id = ? ORDER BY timestamp DESC', (user_id,))
        return [dict(row) for row in cur.fetchall()]

# --- UI Pages ---

@ui.page('/login')
def login():
    def try_login():
        user_id = db_verify_user(email.value, password.value)
        if user_id:
            app.storage.user.update({'user_id': user_id, 'authenticated': True})
            ui.navigate.to('/')
        else:
            ui.notify('Invalid email or password', color='negative')

    with ui.card().classes('absolute-center w-full max-w-sm p-8'):
        ui.label('Mood Journal Login').classes('text-2xl font-bold mb-4 self-center')
        email = ui.input('Email').classes('w-full')
        password = ui.input('Password', password=True, password_toggle_button=True).classes('w-full').on('keydown.enter', try_login)
        ui.button('Log in', on_click=try_login).classes('w-full mt-4')
        ui.link('Create account', '/register').classes('mt-4 self-center text-sm')

@ui.page('/register')
def register():
    def try_register():
        if not email.value or not password.value:
            ui.notify('Please fill all fields', color='warning')
            return
        if db_create_user(email.value, password.value):
            ui.notify('Account created! Please login.', color='positive')
            ui.navigate.to('/login')
        else:
            ui.notify('Email already exists', color='negative')

    with ui.card().classes('absolute-center w-full max-w-sm p-8'):
        ui.label('Create Account').classes('text-2xl font-bold mb-4 self-center')
        email = ui.input('Email').classes('w-full')
        password = ui.input('Password', password=True, password_toggle_button=True).classes('w-full')
        ui.button('Register', on_click=try_register).classes('w-full mt-4')
        ui.link('Back to Login', '/login').classes('mt-4 self-center text-sm')

@ui.page('/')
def home():
    if not app.storage.user.get('authenticated'):
        ui.navigate.to('/login')
        return

    user_id = app.storage.user['user_id']

    def logout():
        app.storage.user.clear()
        ui.navigate.to('/login')

    # Layout
    with ui.header().classes('bg-primary text-white items-center justify-between px-4'):
        ui.label('Mood Journal').classes('text-xl font-bold')
        ui.button('Logout', on_click=logout, icon='logout').props('flat color=white')

    with ui.column().classes('w-full max-w-3xl mx-auto p-4 gap-6'):
        with ui.row().classes('w-full justify-between items-center'):
            ui.label('History').classes('text-xl font-bold')
            ui.button('New Entry', on_click=lambda: ui.navigate.to('/new_entry'), icon='add').classes('bg-secondary text-white')
        
        entries = db_get_entries(user_id)
        if not entries:
            ui.label('No entries yet. Start tracking!').classes('text-gray-500 italic')
        else:
            for entry in entries:
                with ui.card().classes('w-full mb-2'):
                    with ui.row().classes('w-full justify-between items-start'):
                        with ui.column().classes('gap-0'):
                            ui.label(entry['timestamp']).classes('font-bold text-gray-700')
                            if entry['weather']:
                                ui.label(f"Weather: {entry['weather']}").classes('text-sm text-gray-500')
                        
                        with ui.row().classes('gap-2'):
                            ui.chip(f"Mood: {entry['mood']}", color='primary', text_color='white')
                            ui.chip(f"Energy: {entry['energy']}", color='orange', text_color='white')
                            if entry['sleep']:
                                ui.chip(f"Sleep: {entry['sleep']}", color='teal', text_color='white')
                    
                    if entry['notes']:
                        ui.separator().classes('my-2')
                        ui.markdown(entry['notes']).classes('text-gray-800')

@ui.page('/new_entry')
def new_entry_page():
    if not app.storage.user.get('authenticated'):
        ui.navigate.to('/login')
        return

    user_id = app.storage.user['user_id']
    now = datetime.now()
    
    # Form State
    form = {
        'date': now.strftime('%Y-%m-%d'),
        'time': now.strftime('%H:%M'),
        'mood': 'meh',
        'energy': 2, # Index for 'Ok'
        'weather': None,
        'sleep': None,
        'notes': ''
    }

    mood_options = [
        ('happy', 'sentiment_very_satisfied', 'green'),
        ('good', 'sentiment_satisfied', 'light-green'),
        ('meh', 'sentiment_neutral', 'grey'),
        ('bad', 'sentiment_dissatisfied', 'orange'),
        ('awful', 'sentiment_very_dissatisfied', 'red')
    ]

    weather_options = [
        ('sunny', 'wb_sunny', 'orange'),
        ('cloudy', 'cloud', 'grey'),
        ('rain', 'water_drop', 'blue'),
        ('snow', 'ac_unit', 'cyan')
    ]

    energy_labels = ['Exhausted', 'Low', 'Ok', 'High', 'Energized']

    def set_mood(val):
        form['mood'] = val
        render_mood_buttons.refresh()

    @ui.refreshable
    def render_mood_buttons():
        with ui.row().classes('w-full justify-between'):
            for m_val, m_icon, m_col in mood_options:
                props = f'color={m_col} unelevated' if form['mood'] == m_val else 'color=grey flat'
                ui.button(icon=m_icon, on_click=lambda v=m_val: set_mood(v)).props(f'round {props}')

    def set_weather(val):
        if form['weather'] == val:
            form['weather'] = None
        else:
            form['weather'] = val
        render_weather_buttons.refresh()

    @ui.refreshable
    def render_weather_buttons():
        with ui.row().classes('w-full justify-between'):
            for w_val, w_icon, w_col in weather_options:
                props = f'color={w_col} unelevated' if form['weather'] == w_val else 'color=grey flat'
                ui.button(icon=w_icon, on_click=lambda v=w_val: set_weather(v)).props(f'round {props}')

    def save_entry():
        dt_str = f"{form['date']} {form['time']}"
        energy_text = energy_labels[form['energy']]
        db_add_entry(user_id, dt_str, form['mood'], energy_text, form['weather'], form['sleep'], form['notes'])
        ui.notify('Entry saved!', color='positive')
        ui.navigate.to('/')

    with ui.header().classes('bg-primary text-white items-center justify-between px-4'):
        with ui.row().classes('items-center gap-2'):
            ui.button(icon='arrow_back', on_click=lambda: ui.navigate.to('/')).props('flat color=white round dense')
            ui.label('New Entry').classes('text-xl font-bold')

    with ui.column().classes('w-full max-w-3xl mx-auto p-4 gap-6'):
        with ui.card().classes('w-full p-4'):
            with ui.grid().classes('grid-cols-1 md:grid-cols-2 gap-4 w-full'):
                with ui.input('Date').bind_value(form, 'date').classes('w-full') as date_input:
                    with date_input.add_slot('append'):
                        ui.icon('event').classes('cursor-pointer').on('click', lambda: date_menu.open())
                        with ui.menu() as date_menu:
                            ui.date().bind_value(form, 'date').on('change', date_menu.close)
                
                with ui.input('Time').bind_value(form, 'time').classes('w-full') as time_input:
                    with time_input.add_slot('append'):
                        ui.icon('access_time').classes('cursor-pointer').on('click', lambda: time_menu.open())
                        with ui.menu() as time_menu:
                            ui.time().bind_value(form, 'time').on('change', time_menu.close)

                with ui.column().classes('w-full gap-2'):
                    ui.label('Mood')
                    render_mood_buttons()

                with ui.column().classes('w-full gap-2'):
                    with ui.row().classes('w-full justify-between'):
                        ui.label('Energy')
                        ui.label().bind_text_from(form, 'energy', lambda v: energy_labels[v]).classes('font-bold text-primary')
                    ui.slider(min=0, max=4, step=1).bind_value(form, 'energy').props('markers')
                    with ui.row().classes('w-full justify-between text-xs text-gray-400'):
                        ui.label(energy_labels[0])
                        ui.label(energy_labels[-1])

                with ui.column().classes('w-full gap-2'):
                    ui.label('Weather')
                    render_weather_buttons()

                ui.select(['Excellent', 'Good', 'Fair', 'Fragmented', 'Poor'], label='Sleep').bind_value(form, 'sleep').classes('w-full')

            ui.textarea('Notes/Comments').bind_value(form, 'notes').classes('w-full mt-2').props('rows=3')
            ui.button('Save Entry', on_click=save_entry).classes('w-full mt-4 bg-secondary text-white')

@app.get('/manifest.json')
def manifest():
    return {
        "name": "Mood Journal",
        "short_name": "Mood",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#5898d4",
        "theme_color": "#5898d4",
        "icons": [
            {
                "src": "https://cdn.quasar.dev/logo-v2/svg/logo.svg",
                "sizes": "512x512",
                "type": "image/svg+xml"
            }
        ]
    }

ui.add_head_html('''
    <link rel="manifest" href="/manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="theme-color" content="#5898d4">
''', shared=True)

ui.run(storage_secret='change_this_secret_key', title='Mood Journal')