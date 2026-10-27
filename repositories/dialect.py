"""Oracle SQL, on every screen.

The portal's tables are kept by an embedded engine, but the dialect this course
teaches is Oracle's. So Oracle syntax is accepted *everywhere* the portal runs a
statement — the SQL console, the raw-data browser, the studio's portal
connection, every repository query behind a screen or a PDF.

A statement that carries an Oracle-only construct is translated by the same
translator the studio's `ORACLE_XE` connection uses, then executed. A statement
with no such construct is handed to the engine byte for byte, so nothing that
already works can be changed by this layer.

What is understood: `ROWNUM`, `DUAL`, `SYSDATE`, `SYSTIMESTAMP`, `MINUS`,
`LISTAGG … WITHIN GROUP`, `NVL`, `NVL2`, `DECODE`, `TO_CHAR`, `TO_DATE`,
`TO_NUMBER`, `TRUNC`, `NANVL`, `FETCH FIRST n ROWS ONLY`, `OFFSET … FETCH`,
`DATE '1980-12-17'`, and `USER` (which reports the signed-in account).

What is deliberately not: sequences (`NEXTVAL`/`CURRVAL` would reach into the
practice file, which no portal screen may touch), DDL rewriting, and anything
that changes a table's shape. The portal's own data model stays as designed;
this layer only changes how a statement may be spelled.
"""
import re

from config import Config
from repositories import oracle

# Words that only Oracle SQL uses. Anything else is passed straight through.
ORACLE_ONLY = re.compile(
    r"""\b(
        ROWNUM | DUAL | SYSDATE | SYSTIMESTAMP | MINUS | LISTAGG |
        NVL | NVL2 | DECODE | TO_CHAR | TO_DATE | TO_NUMBER | TRUNC | NANVL |
        VARCHAR2 | NVARCHAR2 | NCLOB | ROWID | UROWID
    )\b
    | \bNUMBER\s*\(
    | \bGENERATED\s+(?:ALWAYS|BY\s+DEFAULT)\b
    | \bFETCH\s+(?:FIRST|NEXT)\s+\d+
    | \bOFFSET\s+\d+\s+ROWS?""",
    re.IGNORECASE | re.VERBOSE,
)

_STRING = re.compile(r"'(?:''|[^'])*'")
_COMMENT = re.compile(r'/\*.*?\*/|--[^\n]*', re.S)


def enabled():
    """`DB_DIALECT=oracle` (the default) accepts Oracle syntax anywhere."""
    return (getattr(Config, 'DB_DIALECT', 'oracle') or 'oracle').lower() != 'native'


def stripped(sql):
    """The statement with its literals and comments blanked, for keyword checks."""
    text = _COMMENT.sub(' ', sql or '')
    return _STRING.sub("''", text)


def looks_oracle(sql):
    return bool(ORACLE_ONLY.search(stripped(sql)))


def current_user(fallback='PORTAL'):
    """What Oracle's USER pseudo-column should report: the signed-in account."""
    try:
        from flask import has_request_context, session
        if has_request_context():
            return str(session.get('username') or fallback).upper()
    except (ImportError, RuntimeError):
        pass
    return fallback


def to_engine(sql, user=None):
    """Return ``(engine_sql, notes)``. Passthrough when nothing needs translating."""
    if not sql or not enabled() or not looks_oracle(sql):
        return sql, []
    try:
        translated, notes = oracle.translate(sql, user=user or current_user(), sequences=False)
    except Exception:                       # a translator slip must never break a screen
        return sql, []
    if not translated:
        return sql, []
    return translated, list(notes or [])


def describe(sql):
    """A short, human sentence about what the layer did, or '' when it did nothing."""
    engine_sql, notes = to_engine(sql)
    if engine_sql == sql and not notes:
        return ''
    bits = '; '.join(notes) if notes else 'Oracle syntax translated for the engine.'
    return bits
