import os
from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
  return "Halo, web saya sudah online di Render!"


if __name__ == "__main__":
  # Render memerlukan port dinamis dari environment system
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)