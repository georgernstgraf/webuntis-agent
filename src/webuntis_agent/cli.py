"""CLI entry point for webuntis-agent."""

from __future__ import annotations

import argparse
import sys

# Backward-compat re-exports (split into cli_* modules, #15).
# `from webuntis_agent.cli import <cmd_*>` keeps working.
from webuntis_agent.cli_absences import (
    cmd_batch_check_absences,
    cmd_check_absences,
    cmd_check_all_absences,
)
from webuntis_agent.cli_common import (
    _load_env,
    _session_path,
    _make_client,
    _add_school_year_arg,
    _sleep_between,
    _fixed_text,
    _date_arg,
    _lesson_details_url,
    _block_bounds,
    _base_period_fields,
    _open_period_entries,
    _group_lesson_entries,
    _period_summary,
    _fetch_open_periods,
    _no_open_periods,
    _read_text_arg,
    _resolve_topic_id,
    _submit_topic_entries,
    _format_search_hit,
    _annotate_search_hits,
)
from webuntis_agent.cli_lehrstoff import (
    cmd_lessons,
    cmd_lehrstoff_list,
    cmd_lehrstoff_get,
    cmd_lehrstoff_set,
    cmd_lehrstoff_batch_set,
    cmd_lehrstoff_from_git,
    cmd_lehrstoff_status,
    cmd_lehrstoff_fill,
    cmd_lehrstoff_verify,
    cmd_lehrstoff_fill_fixed,
)
from webuntis_agent.cli_misc import (
    cmd_login,
    cmd_logout,
    cmd_rpc,
    cmd_rest,
    cmd_lesson_info,
    cmd_session_status,
    cmd_search,
    _kv_for_class,
    cmd_kv,
)
from webuntis_agent.cli_students import (
    _teacher_names_for_class,
    _resolve_lsid_from_class_subject,
    cmd_students_list,
    cmd_students_find,
    _build_students_payload,
    _finish_students_command,
    cmd_students_add,
    cmd_students_edit,
)

__all__ = [
    "_load_env",
    "_session_path",
    "_make_client",
    "_add_school_year_arg",
    "_sleep_between",
    "_fixed_text",
    "_date_arg",
    "_lesson_details_url",
    "_block_bounds",
    "_base_period_fields",
    "_open_period_entries",
    "_group_lesson_entries",
    "_period_summary",
    "_fetch_open_periods",
    "_no_open_periods",
    "_read_text_arg",
    "_resolve_topic_id",
    "_submit_topic_entries",
    "_format_search_hit",
    "_annotate_search_hits",
    "cmd_lessons",
    "cmd_lehrstoff_list",
    "cmd_lehrstoff_get",
    "cmd_lehrstoff_set",
    "cmd_lehrstoff_batch_set",
    "cmd_lehrstoff_from_git",
    "cmd_lehrstoff_status",
    "cmd_lehrstoff_fill",
    "cmd_lehrstoff_verify",
    "cmd_lehrstoff_fill_fixed",
    "_teacher_names_for_class",
    "_resolve_lsid_from_class_subject",
    "cmd_students_list",
    "cmd_students_find",
    "_build_students_payload",
    "_finish_students_command",
    "cmd_students_add",
    "cmd_students_edit",
    "cmd_check_absences",
    "cmd_batch_check_absences",
    "cmd_check_all_absences",
    "cmd_login",
    "cmd_logout",
    "cmd_rpc",
    "cmd_rest",
    "cmd_lesson_info",
    "cmd_session_status",
    "cmd_search",
    "_kv_for_class",
    "cmd_kv",
    "main",
]


def main() -> int:
    p = argparse.ArgumentParser(prog="webuntis-agent")
    p.add_argument("--school-year-id", type=int, default=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    rec = sub.add_parser("record", help="run the CDP recorder")
    rec.add_argument("--host", default="localhost",
                     help="CDP host of the browser (default localhost)")
    rec.add_argument("--port", type=int, default=9222,
                     help="CDP port of the browser (default 9222)")
    rec.add_argument("--domain", default="spengergasse.webuntis.com",
                     help="WebUntis domain to filter requests on")

    sub.add_parser(
        "login",
        help="log in once and cache the session for all following calls")
    login_parser = sub.choices["login"]
    login_parser.set_defaults(func=cmd_login)

    sub.add_parser(
        "logout",
        help="invalidate the session and delete the session cache")
    sub.choices["logout"].set_defaults(func=cmd_logout)

    se = sub.add_parser(
        "search", help="search classes/teachers/students (full names)")
    se.add_argument("query")
    se.add_argument("--json", action="store_true")
    se.add_argument("--fallback", action="store_true",
                    help="tokenizing fallback: Vor-/Nachname einzeln "
                         "suchen und zusammenführen (findet z.B. "
                         "'Erika Muster' via Einzelteile + "
                         "Kurzname-Heuristik)")
    se.add_argument("--all-years", action="store_true",
                     help="bei Leerstand bzw. zusätzlich ältere Schuljahre "
                          "durchsuchen (Treffer als NICHT AKTUELL "
                          "gekennzeichnet; --school-year-id pinnt auf ein "
                          "Jahr ohne Fallback)")
    _add_school_year_arg(se)
    se.set_defaults(func=cmd_search)

    kv = sub.add_parser(
        "kv", help="show the Klassenvorstand of a class (id or name), "
                   "or of the class(es) of a student (--student)")
    kv.add_argument("klasse", nargs="?", default=None,
                    help="class id (e.g. 4134) or name (e.g. 5AAIF); "
                         "required unless --student")
    kv.add_argument("--student", default=None,
                    help="student name: resolve student -> class(es) "
                         "-> KV (tokenizing match on first/last/short name)")
    kv.add_argument("--json", action="store_true")
    _add_school_year_arg(kv)
    kv.set_defaults(func=cmd_kv)

    rp = sub.add_parser(
        "rpc", help="generic JSON-RPC passthrough (JSON output)")
    rp.add_argument("method", help="JSON-RPC method, e.g. getKlassen")
    rp.add_argument("params_json", nargs="?", default=None,
                    help="params as JSON string, default {}")
    rp.set_defaults(func=cmd_rpc)

    rst = sub.add_parser(
        "rest", help="generic REST passthrough to /WebUntis/api/<path>")
    rst.add_argument("path", help="path relative to /WebUntis/api, e.g. "
                                  "rest/view/v1/schoolyears")
    rst.add_argument("--method", default="GET",
                     choices=["GET", "POST", "PUT", "DELETE"],
                     help="HTTP method (default GET). NOTE: method does "
                          "NOT imply read vs. write — POST open-periods "
                          "is read-only, PUT lesson-topics writes.")
    rst.add_argument("--data-json", default=None,
                     help="request body as JSON string (POST/PUT)")
    _add_school_year_arg(rst)
    rst.set_defaults(func=cmd_rest)

    les = sub.add_parser(
        "lesson", help="lesson diagnostics")
    les_sub = les.add_subparsers(dest="sub", required=True)
    les_info = les_sub.add_parser(
        "info", help="teachers, klassen, mainStudentgroupId, "
                     "roster vs. attending distribution for one lsId")
    les_info.add_argument("lsid", type=int, help="lesson id (lsId)")
    les_info.add_argument("--json", action="store_true")
    _add_school_year_arg(les_info)
    les_info.set_defaults(func=cmd_lesson_info)

    sess = sub.add_parser(
        "session", help="session cache and diagnostics")
    sess_sub = sess.add_subparsers(dest="sub", required=True)
    sess_status = sess_sub.add_parser(
        "status", help="cache age + live check via app/data")
    sess_status.add_argument("--json", action="store_true",
                             help="include the full app/data payload")
    sess_status.set_defaults(func=cmd_session_status)

    le = sub.add_parser("lehrstoff", help="Lehrstoff (lesson topic)")
    le_sub = le.add_subparsers(dest="sub", required=True)
    le_list = le_sub.add_parser("list")
    le_list.add_argument("--start", type=_date_arg, required=True)
    le_list.add_argument("--end", type=_date_arg, required=True)
    le_list.add_argument("--json", action="store_true")
    _add_school_year_arg(le_list)
    le_list.set_defaults(func=cmd_lehrstoff_list)

    ls = sub.add_parser(
        "lessons", help="list the user's lessons for one class, "
                        "grouped by lesson (lsId)")
    ls.add_argument("classname", help="class name, e.g. 3BAIF")
    ls.add_argument("--subject", default=None,
                    help="filter by subject short name (prefix match)")
    ls.add_argument("--start", type=_date_arg, default=None,
                    help="default: current schoolyear start")
    ls.add_argument("--end", type=_date_arg, default=None,
                    help="default: current schoolyear end")
    ls.add_argument("--full-names", action="store_true",
                    help="resolve teacher shorts to 'Lastname, Firstname'")
    ls.add_argument("--json", action="store_true")
    _add_school_year_arg(ls)
    ls.set_defaults(func=cmd_lessons)

    le_get = le_sub.add_parser("get")
    le_get.add_argument("--period", type=int, required=True)
    _add_school_year_arg(le_get)
    le_get.set_defaults(func=cmd_lehrstoff_get)

    le_set = le_sub.add_parser("set")
    le_set.add_argument("--period", type=int, required=True)
    le_set.add_argument("--topic-id", type=int, default=None)
    src = le_set.add_mutually_exclusive_group(required=True)
    src.add_argument("--text")
    src.add_argument("--text-file")
    src.add_argument("--text-stdin", action="store_true")
    _add_school_year_arg(le_set)
    le_set.set_defaults(func=cmd_lehrstoff_set)

    le_batch = le_sub.add_parser("batch-set",
                                 help="set multiple topics from a JSON file")
    le_batch.add_argument("--file", required=True,
                          help="JSON file: [{periodId, topicId, text, "
                               "classId, start, end, date}, ...]")
    le_batch.add_argument("--delay", type=float, default=1.0,
                           help="seconds to wait between PUTs (default 1.0, "
                                "avoids IP rate-limiting)")
    _add_school_year_arg(le_batch)
    le_batch.set_defaults(func=cmd_lehrstoff_batch_set)

    le_git = le_sub.add_parser("from-git",
                               help="derive text from GRG-* git logs")
    le_git.add_argument("--class-name", required=True)
    le_git.add_argument("--subject", required=True,
                        help="WebUntis subject short name, e.g. SWP1y")
    le_git.add_argument("--date", type=_date_arg, required=True)
    le_git.add_argument("--period", type=int, default=None)
    le_git.add_argument("--topic-id", type=int, default=None)
    le_git.add_argument("--dry-run", action="store_true")
    _add_school_year_arg(le_git)
    le_git.set_defaults(func=cmd_lehrstoff_from_git)

    le_status = le_sub.add_parser("status", help="overview of open periods")
    le_status.add_argument("--start", type=_date_arg, required=True)
    le_status.add_argument("--end", type=_date_arg, required=True)
    le_status.add_argument("--json", action="store_true")
    _add_school_year_arg(le_status)
    le_status.set_defaults(func=cmd_lehrstoff_status)

    le_fill = le_sub.add_parser("fill",
                                help="fetch periods + git diffs, build batch JSON")
    le_fill.add_argument("--start", type=_date_arg, required=True)
    le_fill.add_argument("--end", type=_date_arg, required=True)
    le_fill.add_argument("--dry-run", action="store_true", default=True)
    le_fill.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    le_fill.add_argument("--file", default=None,
                          help="confirmed batch JSON (required without --dry-run)")
    le_fill.add_argument("--delay", type=float, default=1.0)
    le_fill.add_argument("--json", action="store_true")
    _add_school_year_arg(le_fill)
    le_fill.set_defaults(func=cmd_lehrstoff_fill)

    le_verify = le_sub.add_parser("verify",
                                  help="check which periods truly have no text")
    le_verify.add_argument("--start", type=_date_arg, required=True)
    le_verify.add_argument("--end", type=_date_arg, required=True)
    le_verify.add_argument("--json", action="store_true")
    _add_school_year_arg(le_verify)
    le_verify.set_defaults(func=cmd_lehrstoff_verify)

    le_fill_fixed = le_sub.add_parser("fill-fixed",
                                   help="fill SS/BESP with fixed text")
    le_fill_fixed.add_argument("--start", type=_date_arg, required=True)
    le_fill_fixed.add_argument("--end", type=_date_arg, required=True)
    le_fill_fixed.add_argument("--dry-run", action="store_true", default=True,
                            help="(default) show what would be filled, "
                                 "write nothing")
    le_fill_fixed.add_argument("--no-dry-run", dest="dry_run",
                            action="store_false",
                            help="actually submit the fixed-text topics")
    le_fill_fixed.add_argument("--json", action="store_true")
    le_fill_fixed.add_argument("--delay", type=float, default=1.0)
    _add_school_year_arg(le_fill_fixed)
    le_fill_fixed.set_defaults(func=cmd_lehrstoff_fill_fixed)

    # -- absences --
    abs_parser = sub.add_parser("absences", help="Absenzenkontrolle")
    abs_sub = abs_parser.add_subparsers(dest="sub", required=True)

    abs_check = abs_sub.add_parser("check", help="check absences for one period")
    abs_check.add_argument("--period", type=int, required=True)
    abs_check.set_defaults(func=cmd_check_absences)

    abs_batch = abs_sub.add_parser("batch-check",
                                   help="check absences from JSON file")
    abs_batch.add_argument("--file", required=True,
                           help="JSON: [{periodId: int}, ...]")
    abs_batch.add_argument("--delay", type=float, default=1.0)
    abs_batch.set_defaults(func=cmd_batch_check_absences)

    abs_all = abs_sub.add_parser("check-all",
                                 help="fetch open periods and check all absences")
    abs_all.add_argument("--start", type=_date_arg, required=True)
    abs_all.add_argument("--end", type=_date_arg, required=True)
    abs_all.add_argument("--delay", type=float, default=1.0)
    _add_school_year_arg(abs_all)
    abs_all.set_defaults(func=cmd_check_all_absences)

    # -- students --
    stu = sub.add_parser("students", help="Schülerverwaltung (lesson attendance)")
    stu_sub = stu.add_subparsers(dest="sub", required=True)

    stu_list = stu_sub.add_parser(
        "list", help="dump a lesson's attendance matrix")
    stu_list.add_argument("--lsid", type=int, default=None,
                          help="lesson id; optional if CLASS SUBJECT given")
    stu_list.add_argument("class_name", nargs="?", default=None,
                          help="class name, e.g. 2AHWII (with SUBJECT "
                               "resolves the lsId automatically)")
    stu_list.add_argument("subject", nargs="?", default=None,
                          help="subject short name, e.g. SWP1x")
    stu_list.add_argument("--class-id", type=int, default=None,
                          help="only students of this class id")
    stu_list.add_argument("--attending-only", action="store_true")
    stu_list.add_argument("--all", action="store_true",
                          help="text view: show every student, not only "
                               "attending ones (JSON always shows all)")
    stu_list.add_argument("--json", action="store_true")
    _add_school_year_arg(stu_list)
    stu_list.set_defaults(func=cmd_students_list)

    stu_find = stu_sub.add_parser(
        "find",
        help="find students by name (tokenizing, auto-fallback "
             "to older schoolyears)")
    stu_find.add_argument("name", help="name, e.g. 'Erika Muster'")
    stu_find.add_argument("--class", dest="klasse", default=None,
                          help="filter by class name, e.g. 5BAIF")
    stu_find.add_argument("--json", action="store_true")
    _add_school_year_arg(stu_find)
    stu_find.set_defaults(func=cmd_students_find)

    stu_add = stu_sub.add_parser("add",
                                 help="add a student to a lesson's attendance")
    stu_add.add_argument("--lsid", type=int, required=True,
                         help="lesson id (lsId) of the target lesson")
    stu_add.add_argument("--class-id", type=int, required=True,
                         help="class id of the lesson's own class (students "
                              "kept unchanged)")
    stu_add.add_argument("--student-id", type=int, default=None)
    stu_add.add_argument("--student-name", default=None,
                         help="search by (partial) name; needs unique match")
    stu_add.add_argument("--dry-run", action="store_true", default=True)
    stu_add.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    stu_add.add_argument("--out", default=None,
                         help="write the submit payload JSON to this file")
    stu_add.add_argument("--verbose", action="store_true")
    _add_school_year_arg(stu_add)
    stu_add.set_defaults(func=cmd_students_add)

    stu_edit = stu_sub.add_parser(
        "edit",
        help="add/remove students in a lesson's attendance (single write)")
    stu_edit.add_argument("--lsid", type=int, required=True,
                          help="lesson id (lsId) of the target lesson")
    stu_edit.add_argument("--class-id", type=int, required=True,
                          help="class id of the lesson's own class (students "
                               "kept unchanged)")
    stu_edit.add_argument("--add-student-id", type=int, action="append",
                          default=None,
                          help="student id to enroll (repeatable)")
    stu_edit.add_argument("--remove-student-id", type=int, action="append",
                          default=None,
                          help="student id to un-enroll (attendedPeriods "
                               "reset to [], repeatable)")
    stu_edit.add_argument("--dry-run", action="store_true", default=True)
    stu_edit.add_argument("--no-dry-run", dest="dry_run",
                          action="store_false")
    stu_edit.add_argument("--out", default=None,
                          help="write the submit payload JSON to this file")
    stu_edit.add_argument("--verbose", action="store_true")
    _add_school_year_arg(stu_edit)
    stu_edit.set_defaults(func=cmd_students_edit)

    args = p.parse_args()
    try:
        if args.cmd == "record":
            from webuntis_agent.recorder import main as rec
            return rec([f"--host={args.host}", f"--port={args.port}",
                        f"--domain={args.domain}"])
        if hasattr(args, "func"):
            return args.func(args)
    except ModuleNotFoundError as e:
        print(
            f"Fehler: Python-Modul fehlt ({e.name}).\n\n"
            "Anleitung — venv im Repo anlegen:\n"
            "  python3 -m venv .venv\n"
            "  .venv/bin/pip install -e .\n\n"
            "Danach wu (.venv/bin/python) verwenden oder "
            "PYTHON_BIN auf das venv-Python setzen.",
            file=sys.stderr,
        )
        return 3
    p.print_help()
    return 1




if __name__ == "__main__":
    raise SystemExit(main())
