"""LeadFlow CRM: self-contained FastAPI + SQLite portfolio demo."""
from __future__ import annotations

import csv
import io
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict

BASE = Path(__file__).resolve().parent
STAGES = ("new", "contact", "proposal", "negotiation", "won")
STAGE_LABELS = {"new": "Новая", "contact": "На связи", "proposal": "Предложение", "negotiation": "Переговоры", "won": "Выиграно"}

class LeadCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    company: str = Field(min_length=2, max_length=90)
    contact: str = Field(min_length=2, max_length=90)
    service: str = Field(min_length=2, max_length=100)
    amount: int = Field(ge=0, le=100_000_000)
    stage: Literal["new", "contact", "proposal", "negotiation", "won"] = "new"
    note: str = Field(default="", max_length=500)

class LeadPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    company: str | None = Field(default=None, min_length=2, max_length=90)
    contact: str | None = Field(default=None, min_length=2, max_length=90)
    service: str | None = Field(default=None, min_length=2, max_length=100)
    amount: int | None = Field(default=None, ge=0, le=100_000_000)
    stage: Literal["new", "contact", "proposal", "negotiation", "won"] | None = None
    note: str | None = Field(default=None, max_length=500)

@contextmanager
def connect(db_path: str):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def init_db(path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL, contact TEXT NOT NULL, service TEXT NOT NULL,
            amount INTEGER NOT NULL CHECK(amount >= 0), stage TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER, description TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        );
        """)
        if db.execute("SELECT COUNT(*) FROM leads").fetchone()[0]:
            return
        seed = [
            ("Northstar Studio", "Алина М.", "Корпоративный сайт", 185000, "new"),
            ("Green Basket", "Ерлан Д.", "Интернет-магазин", 320000, "contact"),
            ("Nomad Coffee", "Асем К.", "Telegram-бот", 125000, "proposal"),
            ("Vector Logistics", "Тимур С.", "Автоматизация CRM", 490000, "negotiation"),
            ("Bright Academy", "Мадина Т.", "Сайт и формы", 220000, "won"),
            ("Urban Fit", "Артём В.", "Запись клиентов", 145000, "new"),
            ("Lime Market", "Данияр А.", "WhatsApp-бот", 190000, "contact"),
            ("Peak Digital", "Диана Ш.", "Админ-панель", 275000, "proposal"),
            ("Sunflower Bakery", "София Н.", "Каталог товаров", 160000, "won"),
            ("Atlas Services", "Руслан К.", "Интеграция API", 260000, "negotiation"),
            ("Kite Travel", "Айжан Б.", "Лендинг", 110000, "new"),
            ("Orbit Repair", "Никита П.", "Чат-бот поддержки", 150000, "contact"),
        ]
        for i, item in enumerate(seed):
            ts = (datetime.now(timezone.utc) - timedelta(hours=i*3+1)).isoformat(timespec="seconds")
            cur = db.execute("""INSERT INTO leads (company,contact,service,amount,stage,note,created_at,updated_at)
                                VALUES (?,?,?,?,?,'',?,?)""", (*item,ts,ts))
            if i < 6:
                db.execute("INSERT INTO activities (lead_id,description,created_at) VALUES (?,?,?)",
                           (cur.lastrowid, f"Добавлена сделка: {item[0]}", ts))

def create_app(db_path: str | None = None) -> FastAPI:
    path = db_path or os.getenv("LEADFLOW_DB", str(BASE / "leadflow.db"))
    init_db(path)
    app = FastAPI(title="LeadFlow CRM API", version="1.0.0", description="Portfolio demo CRM. No authentication: run on localhost only.")
    app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(BASE / "static" / "index.html")

    @app.get("/api/leads")
    def leads(stage: str | None = None, q: str = Query(default="", max_length=120)):
        if stage and stage not in STAGES:
            raise HTTPException(400, "Неизвестный этап")
        query = "SELECT * FROM leads WHERE 1=1"
        params: list[str] = []
        if stage:
            query += " AND stage=?"
            params.append(stage)
        if q.strip():
            query += " AND (company LIKE ? OR contact LIKE ? OR service LIKE ?)"
            params.extend([f"%{q.strip()}%"] * 3)
        query += " ORDER BY updated_at DESC, id DESC"
        with connect(path) as db:
            return [dict(row) for row in db.execute(query, params)]

    @app.get("/api/summary")
    def summary():
        with connect(path) as db:
            rows = [dict(row) for row in db.execute("SELECT stage, COUNT(*) AS count, COALESCE(SUM(amount),0) AS amount FROM leads GROUP BY stage")]
            recent = [dict(row) for row in db.execute("SELECT * FROM activities ORDER BY created_at DESC,id DESC LIMIT 6")]
        counts = {stage: 0 for stage in STAGES}
        totals = {stage: 0 for stage in STAGES}
        for row in rows:
            counts[row["stage"]] = row["count"]
            totals[row["stage"]] = row["amount"]
        all_count = sum(counts.values())
        return {
            "total": all_count, "active": all_count-counts["won"],
            "pipeline_amount": sum(value for key, value in totals.items() if key != "won"),
            "won_amount": totals["won"],
            "conversion_pct": round(100 * counts["won"] / all_count, 1) if all_count else 0,
            "counts": counts, "amounts": totals, "activities": recent,
        }

    @app.post("/api/leads", status_code=201)
    def create_lead(payload: LeadCreate):
        ts = now_iso()
        with connect(path) as db:
            cur = db.execute("""INSERT INTO leads (company,contact,service,amount,stage,note,created_at,updated_at)
                                VALUES (?,?,?,?,?,?,?,?)""", (payload.company, payload.contact, payload.service,
                                      payload.amount, payload.stage, payload.note, ts, ts))
            db.execute("INSERT INTO activities (lead_id, description,created_at) VALUES (?,?,?)",
                       (cur.lastrowid, f"Новая сделка: {payload.company}", ts))
            result = db.execute("SELECT * FROM leads WHERE id=?", (cur.lastrowid,)).fetchone()
            return dict(result)

    @app.patch("/api/leads/{lead_id}")
    def patch_lead(lead_id: int, payload: LeadPatch):
        data = payload.model_dump(exclude_unset=True)
        if not data:
            raise HTTPException(400, "Нет полей для изменения")
        if any(value is None for value in data.values()):
            raise HTTPException(422, "Поля не могут быть null")
        with connect(path) as db:
            old = db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
            if not old:
                raise HTTPException(404, "Сделка не найдена")
            changed = {key:value for key,value in data.items() if value != old[key]}
            if changed:
                changed["updated_at"] = now_iso()
                set_clause = ",".join(f"{field}=?" for field in changed)
                db.execute(f"UPDATE leads SET {set_clause} WHERE id=?", (*changed.values(), lead_id))
                desc = f"Этап изменён: {STAGE_LABELS[old['stage']]} → {STAGE_LABELS[changed['stage']]}" if "stage" in changed else "Обновлены данные сделки"
                db.execute("INSERT INTO activities (lead_id, description,created_at) VALUES (?,?,?)", (lead_id,desc,now_iso()))
            return dict(db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone())

    @app.delete("/api/leads/{lead_id}", status_code=204)
    def delete_lead(lead_id: int):
        with connect(path) as db:
            old = db.execute("SELECT company FROM leads WHERE id=?", (lead_id,)).fetchone()
            if not old:
                raise HTTPException(404, "Сделка не найдена")
            db.execute("DELETE FROM activities WHERE lead_id=?", (lead_id,))
            db.execute("DELETE FROM leads WHERE id=?", (lead_id,))
            db.execute("INSERT INTO activities (lead_id,description,created_at) VALUES (NULL,?,?)", (f"Удалена сделка: {old['company']}",now_iso()))

    @app.get("/api/export.csv")
    def export_csv():
        with connect(path) as db:
            rows = [dict(r) for r in db.execute("SELECT id,company,contact,service,amount,stage,note,created_at FROM leads ORDER BY id")]
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=["id","company","contact","service","amount","stage","note","created_at"])
        writer.writeheader()
        writer.writerows(rows)
        content = "\ufeff" + out.getvalue()
        return StreamingResponse(iter([content.encode("utf-8")]), media_type="text/csv; charset=utf-8",
                                 headers={"Content-Disposition":"attachment; filename=leadflow_export.csv"})

    return app

app = create_app()
