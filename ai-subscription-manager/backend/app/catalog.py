from fastapi import APIRouter, Request, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, or_, cast, String
from sqlalchemy.inspection import inspect
from .auth import authenticated
from .models import Customer, Supplier, Product, Service, Sale, utcnow
from .schemas import CustomerInput, SupplierInput, ProductInput
from .errors import ApiError, missing

router = APIRouter(prefix="/api", dependencies=[Depends(authenticated)])


def encode(item):
    return jsonable_encoder(
        {c.key: getattr(item, c.key) for c in inspect(item).mapper.column_attrs}
    )


def get(db, model, identifier):
    item = db.get(model, identifier)
    if not item:
        raise missing()
    return item


def paged(items, request):
    page = (
        max(1, int(request.query_params.get("page", "1")))
        if request.query_params.get("page", "1").isdigit()
        else 1
    )
    count = len(items)
    return {
        "count": count,
        "next": page + 1 if count > page * 25 else None,
        "previous": page - 1 if page > 1 else None,
        "results": items[(page - 1) * 25 : page * 25],
    }


def validate(schema, data):
    return schema.model_validate(data).model_dump()


def register_resource(path, model, schema):
    def listing(request: Request, q: str = ""):
        with request.app.state.db.read() as db:
            query = select(model).order_by(model.id.desc())
            if q:
                filters = [model.name.contains(q, autoescape=True)]
                if model is Customer:
                    filters.append(cast(model.contacts, String).contains(q, autoescape=True))
                query = query.where(or_(*filters))
            result = [encode(item) for item in db.scalars(query)]
            if model is Product:
                names = {s.id: s.name for s in db.scalars(select(Supplier))}
                for item in result:
                    item["supplier_name"] = names.get(item["supplier_id"], "")
            return paged(result, request)

    def detail(identifier: int, request: Request):
        with request.app.state.db.read() as db:
            return encode(get(db, model, identifier))

    def create(request: Request, data: dict):
        values = validate(schema, data)
        with request.app.state.db.write() as db:
            if model is Product:
                get(db, Supplier, values["supplier_id"])
            item = model(**values)
            db.add(item)
            db.flush()
            return encode(item)

    def update(identifier: int, request: Request, data: dict):
        with request.app.state.db.write() as db:
            item = get(db, model, identifier)
            merged = encode(item) | data
            values = validate(schema, merged)
            if model is Product:
                get(db, Supplier, values["supplier_id"])
            for key, value in values.items():
                setattr(item, key, value)
            if model is Customer and "archived" in data:
                item.archived_at = utcnow() if data["archived"] else None
            db.flush()
            return encode(item)

    def remove(identifier: int, request: Request):
        with request.app.state.db.write() as db:
            item = get(db, model, identifier)
            refs = []
            if model is Customer:
                refs = [select(Service.id).where(Service.customer_id == identifier)]
            elif model is Supplier:
                refs = [select(Product.id).where(Product.supplier_id == identifier)]
            else:
                refs = [
                    select(Service.id).where(Service.product_id == identifier),
                    select(Sale.id).where(Sale.product_id == identifier),
                ]
            if any(db.scalar(q.limit(1)) for q in refs):
                raise ApiError("referenced", "已有业务记录，请使用归档或停用", 409)
            db.delete(item)
        return {"deleted": True}

    for fn, suffix, methods, code in [
        (listing, "/", ["GET"], 200),
        (create, "/", ["POST"], 201),
        (detail, "/{identifier}/", ["GET"], 200),
        (update, "/{identifier}/", ["PATCH"], 200),
        (remove, "/{identifier}/", ["DELETE"], 200),
    ]:
        router.add_api_route(
            "/" + path + suffix,
            fn,
            methods=methods,
            status_code=code,
            name=f"{path}_{fn.__name__}",
        )


register_resource("customers", Customer, CustomerInput)
register_resource("suppliers", Supplier, SupplierInput)
register_resource("products", Product, ProductInput)
