import yaml
from flask import Flask, render_template_string, render_template, request, jsonify

from data import get_daily_metadata

app = Flask(__name__)


HEAD = """
<head>
    <title>Flask Table</title>
    <style>
        table { width: 50%%; border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid black; padding: 10px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
"""


def _as_page(body: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
        {HEAD}
        <body>
            <a href="/">Home</a> | <a href="/edit-config">Edit config</a>
            {body}
        </body>
    </html>
    """


def generate_html_table(name: str, headers: list, data: list[list]) -> str:
    """ Generate HTML table from headers and rows. """
    html = """
    <h1>{{ name }}</h1>
    <table>
        <tr>
            {% for cell in headers %}
            <th>{{ cell }}</th>
            {% endfor %}
        </tr>
        {% for row in data %}
        <tr>
            {% for cell in row %}
            <td>{{ cell }}</td>
            {% endfor %}
        </tr>
        {% endfor %}
    </table>
    """
    return render_template_string(html, name=name, headers=headers, data=data)


@app.route("/")
def home():
    # Daily stats
    daily_metadata = get_daily_metadata()
    doctors = list(daily_metadata.keys())
    headers = ["Date \ Doctor"] + doctors
    dates = set()
    for doctor in doctors:
        dates.update(daily_metadata[doctor].keys())
    dates = sorted(list(dates), reverse=True)
    data = []
    for date_ in dates:
        row = [date_]
        for doctor in doctors:
            row.append(daily_metadata[doctor].get(date_, 0))
        data.append(row)
    daily_table = generate_html_table("Daily stats", headers, data)

    return _as_page(daily_table)


YAML_FILE = "config.yaml"  # Path to your YAML file


@app.route("/edit-config")
def edit_config():
    return render_template("edit_config.html")


@app.route("/load", methods=["GET"])
def load_yaml():
    with open(YAML_FILE, "r", encoding="utf-8") as f:
        data = f.read()
    return jsonify({"content": data})


@app.route("/save", methods=["POST"])
def save_yaml():
    data = request.json.get("content", "")
    try:
        yaml.safe_load(data)  # Validate YAML format
        with open(YAML_FILE, "w", encoding="utf-8") as f:
            f.write(data)
        return jsonify({"success": True})
    except yaml.YAMLError:
        return jsonify({"success": False, "error": "Invalid YAML format"}), 400


if __name__ == "__main__":
    app.run(debug=True)
