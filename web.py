import yaml
import datetime
import calendar
from flask import Flask, render_template, request, jsonify, redirect, url_for

from data import get_daily_metadata


app = Flask(__name__)


@app.route("/<int:year>/<int:month>/")
def monthly_stats(year, month):
    # Daily stats for given month and year
    daily_metadata = get_daily_metadata(year=year, month=month)

    # Initialize dates as all possible days (integers) of the current month
    num_days = calendar.monthrange(year, month)[1]
    headers = ["Doctor \\ Date"] + list(range(1, num_days + 1))

    data = []
    for doctor, doctor_metadata in daily_metadata.items():
        row = [doctor]
        for day in range(1, num_days + 1):
            date_ = datetime.date(year, month, day)
            row.append(doctor_metadata.get(date_, 0))
        data.append(row)

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


@app.route("/<int:year>/<int:month>/<int:day>/<string:doctor>/")
def daily_stats(year, month, day, doctor):
    pass


@app.route("/")
def home():
    now = datetime.datetime.now()
    return redirect(url_for('monthly_stats', year=now.year, month=now.month))


@app.route("/edit-config")
def edit_config():
    return render_template("edit_config.html")


@app.route("/load", methods=["GET"])
def load_yaml():
    with open("config.yaml", "r", encoding="utf-8") as f:
        data = f.read()
    return jsonify({"content": data})


@app.route("/save", methods=["POST"])
def save_yaml():
    data = request.json.get("content", "")
    try:
        yaml.safe_load(data)  # Validate YAML format
        with open("config.yaml", "w", encoding="utf-8") as f:
            f.write(data)
        return jsonify({"success": True})
    except yaml.YAMLError:
        return jsonify({"success": False, "error": "Invalid YAML format"}), 400


if __name__ == "__main__":
    app.run(debug=True)
