import datetime
import calendar
import config
import os
import yaml
from flask import Flask, render_template, jsonify, redirect, url_for, request, session, flash
from apscheduler.schedulers.background import BackgroundScheduler

import holter
import move_holters
from data import get_daily_metadata


app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Change this to a random secret key
scheduler = BackgroundScheduler()

# Load config including users
with open("config.yaml", 'r') as file:
    CONFIG = yaml.safe_load(file)


@app.before_request
def check_config_access():
    try:
        config.get()
    except Exception as e:
        return render_template("config_error.html", error_message=str(e)), 500


# ------ Authentication operations ------

def require_auth(is_admin=False):
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session:
                return redirect(url_for('login'))
            if is_admin and not session.get('is_admin', False):
                return render_template("404.html"), 404
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_user(username):
    for user in CONFIG.get('users', []):
        if user['username'] == username:
            return user
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']

        user = get_user(username)
        if user and user['password'] == password:
            session['username'] = username
            session['is_admin'] = user['is_admin']
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error='Invalid username or password')

    return render_template('login.html')


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

# ------ Statistics ------

class Cell:
    def __init__(self, value, link=None):
        self.value = value
        self.link = link

    def __str__(self):
        return str(self.value)


@app.route("/<int:year>/<int:month>/")
@require_auth(is_admin=False)
def monthly_stats(year, month):
    # Daily stats for given month and year
    daily_metadata = get_daily_metadata(year=year, month=month)

    # Initialize dates as all possible days (integers) of the current month
    num_days = calendar.monthrange(year, month)[1]
    headers = ["Doctor \\ Date"] + list(range(1, num_days + 1)) + ["Total"]

    data = []
    summary_row = ["Daily total"] + [0] * num_days
    for doctor, doctor_metadata in daily_metadata.items():
        row = [doctor]
        row_count = 0
        for day in range(1, num_days + 1):
            date_ = datetime.date(year, month, day)
            count = doctor_metadata.get(date_, 0)
            row_count += count
            link = url_for('daily_doctor_stats', year=year, month=month, day=day, doctor=doctor)
            row.append(Cell(count, link=link))
            summary_row[day] += count
        row.append(row_count)
        data.append(row)
    summary_row = summary_row[:1] + [
        Cell(value, link=url_for('daily_stats', year=year, month=month, day=day))
        for day, value in zip(range(1, num_days + 1), summary_row[1:])
    ]
    summary_row.append(sum([cell.value for cell in summary_row[1:]]))
    data.append(summary_row)

    previous_year = year - 1 if month == 1 else year
    previous_month = 12 if month == 1 else month - 1
    previous_month_link = url_for('monthly_stats', year=previous_year, month=previous_month)

    next_year = year + 1 if month == 12 else year
    next_month = 1 if month == 12 else month + 1
    next_month_link = url_for('monthly_stats', year=next_year, month=next_month)

    return render_template(
        "stats.html",
        name=f"Stats for {month:02d}/{year}",
        headers=headers,
        data=data,
        previous_month_link=previous_month_link,
        next_month_link=next_month_link,
    )


def _get_daily_data(year, month, day, doctor):
    path = os.path.join(
        config.get()["output_path"], doctor, '{:02d}.{:02d}.{}'.format(day, month, year)
    )
    data = []
    if os.path.exists(path):
        file_names = holter.get_in_folder(path)
        for file_name in file_names:
            patient_data = holter.get_patient_data(file_name)
            row = [
                os.path.basename(file_name),
                patient_data['name'],
            ]
            data.append(row)
    return data


@app.route("/<int:year>/<int:month>/<int:day>/<string:doctor>/")
@require_auth(is_admin=False)
def daily_doctor_stats(year, month, day, doctor):
    data = _get_daily_data(year, month, day, doctor)
    headers = ["File Name", "Name"]
    name = f"Stats for {doctor} on {day:02d}.{month:02d}.{year}"
    return render_template(
        "daily_stats.html",
        name=name,
        headers=headers,
        data=data,
    )

@app.route("/<int:year>/<int:month>/<int:day>/")
@require_auth(is_admin=False)
def daily_stats(year, month, day):
    doctors = get_daily_metadata(year=year, month=month).keys()
    data = []
    for doctor in doctors:
        doctor_data = _get_daily_data(year, month, day, doctor)
        doctor_data = [[doctor] + row for row in doctor_data]
        data += doctor_data
    headers = ["Doctor", "File Name", "Name"]
    name = f"Stats for {day:02d}.{month:02d}.{year}"
    return render_template(
        "daily_stats.html",
        name=name,
        headers=headers,
        data=data,
    )


@app.route("/stats/")
@require_auth(is_admin=False)
def stats():
    now = datetime.datetime.now()
    return redirect(url_for('monthly_stats', year=now.year, month=now.month))

# ------ Config ------

@require_auth(is_admin=False)
def edit_config():
    return render_template("edit_config.html", config=config.get())

@app.route("/")
@require_auth(is_admin=False)
def home():
    return render_template("config.html", config=config.get(), is_admin=session['is_admin'])


# ------ Doctor Management ------

def get_doctor_by_name(name):
    """Get doctor configuration by name."""
    current_config = config.get()
    for doctor in current_config.get('doctors', []):
        if doctor['name'] == name:
            return doctor
    return None


def format_yaml_config(config_data):
    """Format YAML config with proper indentation and spacing like example_config.yaml."""
    lines = []

    # Add basic config
    lines.append(f'input_path: "{config_data["input_path"]}"  # тут мають бути файли з розширенням .zhr')
    lines.append(f'output_path: "{config_data["output_path"]}"  # тут будуть створюватися папки лікарів')
    lines.append(f'rejected_path: "{config_data["rejected_path"]}"  # тут будуть файли дуплікати (імʼя яких є вже в папці output_path)')
    lines.append(f'evening_hours: {config_data["evening_hours"]} # години до кінця дня, після яких холтери будуть переноситись на наступний день')
    lines.append('')
    lines.append('doctors:')

    # Add doctors with proper formatting and spacing
    for i, doctor in enumerate(config_data.get('doctors', [])):
        if i > 0:  # Add empty line between doctors
            lines.append('')

        lines.append(f'  - name: "{doctor["name"]}"  # ім\'я лікаря')
        lines.append(f'    folder_name: "{doctor["folder_name"]}"  # назва папки, яка буде створена в output_path')
        lines.append(f'    limit: {doctor["limit"]}  # склільки максимум холтерів на день буде передано лікарю, -1 - без ліміту')

        # Skip stations
        if doctor.get('skip_stations'):
            lines.append('    skip_stations:  # станції(2 перші літери назви холтера), які не потрібно передавати лікарю')
            for station in doctor['skip_stations']:
                lines.append(f'      - "{station}"')

        # Station limits
        if doctor.get('stations_limits'):
            lines.append('    stations_limits:  # ліміти по станціям (максисмум холтерів, які можна передати лікарю)')
            for station, limit in doctor['stations_limits'].items():
                lines.append(f'      "{station}": {limit}')

        lines.append(f'    is_working: {str(doctor["is_working"]).lower()}  # чи працює лікар взагалі, якщо значення false, то лікарь не буде отримувати холтери')

        # Days off
        if doctor.get('days_off'):
            lines.append('    days_off:  # дні відпочинку, лікарь не працює в ці дні')
            for day_off in doctor['days_off']:
                lines.append(f'      - "{day_off}"')
        else:
            lines.append('    days_off: null')

    lines.append('')
    lines.append('users:  # користувачі які мають доступ до системи, адмін може редагувати конфіг')

    # Add users
    for user in config_data.get('users', []):
        lines.append(f'  - username: "{user["username"]}"')
        lines.append(f'    password: "{user["password"]}"')
        lines.append(f'    is_admin: {str(user["is_admin"]).lower()}')

    return '\n'.join(lines) + '\n'


def update_doctor_config(doctor_name, updated_data):
    """Update doctor configuration in config.yaml file."""
    try:
        # Read current config from file
        with open("config.yaml", 'r', encoding='utf-8') as file:
            current_config = yaml.safe_load(file)

        # Find and update the doctor
        doctor_found = False
        for i, doctor in enumerate(current_config.get('doctors', [])):
            if doctor['name'] == doctor_name:
                # Update the doctor with new data, preserving name and folder_name
                current_config['doctors'][i].update({
                    'limit': updated_data['limit'],
                    'skip_stations': updated_data['skip_stations'],
                    'stations_limits': updated_data['stations_limits'],
                    'is_working': updated_data['is_working'],
                    'days_off': updated_data['days_off']
                })
                doctor_found = True
                break

        if not doctor_found:
            raise ValueError(f"Doctor '{doctor_name}' not found in configuration")

        # Write updated config back to file with proper formatting
        formatted_yaml = format_yaml_config(current_config)
        with open("config.yaml", 'w', encoding='utf-8') as file:
            file.write(formatted_yaml)

        config.reset()

        return True
    except Exception as e:
        print(f"Error updating doctor config: {e}")
        return False


@app.route("/edit_doctor/<string:doctor_name>", methods=["GET", "POST"])
@require_auth(is_admin=True)
def edit_doctor(doctor_name):
    """Edit doctor configuration."""
    doctor = get_doctor_by_name(doctor_name)
    if not doctor:
        return render_template('404.html'), 404

    if request.method == "POST":
        try:
            # Parse form data
            limit = int(request.form.get('limit', -1))
            if limit < -1:
                raise ValueError("Limit must be -1 or greater")

            # Parse skip stations
            skip_stations = []
            for station in request.form.getlist('skip_stations[]'):
                station = station.strip().upper()
                if station:
                    if len(station) != 2 or not station.isalpha():
                        raise ValueError("Skip stations must be exactly 2 letters")
                    skip_stations.append(station)

            # Parse stations limits
            stations_limits = {}
            limit_keys = request.form.getlist('stations_limits_keys[]')
            limit_values = request.form.getlist('stations_limits_values[]')

            for key, value in zip(limit_keys, limit_values):
                key = key.strip().upper()
                if key and value:
                    if len(key) != 2 or not key.isalpha():
                        raise ValueError("Station codes must be exactly 2 letters")
                    try:
                        value = int(value)
                        if value < 1:
                            raise ValueError("Station limits must be positive integers")
                        stations_limits[key] = value
                    except ValueError:
                        raise ValueError("Station limits must be positive integers")

            # Parse is_working checkbox
            is_working = 'is_working' in request.form

            # Parse days off
            days_off = []
            for date_str in request.form.getlist('days_off[]'):
                date_str = date_str.strip()
                if date_str:
                    try:
                        # Validate date format and convert to DD.MM.YYYY
                        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                        formatted_date = date_obj.strftime('%d.%m.%Y')
                        days_off.append(formatted_date)
                    except ValueError:
                        raise ValueError("Invalid date format")

            # Prepare updated data
            updated_data = {
                'limit': limit,
                'skip_stations': skip_stations if skip_stations else None,
                'stations_limits': stations_limits if stations_limits else None,
                'is_working': is_working,
                'days_off': days_off if days_off else None
            }

            # Update configuration
            if update_doctor_config(doctor_name, updated_data):
                # Get the updated doctor data and convert dates for display
                updated_doctor = get_doctor_by_name(doctor_name)
                doctor_copy = updated_doctor.copy()
                if doctor_copy.get('days_off'):
                    converted_days = []
                    for day_off in doctor_copy['days_off']:
                        try:
                            # Parse DD.MM.YYYY format and convert to YYYY-MM-DD
                            date_obj = datetime.datetime.strptime(day_off, '%d.%m.%Y')
                            converted_days.append(date_obj.strftime('%Y-%m-%d'))
                        except ValueError:
                            # If parsing fails, keep original format
                            converted_days.append(day_off)
                    doctor_copy['days_off'] = converted_days

                return render_template('edit_doctor.html',
                                     doctor=doctor_copy,
                                     success="Doctor configuration updated successfully!")
            else:
                return render_template('edit_doctor.html',
                                     doctor=doctor,
                                     error="Failed to update doctor configuration.")

        except ValueError as e:
            return render_template('edit_doctor.html',
                                 doctor=doctor,
                                 error=str(e))
        except Exception as e:
            return render_template('edit_doctor.html',
                                 doctor=doctor,
                                 error=f"An unexpected error occurred: {str(e)}")

    # GET request - show form
    # Convert days_off from DD.MM.YYYY to YYYY-MM-DD for HTML date inputs
    doctor_copy = doctor.copy()
    if doctor_copy.get('days_off'):
        converted_days = []
        for day_off in doctor_copy['days_off']:
            try:
                # Parse DD.MM.YYYY format and convert to YYYY-MM-DD
                date_obj = datetime.datetime.strptime(day_off, '%d.%m.%Y')
                converted_days.append(date_obj.strftime('%Y-%m-%d'))
            except ValueError:
                # If parsing fails, keep original format
                converted_days.append(day_off)
        doctor_copy['days_off'] = converted_days

    return render_template('edit_doctor.html', doctor=doctor_copy)


def _distribute_holters_task():
    move_holters.distribute_holters()


def _start_scheduler():
    if not scheduler.running:
        scheduler.add_job(
            func=_distribute_holters_task,
            trigger="interval",
            seconds=5,
            id="distribute-holters-task",
            replace_existing=True,
        )
        scheduler.start()
        print("Scheduler started.")


@app.route("/scheduler/start", methods=["POST"])
@require_auth(is_admin=True)
def scheduler_start():
    if not scheduler.get_job("distribute-holters-task"):
        scheduler.add_job(
            func=_distribute_holters_task,
            trigger="interval",
            seconds=5,
            id="distribute-holters-task",
            replace_existing=True,
        )
        print("Scheduler job added.")
    return jsonify({"status": "Job is running ✅"})


@app.route("/scheduler/stop", methods=["POST"])
@require_auth(is_admin=True)
def scheduler_stop():
    job = scheduler.get_job("distribute-holters-task")
    if job:
        scheduler.remove_job("distribute-holters-task")
        print("Scheduler job removed.")
    return jsonify({"status": "Job is not running ❌"})


@app.route("/scheduler/status", methods=["GET"])
@require_auth(is_admin=True)
def scheduler_status():
    job = scheduler.get_job("distribute-holters-task")
    if job:
        return jsonify({"status": "Job is running ✅"})
    else:
        return jsonify({"status": "Job is not running ❌"})


# ------ Error Handlers ------

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors with custom template showing ASCII doctor."""
    return render_template('404.html'), 404


if __name__ == "__main__":
    _start_scheduler()
    app.run(debug=True)  # PAVEL-TODO: remove debug=True for production
