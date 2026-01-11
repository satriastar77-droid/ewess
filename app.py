from flask import Flask, render_template
from flask_cors import CORS

from controllers.realtime import realtime_api
from controllers.logs import logs_api
from controllers.stats import stats_api
from controllers.event import event_api

app = Flask(__name__)
CORS(app)

app.register_blueprint(realtime_api)
app.register_blueprint(logs_api)
app.register_blueprint(stats_api)
app.register_blueprint(event_api)

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/api")
def api_status():
    return "EWESS Backend Berjalan"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
