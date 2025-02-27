import os
import json
from flask import Flask, render_template, request, Response


app = Flask(__name__)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
labels_file = os.path.join(STATIC_DIR, "labels.json")


if not os.path.exists(labels_file):
    with open(labels_file, "w") as fp:
        json.dump({}, fp)


@app.route("/")
def index():
    images_dir = os.path.join(STATIC_DIR, "img")
    files = []
    for f in os.listdir(images_dir):
        if os.path.isfile(os.path.join(images_dir, f)):
            if os.path.splitext(f)[-1] in [".jpg", ".png"]:
                files.append(f)
    files.sort()

    with open(labels_file, "r") as fp:
        labels = json.load(fp)
    return render_template("index.html", files=files, labels=labels)


@app.route("/save", methods=["POST"])
def save():
    labels = dict(request.form)
    with open(labels_file, "w") as fp:
        json.dump(labels, fp)
    return Response(status=201)


if __name__ == "__main__":
    app.run(debug=True)
