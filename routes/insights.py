from flask import Blueprint, render_template, request, jsonify
from routes.auth import login_required, role_required
from repositories.insights import InsightsRepository

insights_bp = Blueprint("insights", __name__)

@insights_bp.route("/insights")
@login_required
@role_required("admin")
def insights_view():
    tab = request.args.get("tab", "queries")
    selected_qid = request.args.get("qid", "Q01")

    queries = InsightsRepository.load_showcase_queries()
    current_query = InsightsRepository.get_query_by_id(selected_qid) or (queries[0] if queries else None)
    audit_rows = InsightsRepository.get_audit_log(limit=40)
    tables = InsightsRepository.get_schema_tables()

    return render_template(
        "insights/lab.html",
        tab=tab,
        queries=queries,
        current_query=current_query,
        selected_qid=selected_qid,
        audit_rows=audit_rows,
        tables=tables
    )

@insights_bp.route("/api/insights/execute/<qid>")
@login_required
@role_required("admin")
def execute_query(qid):
    result = InsightsRepository.execute_showcase(qid)
    return jsonify(result)

@insights_bp.route("/api/insights/explain/<qid>")
@login_required
@role_required("admin")
def explain_query(qid):
    result = InsightsRepository.get_explain_plan(qid)
    return jsonify(result)

@insights_bp.route("/api/insights/transaction-demo", methods=["POST"])
@login_required
@role_required("admin")
def run_transaction_demo():
    result = InsightsRepository.run_transaction_demo()
    return jsonify(result)
