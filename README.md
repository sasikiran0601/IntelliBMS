# IntelliBMS - Multi-Battery Management System with Authentication

## Overview
IntelliBMS is an AI-powered battery management system with user authentication that supports monitoring multiple battery packs. Users can create accounts, add custom battery configurations, and monitor both predefined and custom battery packs with different characteristics and configurations.

## New Features

### 🔐 User Authentication System
- **Login/Registration**: Secure user authentication with password hashing
- **Session Management**: Persistent login sessions with remember me option
- **User Isolation**: Each user can only access their own custom batteries
- **Default Credentials**: admin/admin123 for quick testing

### 🔋 Dynamic Battery Management
- **Add Battery Page**: Comprehensive form to add custom battery configurations
- **Real-time Validation**: Form validation with helpful guidance text
- **Battery Library**: View and manage all your custom battery packs
- **Delete Functionality**: Remove unwanted battery configurations

### 📊 Enhanced Battery Selection
- **Predefined Batteries**: 5 pre-configured battery packs for immediate use
- **Custom Batteries**: Your personally added battery configurations
- **Visual Battery Cards**: Each battery shows real-time status, SOH, voltage, and health indicators
- **Interactive Navigation**: Click any battery to view its detailed monitoring page

### Supported Battery Packs

1. **Battery 1 - Tesla Model S Pack**
   - 48 cells, 4.1V base voltage
   - High performance, low degradation rate
   - SOH: 98.5%

2. **Battery 2 - BMW i3 Pack**
   - 40 cells, 3.9V base voltage
   - Moderate degradation, higher fault probability
   - SOH: 85.2%

3. **Battery 3 - Nissan Leaf Pack**
   - 44 cells, 4.0V base voltage
   - Good performance, moderate degradation
   - SOH: 92.8%

4. **Battery 4 - Chevy Bolt Pack**
   - 36 cells, 3.8V base voltage
   - Higher degradation, critical status
   - SOH: 76.3%

5. **Battery 5 - Audi e-tron Pack**
   - 52 cells, 3.95V base voltage
   - Moderate performance and degradation
   - SOH: 89.7%

## URL Structure

### Authentication
- `/login` - User login page
- `/register` - User registration page
- `/logout` - Logout endpoint

### Battery Management
- `/` - Battery selection page (requires login)
- `/add-battery` - Add new battery configuration page
- `/battery/<id>` - Individual battery monitoring dashboard
- `/dashboard` - Legacy dashboard (default battery)

### Predefined Batteries
- `/battery/1` - Tesla Model S Pack monitoring
- `/battery/2` - BMW i3 Pack monitoring
- `/battery/3` - Nissan Leaf Pack monitoring
- `/battery/4` - Chevy Bolt Pack monitoring
- `/battery/5` - Audi e-tron Pack monitoring

## API Endpoints

- `/api/live-data` - Default battery data
- `/api/live-data/1` - Tesla Model S Pack data
- `/api/live-data/2` - BMW i3 Pack data
- `/api/live-data/3` - Nissan Leaf Pack data
- `/api/live-data/4` - Chevy Bolt Pack data
- `/api/live-data/5` - Audi e-tron Pack data

## Features per Battery

Each battery pack has:
- **Unique Cell Configuration**: Different number of cells and voltage characteristics
- **Individual SOH Tracking**: Separate degradation patterns and history
- **Custom Fault Simulation**: Different fault probabilities based on battery type
- **Temperature Monitoring**: Battery-specific temperature ranges
- **Long-term Forecasting**: Individual prediction models for each pack

## How to Use

1. **Start the Application**:
   ```bash
   python app.py
   ```

2. **Access the Interface**:
   - Open your browser to `http://localhost:5002`
   - You'll see the battery selection page

3. **Monitor Individual Batteries**:
   - Click on any battery card to view detailed monitoring
   - Each battery shows real-time cell data, SOH trends, and alerts
   - Use the "Back to Battery Selection" button to return to the main page

## Technical Implementation

- **Flask Backend**: Handles routing and data simulation for multiple batteries
- **Battery State Management**: Each battery maintains separate state and history
- **Dynamic Data Generation**: Real-time simulation with battery-specific characteristics
- **Responsive UI**: Modern interface with dark/light theme support
- **AI Integration**: Continues to use the trained SOH prediction model

## File Structure

```
IntelliBMS/
├── app.py                          # Main Flask application with multi-battery support
├── templates/
│   ├── battery_selection.html      # New battery selection page
│   └── index.html                  # Updated monitoring dashboard
├── generate_and_train.py           # AI model training
├── soh_model.h5                    # Trained AI model
├── soh_history_battery_*.csv       # Individual battery history files
└── test_batteries.py               # Battery functionality tests
```

## Navigation Flow

```
Battery Selection Page (/)
    ↓ (click battery)
Individual Battery Dashboard (/battery/X)
    ↓ (back button)
Battery Selection Page (/)
```

Each battery maintains its own state, degradation patterns, and fault conditions, providing a realistic multi-battery monitoring experience.
