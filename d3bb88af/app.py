"""Foura Goalkeeper Coach — Flask application entry point."""

import json
import os
import socket
import uuid
from datetime import date, datetime
from urllib.parse import urlparse

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, url_for)

import scoring
from models import STAT_FIELDS, Club, Evaluation, Goalkeeper, Match, init_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")

LANGS = ("fr", "ar")
DEFAULT_LANG = "fr"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg"}
APP_NAME = "FOURA GOALKEEPER COACH"

app = Flask(__name__)
app.secret_key = "foura-goalkeeper-coach"
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

TRANSLATIONS = {}
for _code in LANGS:
    with open(os.path.join(BASE_DIR, "translations", f"{_code}.json"), encoding="utf-8") as fh:
        TRANSLATIONS[_code] = json.load(fh)

init_db()


def get_lang():
    lang = request.args.get("lang")
    if lang in LANGS:
        return lang
    lang = request.cookies.get("lang")
    return lang if lang in LANGS else DEFAULT_LANG


def translate(key, lang=None):
    lang = lang or get_lang()
    return TRANSLATIONS.get(lang, {}).get(key) or TRANSLATIONS[DEFAULT_LANG].get(key, key)


@app.context_processor
def inject_globals():
    lang = get_lang()
    club = Club.get() or {}
    if club.get("logo"):
        logo = url_for("static", filename=club["logo"])
    else:
        logo = url_for("static", filename="img/logo_placeholder.svg")

    def t(key):
        return translate(key, lang)

    return {
        "t": t,
        "lang": lang,
        "is_rtl": lang == "ar",
        "club": club,
        "club_logo": logo,
        "app_name": APP_NAME,
        "current_year": datetime.now().year,
    }


@app.template_filter("score_color")
def score_color_filter(score):
    return scoring.score_color(score or 0)


@app.template_filter("rating_of")
def rating_of_filter(score):
    return scoring.rating_key(score or 0)


def _save_upload(file_storage, prefix):
    if not file_storage or not file_storage.filename:
        return None
    extension = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        return None
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"{prefix}_{uuid.uuid4().hex[:10]}.{extension}"
    file_storage.save(os.path.join(UPLOAD_DIR, filename))
    return f"uploads/{filename}"


def _num(field):
    try:
        value = int(float((request.form.get(field) or "").strip()))
    except ValueError:
        value = 0
    return max(value, 0)


def _optional_int(field):
    raw = (request.form.get(field) or "").strip()
    return int(raw) if raw.isdigit() else None


def _collect_stats():
    return {field: _num(field) for field in STAT_FIELDS}


def _collect_match_info():
    venue = request.form.get("venue")
    return {
        "match_date": (request.form.get("match_date") or date.today().isoformat()),
        "opponent": (request.form.get("opponent") or "").strip(),
        "competition": (request.form.get("competition") or "").strip(),
        "venue": "away" if venue == "away" else "home",
        "notes": (request.form.get("notes") or "").strip(),
    }


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #

@app.route("/")
def index():
    return render_template(
        "index.html",
        goalkeepers=Goalkeeper.all(),
        summary=Evaluation.summary(),
        recent=Match.recent(5),
        ranking=Goalkeeper.ranking(),
    )


# --------------------------------------------------------------------------- #
# Goalkeepers
# --------------------------------------------------------------------------- #

@app.route("/goalkeepers")
def goalkeepers_list():
    return render_template("goalkeepers.html", goalkeepers=Goalkeeper.all())


@app.route("/goalkeepers/new", methods=["GET", "POST"])
def goalkeeper_new():
    if request.method == "POST":
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        if not first_name or not last_name:
            flash("error_required", "error")
            return redirect(url_for("goalkeeper_new"))
        photo = _save_upload(request.files.get("photo"), "gk")
        gid = Goalkeeper.create(
            first_name, last_name,
            birth_date=(request.form.get("birth_date") or "").strip() or None,
            nationality=(request.form.get("nationality") or "").strip() or None,
            jersey_number=_optional_int("jersey_number"),
            photo=photo,
        )
        flash("saved_ok")
        return redirect(url_for("goalkeeper_detail", gid=gid))
    return render_template("goalkeeper_form.html", goalkeeper=None)


@app.route("/goalkeepers/<int:gid>")
def goalkeeper_detail(gid):
    goalkeeper = Goalkeeper.get(gid)
    if not goalkeeper:
        abort(404)
    return render_template(
        "goalkeeper_detail.html",
        goalkeeper=goalkeeper,
        matches=Match.all(gid),
    )


@app.route("/goalkeepers/<int:gid>/edit", methods=["GET", "POST"])
def goalkeeper_edit(gid):
    goalkeeper = Goalkeeper.get(gid)
    if not goalkeeper:
        abort(404)
    if request.method == "POST":
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        if not first_name or not last_name:
            flash("error_required", "error")
            return redirect(url_for("goalkeeper_edit", gid=gid))
        photo = _save_upload(request.files.get("photo"), "gk")
        Goalkeeper.update(
            gid, first_name, last_name,
            birth_date=(request.form.get("birth_date") or "").strip() or None,
            nationality=(request.form.get("nationality") or "").strip() or None,
            jersey_number=_optional_int("jersey_number"),
            photo=photo,
        )
        flash("saved_ok")
        return redirect(url_for("goalkeeper_detail", gid=gid))
    return render_template("goalkeeper_form.html", goalkeeper=goalkeeper)


@app.route("/goalkeepers/<int:gid>/delete", methods=["POST"])
def goalkeeper_delete(gid):
    Goalkeeper.delete(gid)
    flash("deleted_ok")
    return redirect(url_for("goalkeepers_list"))


# --------------------------------------------------------------------------- #
# Matches & evaluations
# --------------------------------------------------------------------------- #

@app.route("/matches")
def matches_list():
    selected = request.args.get("goalkeeper_id", type=int)
    return render_template(
        "matches.html",
        matches=Match.all(selected),
        goalkeepers=Goalkeeper.all(),
        selected_goalkeeper=selected,
    )


@app.route("/matches/new", methods=["GET", "POST"])
def match_new():
    if request.method == "POST":
        goalkeeper_id = request.form.get("goalkeeper_id", type=int)
        if not goalkeeper_id:
            flash("error_required", "error")
            return redirect(url_for("match_new"))
        stats = _collect_stats()
        mid = Match.create(goalkeeper_id, _collect_match_info(), stats)
        Evaluation.save(mid, scoring.compute_evaluation(stats))
        flash("saved_ok")
        return redirect(url_for("match_result", mid=mid))
    return render_template(
        "match_form.html",
        match=None,
        goalkeepers=Goalkeeper.all(),
        today=date.today().isoformat(),
        categories=scoring.CATEGORIES,
        weights={c["key"]: c["weight"] for c in scoring.CATEGORIES},
    )


@app.route("/matches/<int:mid>")
def match_result(mid):
    match_row = Match.get(mid)
    if not match_row:
        abort(404)
    evaluation = Evaluation.get_by_match(mid)
    result = evaluation["breakdown"] if evaluation else scoring.compute_evaluation(match_row)
    return render_template(
        "match_result.html",
        match=match_row,
        result=result,
        categories=scoring.CATEGORIES,
    )


@app.route("/matches/<int:mid>/edit", methods=["GET", "POST"])
def match_edit(mid):
    match_row = Match.get(mid)
    if not match_row:
        abort(404)
    if request.method == "POST":
        stats = _collect_stats()
        Match.update(mid, _collect_match_info(), stats)
        Evaluation.save(mid, scoring.compute_evaluation(stats))
        flash("saved_ok")
        return redirect(url_for("match_result", mid=mid))
    return render_template(
        "match_form.html",
        match=match_row,
        goalkeepers=Goalkeeper.all(),
        today=match_row["match_date"],
        categories=scoring.CATEGORIES,
        weights={c["key"]: c["weight"] for c in scoring.CATEGORIES},
    )


@app.route("/matches/<int:mid>/delete", methods=["POST"])
def match_delete(mid):
    Match.delete(mid)
    flash("deleted_ok")
    return redirect(url_for("matches_list"))


# --------------------------------------------------------------------------- #
# Club settings
# --------------------------------------------------------------------------- #

@app.route("/club", methods=["GET", "POST"])
def club_settings():
    if request.method == "POST":
        logo = _save_upload(request.files.get("logo"), "logo")
        Club.update(
            (request.form.get("name_fr") or "").strip(),
            (request.form.get("name_ar") or "").strip(),
            logo,
        )
        flash("saved_ok")
        return redirect(url_for("club_settings"))
    return render_template("club.html", club=Club.get() or {})


# --------------------------------------------------------------------------- #
# Language & API
# --------------------------------------------------------------------------- #

@app.route("/lang/<code>")
def set_language(code):
    code = code if code in LANGS else DEFAULT_LANG
    referrer = request.referrer
    if not referrer or urlparse(referrer).netloc != request.host:
        referrer = url_for("index")
    response = redirect(referrer)
    response.set_cookie("lang", code, max_age=60 * 60 * 24 * 365)
    return response


@app.route("/api/translations/<code>")
def api_translations(code):
    if code not in LANGS:
        abort(404)
    return jsonify(TRANSLATIONS[code])


@app.route("/api/matches/<int:mid>/evaluation")
def api_evaluation(mid):
    match_row = Match.get(mid)
    if not match_row:
        abort(404)
    evaluation = Evaluation.get_by_match(mid)
    result = evaluation["breakdown"] if evaluation else scoring.compute_evaluation(match_row)
    return jsonify({
        "match_id": mid,
        "goalkeeper": f"{match_row['first_name']} {match_row['last_name']}",
        "date": match_row["match_date"],
        "opponent": match_row["opponent"],
        "evaluation": result,
    })


def _local_network_ip():
    # UDP connect does not send packets; it only resolves the outgoing interface IP.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(0.3)
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()


if __name__ == "__main__":
    network_ip = _local_network_ip()
    print("=" * 60)
    print(f" {APP_NAME}")
    print("=" * 60)
    print(" Sur cet ordinateur      : http://127.0.0.1:5000")
    if network_ip:
        print(f" A partager sur le reseau : http://{network_ip}:5000")
    else:
        print(" Reseau local non detecte (verifiez la connexion Wi-Fi / Ethernet)")
    print("=" * 60)
    print(" Laissez cette fenetre ouverte pendant l'utilisation.")
    print("=" * 60)
    if os.environ.get("FOURA_OPEN_BROWSER") == "1":
        import threading
        import webbrowser
        threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
