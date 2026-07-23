from __future__ import annotations

import csv
import io
from datetime import date, datetime, time
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.deps import AuthContext, require_any
from pos.models.orders import Order, OrderLine, OrderStatus, Payment

router = APIRouter(prefix="/reports")


@router.get("/rfm")
def rfm_segments(
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    """Simple RFM segmentation for customers with paid orders in this store."""
    from datetime import datetime, timedelta
    from pos.models.customers import Customer

    since = datetime.utcnow() - timedelta(days=365)
    customers = db.query(Customer).all()
    segments = []
    for c in customers:
        orders = (
            db.query(Order)
            .filter(
                Order.customer_id == c.id,
                Order.store_id == ctx.store_id,
                Order.status == OrderStatus.paid,
                Order.paid_at.isnot(None),
            )
            .all()
        )
        if not orders:
            continue
        last = max(o.paid_at for o in orders if o.paid_at)
        recency_days = (datetime.utcnow() - last.replace(tzinfo=None)).days if last else 999
        frequency = len(orders)
        from decimal import Decimal as Dec

        monetary = sum((o.total for o in orders), Dec("0"))
        # crude scores 1-3
        r = 3 if recency_days <= 30 else 2 if recency_days <= 90 else 1
        f = 3 if frequency >= 5 else 2 if frequency >= 2 else 1
        m = 3 if monetary >= 500000 else 2 if monetary >= 100000 else 1
        label = "Champions" if r + f + m >= 8 else "Loyal" if r + f + m >= 6 else "At Risk" if r == 1 else "Potential"
        segments.append(
            {
                "customer_id": c.id,
                "name": c.name,
                "phone": c.phone,
                "recency_days": recency_days,
                "frequency": frequency,
                "monetary": str(monetary),
                "rfm": f"{r}{f}{m}",
                "segment": label,
            }
        )
    return {"segments": segments, "count": len(segments)}


@router.get("/daily-sales")
def daily_sales(
    report_date: date | None = Query(default=None, alias="date"),
    ctx: AuthContext = Depends(require_any("manager", "admin", "cashier")),
    db: Session = Depends(get_db),
):
    day = report_date or date.today()
    start = datetime.combine(day, time.min)
    end = datetime.combine(day, time.max)

    orders = (
        db.query(Order)
        .filter(
            Order.store_id == ctx.store_id,
            Order.status == OrderStatus.paid,
            Order.paid_at >= start,
            Order.paid_at <= end,
        )
        .all()
    )
    gross = sum((o.subtotal for o in orders), Decimal("0"))
    discount = sum((o.discount for o in orders), Decimal("0"))
    net = sum((o.total for o in orders), Decimal("0"))

    by_method: dict[str, Decimal] = {}
    for o in orders:
        for p in o.payments:
            key = p.method.value
            by_method[key] = by_method.get(key, Decimal("0")) + p.amount

    # top products
    top_rows = (
        db.query(
            OrderLine.product_name,
            func.sum(OrderLine.qty).label("qty"),
            func.sum(OrderLine.line_total).label("revenue"),
        )
        .join(Order, Order.id == OrderLine.order_id)
        .filter(
            Order.store_id == ctx.store_id,
            Order.status == OrderStatus.paid,
            Order.paid_at >= start,
            Order.paid_at <= end,
        )
        .group_by(OrderLine.product_name)
        .order_by(func.sum(OrderLine.line_total).desc())
        .limit(10)
        .all()
    )
    top_products = [
        {"name": r.product_name, "qty": int(r.qty or 0), "revenue": str(r.revenue or 0)}
        for r in top_rows
    ]

    return {
        "date": day.isoformat(),
        "store_id": ctx.store_id,
        "order_count": len(orders),
        "gross": str(gross),
        "discount": str(discount),
        "net": str(net),
        "by_payment_method": {k: str(v) for k, v in by_method.items()},
        "top_products": top_products,
    }


@router.get("/analytics")
def analytics_dashboard(
    days: int = Query(default=7, ge=1, le=90),
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    """
    Multi-day analytics: revenue by day, by hour (today), top products, simple CLV proxy.
    """
    from datetime import timedelta

    today = date.today()
    start_day = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start_day, time.min)
    end_dt = datetime.combine(today, time.max)

    orders = (
        db.query(Order)
        .filter(
            Order.store_id == ctx.store_id,
            Order.status == OrderStatus.paid,
            Order.paid_at >= start_dt,
            Order.paid_at <= end_dt,
        )
        .all()
    )

    by_day: dict[str, dict] = {}
    by_hour: dict[int, Decimal] = {h: Decimal("0") for h in range(24)}
    for o in orders:
        if not o.paid_at:
            continue
        dkey = o.paid_at.date().isoformat() if hasattr(o.paid_at, "date") else str(o.paid_at)[:10]
        slot = by_day.setdefault(dkey, {"order_count": 0, "revenue": Decimal("0")})
        slot["order_count"] += 1
        slot["revenue"] += o.total
        if o.paid_at.date() == today:
            by_hour[o.paid_at.hour] = by_hour.get(o.paid_at.hour, Decimal("0")) + o.total

    # fill missing days
    day_series = []
    for i in range(days):
        d = (start_day + timedelta(days=i)).isoformat()
        slot = by_day.get(d, {"order_count": 0, "revenue": Decimal("0")})
        day_series.append(
            {
                "date": d,
                "order_count": slot["order_count"],
                "revenue": str(slot["revenue"]),
            }
        )

    top_rows = (
        db.query(
            OrderLine.product_name,
            func.sum(OrderLine.qty).label("qty"),
            func.sum(OrderLine.line_total).label("revenue"),
        )
        .join(Order, Order.id == OrderLine.order_id)
        .filter(
            Order.store_id == ctx.store_id,
            Order.status == OrderStatus.paid,
            Order.paid_at >= start_dt,
            Order.paid_at <= end_dt,
        )
        .group_by(OrderLine.product_name)
        .order_by(func.sum(OrderLine.line_total).desc())
        .limit(10)
        .all()
    )

    # CLV proxy: avg lifetime spend of customers with paid orders in window
    cust_spend: dict[str, Decimal] = {}
    for o in orders:
        if not o.customer_id:
            continue
        cust_spend[o.customer_id] = cust_spend.get(o.customer_id, Decimal("0")) + o.total
    clv_avg = (
        (sum(cust_spend.values(), Decimal("0")) / len(cust_spend)).quantize(Decimal("0.01"))
        if cust_spend
        else Decimal("0")
    )

    total_revenue = sum((o.total for o in orders), Decimal("0"))
    return {
        "store_id": ctx.store_id,
        "days": days,
        "from": start_day.isoformat(),
        "to": today.isoformat(),
        "totals": {
            "order_count": len(orders),
            "revenue": str(total_revenue),
            "customers": len(cust_spend),
            "avg_order_value": str(
                (total_revenue / len(orders)).quantize(Decimal("0.01")) if orders else Decimal("0")
            ),
            "clv_proxy_avg": str(clv_avg),
        },
        "by_day": day_series,
        "by_hour_today": [{"hour": h, "revenue": str(by_hour[h])} for h in range(24)],
        "top_products": [
            {
                "name": r.product_name,
                "qty": int(r.qty or 0),
                "revenue": str(r.revenue or 0),
            }
            for r in top_rows
        ],
    }


@router.get("/export.csv")
def export_sales_csv(
    days: int = Query(default=7, ge=1, le=90),
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    """Export paid orders as CSV (P4-M6 Excel-compatible)."""
    from datetime import timedelta

    today = date.today()
    start_day = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start_day, time.min)
    end_dt = datetime.combine(today, time.max)
    orders = (
        db.query(Order)
        .filter(
            Order.store_id == ctx.store_id,
            Order.status == OrderStatus.paid,
            Order.paid_at >= start_dt,
            Order.paid_at <= end_dt,
        )
        .order_by(Order.paid_at.asc())
        .all()
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["order_id", "paid_at", "customer_id", "subtotal", "discount", "total", "status"])
    for o in orders:
        w.writerow(
            [
                o.id,
                o.paid_at.isoformat() if o.paid_at else "",
                o.customer_id or "",
                str(o.subtotal),
                str(o.discount),
                str(o.total),
                o.status.value,
            ]
        )
    data = buf.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="sales_{days}d.csv"'},
    )


@router.get("/export.xlsx")
def export_sales_xlsx(
    days: int = Query(default=7, ge=1, le=90),
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    """
    Excel-compatible SpreadsheetML export (P5) — opens in Excel/LibreOffice
    without third-party xlsx libraries.
    """
    from datetime import timedelta
    from xml.sax.saxutils import escape

    today = date.today()
    start_day = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start_day, time.min)
    end_dt = datetime.combine(today, time.max)
    orders = (
        db.query(Order)
        .filter(
            Order.store_id == ctx.store_id,
            Order.status == OrderStatus.paid,
            Order.paid_at >= start_dt,
            Order.paid_at <= end_dt,
        )
        .order_by(Order.paid_at.asc())
        .all()
    )

    def cell(v: str, num: bool = False) -> str:
        t = "Number" if num else "String"
        return f'<Cell><Data ss:Type="{t}">{escape(v)}</Data></Cell>'

    rows_xml = [
        "<Row>"
        + cell("order_id")
        + cell("paid_at")
        + cell("customer_id")
        + cell("subtotal")
        + cell("discount")
        + cell("total")
        + cell("status")
        + "</Row>"
    ]
    for o in orders:
        rows_xml.append(
            "<Row>"
            + cell(o.id)
            + cell(o.paid_at.isoformat() if o.paid_at else "")
            + cell(o.customer_id or "")
            + cell(str(o.subtotal), num=True)
            + cell(str(o.discount), num=True)
            + cell(str(o.total), num=True)
            + cell(o.status.value)
            + "</Row>"
        )

    xml = (
        '<?xml version="1.0"?>\n'
        '<?mso-application progid="Excel.Sheet"?>\n'
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" '
        'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">\n'
        f'<Worksheet ss:Name="Sales_{days}d"><Table>\n'
        + "\n".join(rows_xml)
        + "\n</Table></Worksheet>\n</Workbook>\n"
    )
    data = xml.encode("utf-8")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.ms-excel",
        headers={"Content-Disposition": f'attachment; filename="sales_{days}d.xls"'},
    )


def _eod_lines(db: Session, store_id: str, day: date) -> tuple[list[str], Decimal, int]:
    start = datetime.combine(day, time.min)
    end = datetime.combine(day, time.max)
    orders = (
        db.query(Order)
        .filter(
            Order.store_id == store_id,
            Order.status == OrderStatus.paid,
            Order.paid_at >= start,
            Order.paid_at <= end,
        )
        .all()
    )
    net = sum((o.total for o in orders), Decimal("0"))
    lines = [
        "===== BAO CAO CUOI NGAY =====",
        f"Ngay: {day.isoformat()}",
        f"Store: {store_id}",
        f"So don: {len(orders)}",
        f"Doanh thu net: {net}",
        "----- Chi tiet -----",
    ]
    for o in orders[:80]:
        lines.append(
            f"{o.id[:8]}  {o.total}  {(o.paid_at.isoformat() if o.paid_at else '')[:19]}"
        )
    lines.append("===== HET =====")
    return lines, net, len(orders)


@router.get("/export.txt")
def export_sales_txt(
    report_date: date | None = Query(default=None, alias="date"),
    ctx: AuthContext = Depends(require_any("manager", "admin", "cashier")),
    db: Session = Depends(get_db),
):
    """Printable end-of-day text report (PDF-ready plain text)."""
    day = report_date or date.today()
    lines, _net, _n = _eod_lines(db, ctx.store_id, day)
    return PlainTextResponse("\n".join(lines), media_type="text/plain; charset=utf-8")


@router.get("/export.pdf")
def export_sales_pdf(
    report_date: date | None = Query(default=None, alias="date"),
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    """EOD PDF export (P4-M6) — minimal PDF without third-party libs."""
    from pos.services.pdf_report import text_report_to_pdf

    day = report_date or date.today()
    lines, _net, _n = _eod_lines(db, ctx.store_id, day)
    pdf = text_report_to_pdf(lines, title=f"EOD {day.isoformat()}")
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="eod_{day.isoformat()}.pdf"'},
    )



