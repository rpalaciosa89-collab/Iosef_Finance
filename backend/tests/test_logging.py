"""
SP-6.4: logging estructurado JSON con request_id.
"""
import ast
import json
import logging


def test_request_id_generated(client):
    """Cada request genera un request_id y lo expone en el header de respuesta."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers
    assert len(resp.headers["x-request-id"]) >= 8


def test_request_id_respects_header(client):
    """Si el cliente envia X-Request-Id, se respeta (correlacion distribuida)."""
    resp = client.get("/api/health", headers={"X-Request-Id": "trace-abc-123"})
    assert resp.headers["x-request-id"] == "trace-abc-123"


def test_logs_are_json_with_request_id(client, caplog):
    """El record de acceso lleva request_id y campos estructurados (JSON al imprimir)."""
    import logging

    with caplog.at_level(logging.INFO):
        client.get("/api/health")

    access_records = [r for r in caplog.records if r.name == "access"]
    assert len(access_records) >= 1, "no se emitió log de acceso"
    record = access_records[0]
    assert getattr(record, "request_id", None), "el record debe llevar request_id"
    assert getattr(record, "status_code", None) is not None
    assert getattr(record, "latency_ms", None) is not None


def test_json_formatter_produces_valid_json(caplog):
    """El JsonFormatter serializa el record como JSON valido con request_id."""
    from app.core.logging_setup import JsonFormatter, request_id_var

    token = request_id_var.set("trace-xyz")
    try:
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname=__file__, lineno=1,
            msg="hola %s", args=("mundo",), exc_info=None,
        )
        out = JsonFormatter().format(record)
        parsed = json.loads(out)
        assert parsed["message"] == "hola mundo"
        assert parsed["request_id"] == "trace-xyz"
        assert parsed["level"] == "INFO"
    finally:
        request_id_var.reset(token)



def test_no_print_in_services():
    """No debe haber prints residuales en los servicios criticos (fuera de __main__)."""
    import ast
    import os

    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "services")
    offenders = []
    for root, _, files in os.walk(base):
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(root, f)
            tree = ast.parse(open(path).read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "print":
                    # excluir bloques if __name__ == "__main__" (demo scripts)
                    in_main = any(
                        isinstance(parent, ast.If)
                        and isinstance(parent.test, ast.Compare)
                        and isinstance(parent.test.left, ast.Name)
                        and parent.test.left.id == "__name__"
                        for parent in _ancestors(tree, node)
                    )
                    if not in_main:
                        offenders.append(f"{f}:{node.lineno}")
    assert offenders == [], f"prints en servicios: {offenders}"


def _ancestors(tree, node):
    """Genera los ancestros de node en el arbol sintactico."""
    for parent in ast.walk(tree):
        if node in ast.walk(parent) and parent is not node:
            yield parent