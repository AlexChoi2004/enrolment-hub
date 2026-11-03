"""The semester simulator pages. Only the simulated demo student can use them."""
from flask import Blueprint, abort, flash, g, make_response, redirect, render_template, request, url_for

from shared import security
from shared.db import get_db
from simulator import service

bp = Blueprint("simulator", __name__, template_folder="templates", url_prefix="/simulator")


def _demo_only():
    if not g.user["is_demo"]:
        abort(403)


def _private(html, status=200):
    response = make_response(html, status)
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.get("")
@security.login_required
def index():
    _demo_only()
    return _private(render_template("simulator/index.html", state=service.current_state(get_db(), g.user["id"])))


@bp.get("/results")
@security.login_required
def results():
    _demo_only()
    mode = "skip" if request.args.get("mode") == "skip" else "complete"
    state = service.current_state(get_db(), g.user["id"])
    return _private(render_template("simulator/results.html", state=state, mode=mode, labels=service.LABELS, form={}, errors=[]))


@bp.post("/review")
@security.login_required
def review():
    _demo_only()
    security.require_csrf()
    state = service.current_state(get_db(), g.user["id"])
    mode = "skip" if request.form.get("mode") == "skip" else "complete"
    choices, errors = service.parse_choices(state["subjects"], request.form.get)
    errors += service.check_choices(state["subjects"], choices)
    if errors:
        return _private(render_template("simulator/results.html", state=state, mode=mode, labels=service.LABELS,
                                        form=request.form, errors=errors), 400)
    rows = [{**s, **choices[s["code"]], "label": service.LABELS[choices[s["code"]]["result"]]} for s in state["subjects"]]
    return _private(render_template("simulator/review.html", state=state, mode=mode, rows=rows))


@bp.post("/finish")
@security.login_required
def finish():
    _demo_only()
    security.require_csrf()
    conn = get_db()
    state = service.current_state(conn, g.user["id"])
    choices, errors = service.parse_choices(state["subjects"], request.form.get)
    if errors:
        flash(" ".join(errors), "error")
        return redirect(url_for("simulator.results"), code=303)
    try:
        done = service.complete_semester(conn, g.user["id"], choices)
    except service.SimulatorError as exc:
        flash(str(exc), "error")
        return redirect(url_for("simulator.results"), code=303)
    passed = sum(1 for r in done["results"] if r["outcome"] == "passed")
    failed = sum(1 for r in done["results"] if r["outcome"] == "failed")
    flash(f"{done['from']} finished: {passed} passed, {failed} failed, {len(done['no_result'])} with no result. "
          f"You are now in {done['to']} (Year {done['year']}, Semester {done['semester']}).", "success")
    if done["plans_to_reschedule"]:
        flash(f"{done['plans_to_reschedule']} planned subject(s) were planned for a session that has passed: "
              "reschedule them in the Degree planner.", "warning")
    return redirect(url_for("simulator.index"), code=303)


@bp.get("/reset")
@security.login_required
def reset_page():
    _demo_only()
    return _private(render_template("simulator/reset.html"))


@bp.post("/reset")
@security.login_required
def reset():
    _demo_only()
    security.require_csrf()
    if request.form.get("confirm") != "yes":
        flash("Tick the box to confirm the reset.", "error")
        return redirect(url_for("simulator.reset_page"), code=303)
    service.reset_demo_student(get_db())
    flash("The demo student has been reset to the original seeded records.", "success")
    return redirect(url_for("simulator.index"), code=303)
