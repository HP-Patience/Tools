import hashlib, json
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Request, Depends
from sqlalchemy import select, update
from .auth import authenticated
from .catalog import encode, get, paged
from .models import Customer, Supplier, Product, Service, Sale, Reminder, utcnow
from .schemas import SaleInput, VoidInput, CorrectionInput
from .calendar import add_term, service_status, today
from .errors import ApiError

router = APIRouter(prefix="/api", dependencies=[Depends(authenticated)])


def state(service):
    return {
        "expires_on": service.expires_on.isoformat() if service.expires_on else None,
        "ended": bool(service.ended_at),
        "purchased_quota": service.purchased_quota,
        "product_id": service.product_id,
    }


def cancel_old(db, service):
    query = update(Reminder).where(Reminder.service_id == service.id, Reminder.status == "pending")
    if not service.ended_at:
        query = (
            query.where(Reminder.target_expiry != service.expires_on)
            if service.expires_on
            else query
        )
    db.execute(query.values(status="cancelled"))


def check_revision(service, revision):
    if service.revision != revision:
        raise ApiError("stale_service", "服务已经更新，请刷新后核对再提交", 409)


def transact(database, data, kind="purchase", service_id=None):
    payload = data.model_dump(mode="json") | {"kind": kind, "service_id": service_id}
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    with database.write() as db:
        prior = db.scalar(select(Sale).where(Sale.submission_id == str(data.submission_id)))
        if prior:
            if prior.payload_hash != fingerprint:
                raise ApiError("submission_conflict", "相同提交标识不能用于不同交易", 409)
            return encode(prior)
        customer = get(db, Customer, data.customer_id)
        product = get(db, Product, data.product_id)
        supplier = get(db, Supplier, product.supplier_id)
        if customer.archived_at or not product.is_active or not supplier.is_active:
            raise ApiError("inactive", "客户、商品或渠道已停用")
        if service_id:
            service = get(db, Service, service_id)
            if service.customer_id != data.customer_id:
                raise ApiError("customer_mismatch", "客户与服务不匹配")
            check_revision(service, data.expected_revision)
            before = state(service)
            base = (
                max(service.expires_on or data.sold_on, data.sold_on)
                if kind == "renewal"
                else service.started_on
            )
            service.revision += 1
            service.ended_at = None
        else:
            base = data.started_on or data.sold_on
            service = Service(
                customer_id=customer.id,
                product_id=product.id,
                started_on=base,
                identifier=data.identifier,
                notes=data.notes,
                purchased_quota="0",
                revision=1,
            )
            db.add(service)
            db.flush()
            before = {}
        expiry = data.expires_on
        if expiry is None and data.term_count:
            try:
                expiry = add_term(base, data.term_count, data.term_unit)
            except (ValueError, OverflowError):
                raise ApiError("invalid_term", "期限超出支持的日期范围")
        if kind == "renewal" and expiry is None:
            raise ApiError("missing_expiry", "续费应填写期限或到期日")
        if expiry and expiry < base:
            raise ApiError("invalid_expiry", "到期日期不能早于本次服务开始日期")
        if kind == "topup":
            if data.quota_amount is None:
                raise ApiError("missing_quota", "追加额度必须填写额度和单位")
            if service.quota_unit and service.quota_unit != data.quota_unit:
                raise ApiError("quota_unit", "不能混合不同额度单位")
            if expiry is not None:
                service.expires_on = expiry
        else:
            service.expires_on = expiry
            service.product_id = product.id
        if data.quota_amount is not None:
            if service.quota_unit and service.quota_unit != data.quota_unit:
                raise ApiError("quota_unit", "不能混合不同额度单位")
            service.purchased_quota = str(
                Decimal(service.purchased_quota) + Decimal(data.quota_amount)
            )
            service.quota_unit = data.quota_unit
        snapshot = {
            "customer_name": customer.name,
            "supplier_name": supplier.name,
            "product_name": product.name,
            "platform": product.platform,
            "plan": product.plan,
            "delivery": product.delivery,
            "source_name": product.source_name,
            "source_url": product.source_url,
            "warranty_notes": product.warranty_notes,
            "started_on": base.isoformat(),
            "expires_on": expiry.isoformat() if expiry else None,
            "term_count": data.term_count,
            "term_unit": data.term_unit,
            "quota_amount": data.quota_amount,
            "quota_unit": data.quota_unit,
            "notes": data.notes,
        }
        sale = Sale(
            customer_id=customer.id,
            service_id=service.id,
            product_id=product.id,
            kind=kind,
            sold_on=data.sold_on,
            cost_fen=data.cost_fen,
            price_fen=data.price_fen,
            snapshot=snapshot,
            before_state=before,
            after_state=state(service),
            submission_id=str(data.submission_id),
            payload_hash=fingerprint,
        )
        db.add(sale)
        cancel_old(db, service)
        db.flush()
        return encode(sale)


@router.post("/sales/", status_code=201)
def purchase(request: Request, data: SaleInput):
    return transact(request.app.state.db, data)


@router.post("/services/{identifier}/renew/", status_code=201)
def renew(identifier: int, request: Request, data: SaleInput):
    return transact(request.app.state.db, data, "renewal", identifier)


@router.post("/services/{identifier}/topup/", status_code=201)
def topup(identifier: int, request: Request, data: SaleInput):
    return transact(request.app.state.db, data, "topup", identifier)


def service_output(db, item):
    data = encode(item)
    data["status"] = service_status(item)
    data["customer_name"] = get(db, Customer, item.customer_id).name
    data["contacts"] = get(db, Customer, item.customer_id).contacts
    product = get(db, Product, item.product_id)
    data["product_name"] = product.name
    data["supplier_id"] = product.supplier_id
    data["supplier_name"] = get(db, Supplier, product.supplier_id).name
    return data


@router.get("/services/")
def services(request: Request, expiry_from: date | None = None, expiry_to: date | None = None):
    with request.app.state.db.read() as db:
        values = [
            service_output(db, item)
            for item in db.scalars(select(Service).order_by(Service.id.desc()))
        ]
        q = request.query_params
        for key in ("customer_id", "product_id", "supplier_id"):
            if q.get(key):
                values = [v for v in values if str(v[key]) == q[key]]
        if q.get("status"):
            values = [v for v in values if v["status"] == q["status"]]
        if expiry_from:
            values = [
                v for v in values if v["expires_on"] and v["expires_on"] >= expiry_from.isoformat()
            ]
        if expiry_to:
            values = [
                v for v in values if v["expires_on"] and v["expires_on"] <= expiry_to.isoformat()
            ]
        if q.get("q"):
            values = [
                v
                for v in values
                if q["q"].lower()
                in (v["customer_name"] + v["product_name"] + v["identifier"]).lower()
            ]
        return paged(values, request)


@router.get("/services/{identifier}/")
def service_detail(identifier: int, request: Request):
    with request.app.state.db.read() as db:
        return service_output(db, get(db, Service, identifier))


@router.get("/sales/")
def sales(request: Request, sold_from: date | None = None, sold_to: date | None = None):
    with request.app.state.db.read() as db:
        query = select(Sale).order_by(Sale.id.desc())
        q = request.query_params
        for key in ("customer_id", "product_id", "service_id"):
            if q.get(key):
                query = query.where(getattr(Sale, key) == q[key])
        if sold_from:
            query = query.where(Sale.sold_on >= sold_from)
        if sold_to:
            query = query.where(Sale.sold_on <= sold_to)
        values = [encode(item) for item in db.scalars(query)]
        if q.get("supplier_id"):
            ids = set(db.scalars(select(Product.id).where(Product.supplier_id == q["supplier_id"])))
            values = [v for v in values if v["product_id"] in ids]
        return paged(values, request)


@router.get("/sales/{identifier}/")
def sale_detail(identifier: int, request: Request):
    with request.app.state.db.read() as db:
        return encode(get(db, Sale, identifier))


def edit_sale(identifier, request, data, void):
    with request.app.state.db.write() as db:
        sale = get(db, Sale, identifier)
        service = get(db, Service, sale.service_id)
        check_revision(service, data.expected_revision)
        if sale.voided_at:
            raise ApiError("voided", "交易已作废", 409)
        if data.service_state.expires_on and data.service_state.expires_on < service.started_on:
            raise ApiError("invalid_expiry", "到期日期不能早于服务开始日期")
        history = list(sale.snapshot.get("correction_history", []))
        history.append(
            {
                "at": utcnow().isoformat(),
                "cost_fen": sale.cost_fen,
                "price_fen": sale.price_fen,
                "sold_on": sale.sold_on.isoformat(),
                "service": state(service),
                "reason": data.reason,
                "action": "void" if void else "correct",
            }
        )
        sale.snapshot = {**sale.snapshot, "correction_history": history}
        if void:
            sale.voided_at = utcnow()
            sale.void_reason = data.reason
        else:
            sale.cost_fen = data.cost_fen
            sale.price_fen = data.price_fen
            sale.sold_on = data.sold_on
        service.expires_on = data.service_state.expires_on
        service.ended_at = utcnow() if data.service_state.ended else None
        service.purchased_quota = data.service_state.purchased_quota
        service.revision += 1
        cancel_old(db, service)
        db.flush()
        return encode(sale)


@router.post("/sales/{identifier}/void/")
def void_sale(identifier: int, request: Request, data: VoidInput):
    return edit_sale(identifier, request, data, True)


@router.post("/sales/{identifier}/correct/")
def correct_sale(identifier: int, request: Request, data: CorrectionInput):
    return edit_sale(identifier, request, data, False)


@router.post("/services/{identifier}/end/")
def end(identifier: int, request: Request, data: dict):
    with request.app.state.db.write() as db:
        item = get(db, Service, identifier)
        check_revision(item, data.get("expected_revision"))
        item.ended_at = utcnow()
        item.revision += 1
        cancel_old(db, item)
        db.flush()
        return service_output(db, item)


@router.get("/dashboard/")
def dashboard(request: Request, month: str = ""):
    try:
        start = date.fromisoformat(month + "-01") if month else today().replace(day=1)
    except ValueError:
        raise ApiError("month", "月份格式应为 YYYY-MM")
    end = add_term(start, 1, "month")
    with request.app.state.db.read() as db:
        records = list(
            db.scalars(
                select(Sale).where(
                    Sale.sold_on >= start, Sale.sold_on < end, Sale.voided_at.is_(None)
                )
            )
        )
        revenue = sum(s.price_fen for s in records)
        cost = sum(s.cost_fen for s in records)
        active = list(db.scalars(select(Service).where(Service.ended_at.is_(None))))
        due = [
            service_output(db, s)
            for s in active
            if s.expires_on and s.started_on <= today() and (s.expires_on - today()).days <= 3
        ]
        due.sort(key=lambda s: s["expires_on"])
        return {
            "month": start.strftime("%Y-%m"),
            "totals": {
                "revenue_fen": revenue,
                "cost_fen": cost,
                "profit_fen": revenue - cost,
            },
            "sale_count": len(records),
            "customer_count": db.scalar(select(__import__("sqlalchemy").func.count(Customer.id))),
            "service_count": len(active),
            "due": due,
            "recent_sales": [
                encode(s) for s in db.scalars(select(Sale).order_by(Sale.id.desc()).limit(6))
            ],
        }
