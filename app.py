import os
import time
import random
import json
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sklearn.linear_model import LinearRegression
from tensorflow.keras.models import load_model
from database import db, User, Battery, init_db
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# Configuration
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///intellibms.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'csv', 'json', 'xlsx', 'xls', 'txt'}

# Initialize extensions
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Initialize database
init_db(app)

# --- Helper Functions ---
def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_battery_file(file_path, filename):
    """Parse uploaded battery file and extract battery parameters"""
    try:
        print(f"Parsing file: {filename}")
        file_ext = filename.rsplit('.', 1)[1].lower()
        print(f"File extension: {file_ext}")
        
        if file_ext == 'csv':
            df = pd.read_csv(file_path)
        elif file_ext in ['xlsx', 'xls']:
            df = pd.read_excel(file_path)
        elif file_ext == 'json':
            with open(file_path, 'r') as f:
                data = json.load(f)
            df = pd.DataFrame([data] if isinstance(data, dict) else data)
        elif file_ext == 'txt':
            # Try to parse as CSV first, then as key-value pairs
            try:
                df = pd.read_csv(file_path, delimiter='\t')
            except:
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                data = {}
                for line in lines:
                    if ':' in line:
                        key, value = line.strip().split(':', 1)
                        data[key.strip()] = value.strip()
                df = pd.DataFrame([data])
        
        # Extract battery parameters with defaults
        print(f"DataFrame columns: {df.columns.tolist() if hasattr(df, 'columns') else 'No columns'}")
        print(f"DataFrame shape: {df.shape if hasattr(df, 'shape') else 'No shape'}")
        
        battery_data = {
            'name': df.get('name', df.get('battery_name', ['Auto Battery']))[0] if len(df) > 0 else 'Auto Battery',
            'battery_type': df.get('type', df.get('battery_type', ['Li-ion']))[0] if len(df) > 0 else 'Li-ion',
            'num_cells': int(df.get('cells', df.get('num_cells', [48]))[0]) if len(df) > 0 else 48,
            'base_voltage': float(df.get('voltage', df.get('base_voltage', [4.1]))[0]) if len(df) > 0 else 4.1,
            'base_soh': float(df.get('soh', df.get('base_soh', [95.0]))[0]) if len(df) > 0 else 95.0,
            'base_temp': float(df.get('temperature', df.get('base_temp', [25.0]))[0]) if len(df) > 0 else 25.0,
            'degradation_rate': float(df.get('degradation', df.get('degradation_rate', [0.03]))[0]) if len(df) > 0 else 0.03,
            'fault_probability': float(df.get('fault_prob', df.get('fault_probability', [0.1]))[0]) if len(df) > 0 else 0.1,
            'capacity_ah': float(df.get('capacity', df.get('capacity_ah', [100.0]))[0]) if len(df) > 0 else 100.0,
            'max_charge_rate': float(df.get('charge_rate', df.get('max_charge_rate', [50.0]))[0]) if len(df) > 0 else 50.0,
            'max_discharge_rate': float(df.get('discharge_rate', df.get('max_discharge_rate', [100.0]))[0]) if len(df) > 0 else 100.0,
            'operating_temp_min': float(df.get('temp_min', df.get('operating_temp_min', [-10.0]))[0]) if len(df) > 0 else -10.0,
            'operating_temp_max': float(df.get('temp_max', df.get('operating_temp_max', [60.0]))[0]) if len(df) > 0 else 60.0,
            'description': df.get('description', ['Auto-generated from uploaded file'])[0] if len(df) > 0 else 'Auto-generated from uploaded file'
        }
        
        return battery_data
        
    except Exception as e:
        print(f"Error parsing file {filename}: {str(e)}")
        # Return default battery configuration
        return {
            'name': f'Auto Battery - {filename}',
            'battery_type': 'Li-ion',
            'num_cells': 48,
            'base_voltage': 4.1,
            'base_soh': 95.0,
            'base_temp': 25.0,
            'degradation_rate': 0.03,
            'fault_probability': 0.1,
            'capacity_ah': 100.0,
            'max_charge_rate': 50.0,
            'max_discharge_rate': 100.0,
            'operating_temp_min': -10.0,
            'operating_temp_max': 60.0,
            'description': f'Auto-generated from uploaded file: {filename}'
        }

# --- AI Model and Accuracy Metrics Loading ---
MODEL_FILE = 'soh_model.h5'
METRICS_FILE = 'accuracy_metrics.json'
model = None
model_performance = {"mae": "N/A", "r2_score": "N/A"}  # Default values

if os.path.exists(MODEL_FILE):
    try:
        model = load_model(MODEL_FILE)
        print("AI model loaded successfully.")
        # Load the metrics file created by the training script
        if os.path.exists(METRICS_FILE):
            with open(METRICS_FILE, 'r') as f:
                model_performance = json.load(f)
            print(f"Model performance metrics loaded: {model_performance}")
    except Exception as e:
        print(f"Error loading model or metrics: {e}")
else:
    print(f"CRITICAL: Model file '{MODEL_FILE}' not found. Please run 'generate_and_train.py' first.")

# --- Battery Configurations ---
BATTERY_CONFIGS = {
    1: {
        "name": "Tesla Model S Pack",
        "num_cells": 48,
        "base_voltage": 4.1,
        "base_soh": 98.5,
        "base_temp": 25.5,
        "degradation_rate": 0.02,
        "fault_probability": 0.1
    },
    2: {
        "name": "BMW i3 Pack", 
        "num_cells": 40,
        "base_voltage": 3.9,
        "base_soh": 85.2,
        "base_temp": 28.0,
        "degradation_rate": 0.05,
        "fault_probability": 0.3
    },
    3: {
        "name": "Nissan Leaf Pack",
        "num_cells": 44,
        "base_voltage": 4.0,
        "base_soh": 92.8,
        "base_temp": 26.2,
        "degradation_rate": 0.03,
        "fault_probability": 0.15
    },
    4: {
        "name": "Chevy Bolt Pack",
        "num_cells": 36,
        "base_voltage": 3.8,
        "base_soh": 76.3,
        "base_temp": 30.1,
        "degradation_rate": 0.08,
        "fault_probability": 0.5
    },
    5: {
        "name": "Audi e-tron Pack",
        "num_cells": 52,
        "base_voltage": 3.95,
        "base_soh": 89.7,
        "base_temp": 27.3,
        "degradation_rate": 0.04,
        "fault_probability": 0.2
    }
}

# --- Battery State Management ---
battery_states = {}

def initialize_battery_state(battery_id):
    """Initialize state for a specific battery"""
    if battery_id not in battery_states:
        config = BATTERY_CONFIGS[battery_id]
        
        # Generate history file for this battery
        history_file = f'soh_history_battery_{battery_id}.csv'
        if not os.path.exists(history_file):
            print(f"Generating synthetic history file: {history_file}...")
            timestamps = [int((datetime.now() - timedelta(days=x)).timestamp()) for x in range(180)]
            base_degradation = config["degradation_rate"] * 180 / 365 * 100  # Yearly degradation
            soh_history = config["base_soh"] + np.linspace(base_degradation, 0, 180) + np.random.normal(0, 0.5, 180)
            pd.DataFrame({'timestamp': sorted(timestamps), 'soh': soh_history}).to_csv(history_file, index=False)
        
        history_df = pd.read_csv(history_file)
        lr_model = LinearRegression().fit(history_df[['timestamp']], history_df['soh'])
        
        battery_states[battery_id] = {
            "config": config,
            "history_df": history_df,
            "lr_model": lr_model,
            "history_buffer": [],
            "battery_cells": [{"id": i, "voltage": config["base_voltage"], "is_faulty": False, "is_balancing": False, "temperature": config["base_temp"]} for i in range(config["num_cells"])],
            "pack_soh": config["base_soh"],
            "fault_introduced": False,
            "faulty_cell_index": -1,
            "last_fault_check_time": time.time()
        }
    
    return battery_states[battery_id]

# --- Long-Term Forecast & State Initialization (Legacy for backward compatibility) ---
HISTORY_FILE = 'soh_history.csv'
if not os.path.exists(HISTORY_FILE):
    print(f"Generating synthetic history file: {HISTORY_FILE}...")
    timestamps = [int((datetime.now() - timedelta(days=x)).timestamp()) for x in range(180)]
    soh_history = 100 - np.linspace(0, 3, 180) + np.random.normal(0, 0.1, 180)
    pd.DataFrame({'timestamp': sorted(timestamps), 'soh': soh_history}).to_csv(HISTORY_FILE, index=False)

history_df = pd.read_csv(HISTORY_FILE)
lr_model = LinearRegression().fit(history_df[['timestamp']], history_df['soh'])
NUM_CELLS, SEQUENCE_LENGTH = 48, 50
history_buffer = []
battery_cells = [{"id": i, "voltage": 4.1, "is_faulty": False, "is_balancing": False, "temperature": 25.5} for i in range(NUM_CELLS)]
pack_soh, fault_introduced, faulty_cell_index = 99.8, False, -1
last_fault_check_time = time.time()

# --- AI Prediction & Forecast Functions ---
def get_ai_prediction(current_features, battery_state=None):
    if model is None: return None
    
    # Use battery-specific history buffer if provided
    if battery_state:
        history_buffer_to_use = battery_state["history_buffer"]
    else:
        history_buffer_to_use = history_buffer
    
    history_buffer_to_use.append(current_features)
    if len(history_buffer_to_use) > SEQUENCE_LENGTH: 
        history_buffer_to_use.pop(0)
    if len(history_buffer_to_use) < SEQUENCE_LENGTH: 
        return None
    
    # Simple scaling for live prediction
    live_data_scaled = (np.array(history_buffer_to_use) - [4.1, 20, 35, 90]) / [0.1, 10, 10, 10]
    reshaped_data = live_data_scaled.reshape(1, SEQUENCE_LENGTH, 4)
    predicted_soh_scaled = model.predict(reshaped_data, verbose=0)[0][0]
    return float(predicted_soh_scaled * 20 + 80) # Inverse scale

def get_long_term_forecast(battery_state=None):
    # Use battery-specific data if provided
    if battery_state:
        lr_model_to_use = battery_state["lr_model"]
        history_df_to_use = battery_state["history_df"]
    else:
        lr_model_to_use = lr_model
        history_df_to_use = history_df
    
    future_ts = [int((datetime.now() + timedelta(days=x*30)).timestamp()) for x in range(1, 25)]
    future_soh = lr_model_to_use.predict(np.array(future_ts).reshape(-1, 1))
    projection = [{'x': ts, 'y': soh} for ts, soh in zip(future_ts, future_soh)]
    forecast_text = "Stable"
    for ts, soh in zip(future_ts, future_soh):
        if soh <= 80:
            forecast_text = datetime.fromtimestamp(ts).strftime("%b %Y"); break
    return {"text": forecast_text, "history": history_df_to_use.to_dict('records'), "projection": projection}

# --- Main Simulation Functions ---
def simulate_battery_data(battery_id=None):
    """Simulate battery data for a specific battery or default battery"""
    if battery_id and battery_id in BATTERY_CONFIGS:
        return simulate_specific_battery_data(battery_id)
    else:
        return simulate_default_battery_data()

def simulate_custom_battery_data(battery):
    """Simulate data for a custom user-defined battery"""
    # Convert Battery model to config format
    config = {
        "name": battery.name,
        "num_cells": battery.num_cells,
        "base_voltage": battery.base_voltage,
        "base_soh": battery.base_soh,
        "base_temp": battery.base_temp,
        "degradation_rate": battery.degradation_rate,
        "fault_probability": battery.fault_probability
    }
    
    # Initialize battery state if not exists
    battery_id = f"custom_{battery.id}"
    if battery_id not in battery_states:
        # Generate history file for this battery
        history_file = f'soh_history_custom_{battery.id}.csv'
        if not os.path.exists(history_file):
            timestamps = [int((datetime.now() - timedelta(days=x)).timestamp()) for x in range(180)]
            base_degradation = config["degradation_rate"] * 180 / 365 * 100
            soh_history = config["base_soh"] + np.linspace(base_degradation, 0, 180) + np.random.normal(0, 0.5, 180)
            pd.DataFrame({'timestamp': sorted(timestamps), 'soh': soh_history}).to_csv(history_file, index=False)
        
        history_df = pd.read_csv(history_file)
        lr_model = LinearRegression().fit(history_df[['timestamp']], history_df['soh'])
        
        battery_states[battery_id] = {
            "config": config,
            "history_df": history_df,
            "lr_model": lr_model,
            "history_buffer": [],
            "battery_cells": [{"id": i, "voltage": config["base_voltage"], "is_faulty": False, "is_balancing": False, "temperature": config["base_temp"]} for i in range(config["num_cells"])],
            "pack_soh": config["base_soh"],
            "fault_introduced": False,
            "faulty_cell_index": -1,
            "last_fault_check_time": time.time()
        }
    
    battery_state = battery_states[battery_id]
    
    # Update cell voltages
    for cell in battery_state["battery_cells"]:
        if not cell["is_faulty"]:
            voltage_variation = random.uniform(-0.002, 0.002)
            cell["voltage"] = round(max(3.0, min(4.2, cell["voltage"] + voltage_variation)), 3)
        cell["temperature"] = round(config["base_temp"] + random.uniform(-2, 2), 1)
    
    # Introduce faults based on probability
    if (not battery_state["fault_introduced"] and 
        time.time() - battery_state["last_fault_check_time"] > 30 and 
        random.random() < config["fault_probability"] / 100):
        
        battery_state["faulty_cell_index"] = random.randint(0, config["num_cells"] - 1)
        battery_state["battery_cells"][battery_state["faulty_cell_index"]].update({
            "is_faulty": True, 
            "voltage": config["base_voltage"] - 0.5
        })
        battery_state["fault_introduced"] = True
    
    # Calculate averages and predictions
    avg_voltage = sum(c['voltage'] for c in battery_state["battery_cells"]) / config["num_cells"]
    avg_temp = sum(c['temperature'] for c in battery_state["battery_cells"]) / config["num_cells"]
    
    predicted_soh = get_ai_prediction([avg_voltage, random.uniform(15, 25), avg_temp, battery_state["pack_soh"]], battery_state)
    if predicted_soh: 
        battery_state["pack_soh"] = predicted_soh
    
    # Apply gradual degradation
    battery_state["pack_soh"] -= config["degradation_rate"] / 365 / 24 / 60
    
    return {
        "pack_summary": {
            "total_voltage": float(round(sum(c["voltage"] for c in battery_state["battery_cells"]), 2)),
            "avg_temperature": float(round(avg_temp, 2)),
            "state_of_health": float(round(battery_state["pack_soh"], 2)),
            "alert": f"Critical Fault: Cell #{battery_state['faulty_cell_index']} is malfunctioning!" if battery_state["fault_introduced"] else "None",
            "battery_name": config["name"],
            "battery_id": battery.id
        },
        "cells": battery_state["battery_cells"],
        "long_term_forecast": get_long_term_forecast(battery_state),
        "model_performance": model_performance
    }

def simulate_default_battery_data():
    """Legacy simulation function for backward compatibility"""
    global pack_soh, fault_introduced, faulty_cell_index, last_fault_check_time
    for cell in battery_cells:
        if not cell["is_faulty"]: 
            cell["voltage"] = round(max(3.0, min(4.2, cell["voltage"] + random.uniform(-0.001, 0.001))), 3)
    
    if not fault_introduced and time.time() - last_fault_check_time > 20:
        faulty_cell_index = random.randint(0, NUM_CELLS - 1)
        battery_cells[faulty_cell_index].update({"is_faulty": True, "voltage": 3.6})
        fault_introduced = True
        
    avg_voltage = sum(c['voltage'] for c in battery_cells) / NUM_CELLS
    predicted_soh = get_ai_prediction([avg_voltage, random.uniform(15, 25), 25.5, pack_soh])
    if predicted_soh: pack_soh = predicted_soh
    
    return {
        "pack_summary": {
            "total_voltage": float(round(sum(c["voltage"] for c in battery_cells), 2)),
            "avg_temperature": float(round(random.uniform(25.0, 26.0), 2)),
            "state_of_health": float(round(pack_soh, 2)),
            "alert": f"Critical Fault: Cell #{faulty_cell_index} is malfunctioning!" if fault_introduced else "None",
        },
        "cells": battery_cells,
        "long_term_forecast": get_long_term_forecast(),
        "model_performance": model_performance
    }

def simulate_specific_battery_data(battery_id):
    """Simulate data for a specific battery configuration"""
    battery_state = initialize_battery_state(battery_id)
    config = battery_state["config"]
    
    # Update cell voltages
    for cell in battery_state["battery_cells"]:
        if not cell["is_faulty"]:
            voltage_variation = random.uniform(-0.002, 0.002)
            cell["voltage"] = round(max(3.0, min(4.2, cell["voltage"] + voltage_variation)), 3)
        cell["temperature"] = round(config["base_temp"] + random.uniform(-2, 2), 1)
    
    # Introduce faults based on probability
    if (not battery_state["fault_introduced"] and 
        time.time() - battery_state["last_fault_check_time"] > 30 and 
        random.random() < config["fault_probability"] / 100):
        
        battery_state["faulty_cell_index"] = random.randint(0, config["num_cells"] - 1)
        battery_state["battery_cells"][battery_state["faulty_cell_index"]].update({
            "is_faulty": True, 
            "voltage": config["base_voltage"] - 0.5
        })
        battery_state["fault_introduced"] = True
    
    # Calculate averages and predictions
    avg_voltage = sum(c['voltage'] for c in battery_state["battery_cells"]) / config["num_cells"]
    avg_temp = sum(c['temperature'] for c in battery_state["battery_cells"]) / config["num_cells"]
    
    predicted_soh = get_ai_prediction([avg_voltage, random.uniform(15, 25), avg_temp, battery_state["pack_soh"]], battery_state)
    if predicted_soh: 
        battery_state["pack_soh"] = predicted_soh
    
    # Apply gradual degradation
    battery_state["pack_soh"] -= config["degradation_rate"] / 365 / 24 / 60  # Per minute degradation
    
    return {
        "pack_summary": {
            "total_voltage": float(round(sum(c["voltage"] for c in battery_state["battery_cells"]), 2)),
            "avg_temperature": float(round(avg_temp, 2)),
            "state_of_health": float(round(battery_state["pack_soh"], 2)),
            "alert": f"Critical Fault: Cell #{battery_state['faulty_cell_index']} is malfunctioning!" if battery_state["fault_introduced"] else "None",
            "battery_name": config["name"],
            "battery_id": battery_id
        },
        "cells": battery_state["battery_cells"],
        "long_term_forecast": get_long_term_forecast(battery_state),
        "model_performance": model_performance
    }

# --- Authentication Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = 'remember' in request.form
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash('Logged in successfully!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Validation
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        # Create new user
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# --- Battery Management Routes ---
@app.route('/')
def home():
    """Redirect to login page"""
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard after login"""
    return render_template('dashboard.html')

@app.route('/battery-selection')
@login_required
def battery_selection(): 
    # Get user's custom batteries
    user_batteries = Battery.query.filter_by(user_id=current_user.id).order_by(Battery.created_at.desc()).limit(5).all()
    return render_template('battery_selection.html', user_batteries=user_batteries)

@app.route('/add-battery', methods=['GET', 'POST'])
@login_required
def add_battery():
    if request.method == 'POST':
        try:
            # Get form data
            battery = Battery(
                name=request.form['name'],
                battery_type=request.form['battery_type'],
                num_cells=int(request.form['num_cells']),
                base_voltage=float(request.form['base_voltage']),
                base_soh=float(request.form['base_soh']),
                base_temp=float(request.form['base_temp']),
                degradation_rate=float(request.form['degradation_rate']),
                fault_probability=float(request.form['fault_probability']),
                capacity_ah=float(request.form['capacity_ah']) if request.form['capacity_ah'] else None,
                max_charge_rate=float(request.form['max_charge_rate']) if request.form['max_charge_rate'] else None,
                max_discharge_rate=float(request.form['max_discharge_rate']) if request.form['max_discharge_rate'] else None,
                operating_temp_min=float(request.form['operating_temp_min']) if request.form['operating_temp_min'] else None,
                operating_temp_max=float(request.form['operating_temp_max']) if request.form['operating_temp_max'] else None,
                description=request.form['description'] if request.form['description'] else None,
                user_id=current_user.id
            )
            
            db.session.add(battery)
            db.session.commit()
            
            flash(f'Battery "{battery.name}" added successfully!', 'success')
            return redirect(url_for('add_battery'))
            
        except Exception as e:
            flash(f'Error adding battery: {str(e)}', 'error')
    
    return render_template('add_battery.html')

@app.route('/battery/<int:battery_id>')
@login_required
def battery_dashboard(battery_id):
    # Check if it's a predefined battery or user's custom battery
    if battery_id in BATTERY_CONFIGS:
        return render_template('index.html', battery_id=battery_id, battery_name=BATTERY_CONFIGS[battery_id]["name"])
    else:
        # Check if it's user's custom battery
        battery = Battery.query.filter_by(id=battery_id, user_id=current_user.id).first()
        if not battery:
            flash('Battery not found or access denied', 'error')
            return redirect(url_for('battery_selection'))
        return render_template('index.html', battery_id=battery_id, battery_name=battery.name, is_custom=True)

@app.route('/dashboard')
@login_required
def legacy_dashboard(): 
    return render_template('index.html')

@app.route('/upload-battery-files', methods=['POST'])
@login_required
def upload_battery_files():
    """Handle file upload and create battery from uploaded data"""
    try:
        print(f"Upload request from user: {current_user.username}")
        if 'battery_files' not in request.files:
            return jsonify({'success': False, 'message': 'No files uploaded'})
        
        files = request.files.getlist('battery_files')
        if not files or files[0].filename == '':
            return jsonify({'success': False, 'message': 'No files selected'})
        
        created_batteries = []
        
        for file in files:
            print(f"Processing file: {file.filename}")
            if file and allowed_file(file.filename):
                # Secure the filename
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                print(f"Saving file to: {file_path}")
                
                # Save the file
                file.save(file_path)
                
                # Parse the file and extract battery data
                battery_data = parse_battery_file(file_path, filename)
                
                # Create battery in database
                battery = Battery(
                    name=battery_data['name'],
                    battery_type=battery_data['battery_type'],
                    num_cells=battery_data['num_cells'],
                    base_voltage=battery_data['base_voltage'],
                    base_soh=battery_data['base_soh'],
                    base_temp=battery_data['base_temp'],
                    degradation_rate=battery_data['degradation_rate'],
                    fault_probability=battery_data['fault_probability'],
                    capacity_ah=battery_data['capacity_ah'],
                    max_charge_rate=battery_data['max_charge_rate'],
                    max_discharge_rate=battery_data['max_discharge_rate'],
                    operating_temp_min=battery_data['operating_temp_min'],
                    operating_temp_max=battery_data['operating_temp_max'],
                    description=battery_data['description'],
                    user_id=current_user.id
                )
                
                db.session.add(battery)
                db.session.commit()
                
                created_batteries.append(battery.id)
                
                # Clean up uploaded file
                os.remove(file_path)
        
        if created_batteries:
            # Return the first created battery ID for redirection
            return jsonify({
                'success': True, 
                'message': f'Successfully created {len(created_batteries)} battery(s)',
                'battery_id': created_batteries[0],
                'battery_ids': created_batteries
            })
        else:
            return jsonify({'success': False, 'message': 'No valid files processed'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error processing files: {str(e)}'})

# --- API Routes ---
@app.route('/api/live-data')
@login_required
def get_live_data(): 
    return jsonify(simulate_battery_data())

@app.route('/api/live-data/<int:battery_id>')
@login_required
def get_battery_live_data(battery_id):
    if battery_id in BATTERY_CONFIGS:
        return jsonify(simulate_battery_data(battery_id))
    else:
        # Check if it's user's custom battery
        battery = Battery.query.filter_by(id=battery_id, user_id=current_user.id).first()
        if not battery:
            return jsonify({"error": "Battery not found"}), 404
        return jsonify(simulate_custom_battery_data(battery))

@app.route('/api/user-batteries')
@login_required
def get_user_batteries():
    """Get all batteries for the current user"""
    try:
        batteries = Battery.query.filter_by(user_id=current_user.id).order_by(Battery.created_at.desc()).all()
        
        battery_list = []
        for battery in batteries:
            battery_list.append({
                'id': battery.id,
                'name': battery.name,
                'battery_type': battery.battery_type,
                'num_cells': battery.num_cells,
                'base_voltage': battery.base_voltage,
                'base_soh': battery.base_soh,
                'base_temp': battery.base_temp,
                'created_at': battery.created_at.isoformat(),
                'description': battery.description
            })
        
        return jsonify({
            'success': True,
            'batteries': battery_list,
            'count': len(battery_list)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error fetching batteries: {str(e)}'}), 500

@app.route('/api/battery/<int:battery_id>', methods=['DELETE'])
@login_required
def delete_battery(battery_id):
    battery = Battery.query.filter_by(id=battery_id, user_id=current_user.id).first()
    if not battery:
        return jsonify({"success": False, "message": "Battery not found"}), 404
    
    try:
        db.session.delete(battery)
        db.session.commit()
        return jsonify({"success": True, "message": "Battery deleted successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    if model:
        app.run(host='0.0.0.0', port=5002, debug=False)
    else:
        print("\n--- Cannot start server: AI model is not loaded. ---")