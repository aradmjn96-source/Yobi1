from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify(
        app="Yobi1",
        version="0.1.0",
        status="Yobi1 Server is running!"
    )

@app.route("/health")
def health():
    return jsonify(ok=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
