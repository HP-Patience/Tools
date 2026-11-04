import argparse, getpass, json, sqlite3
from pathlib import Path
from datetime import timedelta
from sqlalchemy import select
from .config import Settings
from .db import Database
from .models import Owner, Customer, Supplier, Product
from .auth import hash_password
from .calendar import today


def backup(source, destination):
    target = Path(destination)
    if target.exists():
        raise ValueError("备份目标已存在，拒绝覆盖")
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as original, sqlite3.connect(target) as copied:
        original.backup(copied)
        if copied.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("备份完整性检查失败")
    return str(target)


def seed_demo(db):
    from .billing import transact
    from .schemas import SaleInput
    from uuid import uuid4

    with db.write() as session:
        if session.scalar(select(Customer.id).limit(1)):
            raise ValueError("演示数据只允许写入空业务数据库")
        supplier = Supplier(
            name="示例供货渠道",
            url="https://example.com",
            contact_details="演示资料，请替换为真实上游",
            notes="仅供本地体验",
        )
        session.add(supplier)
        session.flush()
        products = [
            Product(
                supplier_id=supplier.id,
                name=n,
                platform=p,
                plan=n,
                delivery=d,
                cost_fen=c,
                price_fen=s,
                term_count=1,
                term_unit="month",
            )
            for n, p, d, c, s in [
                ("ChatGPT Plus", "OpenAI", "代充", 6800, 12800),
                ("Claude Pro", "Anthropic", "独立账号", 8500, 14800),
                ("ChatGPT Pro", "OpenAI", "团队席位", 65000, 89000),
            ]
        ]
        session.add_all(products)
        customers = [
            Customer(
                name=n,
                contacts=[{"kind": "wechat", "value": "demo_" + str(i + 1)}],
                notes="演示客户",
            )
            for i, n in enumerate(["林同学", "陈先生", "周女士", "许先生"])
        ]
        session.add_all(customers)
        session.flush()
        pairs = [
            (
                c.id,
                products[i % 3].id,
                products[i % 3].cost_fen,
                products[i % 3].price_fen,
                i,
            )
            for i, c in enumerate(customers)
        ]
    for cid, pid, cost, price, i in pairs:
        transact(
            db,
            SaleInput(
                customer_id=cid,
                product_id=pid,
                cost_fen=cost,
                price_fen=price,
                sold_on=today() - timedelta(days=20),
                started_on=today() - timedelta(days=20),
                expires_on=today() + timedelta(days=[3, 0, -2, 18][i]),
                submission_id=uuid4(),
                identifier="演示服务 " + str(i + 1),
            ),
        )


def main():
    parser = argparse.ArgumentParser(description="续订 · 后台维护命令")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("bootstrap-owner").add_argument("--username", default="owner")
    subs.add_parser("run-reminders")
    subs.add_parser("seed-demo")
    subs.add_parser("backup").add_argument("destination")
    args = parser.parse_args()
    settings = Settings()
    db = Database(settings.database_path)
    if args.command == "bootstrap-owner":
        password = getpass.getpass("设置管理员密码（至少12位）：")
        if len(password) < 12:
            parser.error("密码至少12位")
        if password != getpass.getpass("再次输入："):
            parser.error("两次密码不一致")
        with db.write() as session:
            if session.get(Owner, 1):
                parser.error("管理员已存在，拒绝创建第二个账号")
            session.add(Owner(id=1, username=args.username, password_hash=hash_password(password)))
        print("管理员已创建")
    elif args.command == "backup":
        print(backup(settings.database_path, args.destination))
    elif args.command == "seed-demo":
        if settings.production:
            parser.error("生产环境禁止导入演示数据")
        seed_demo(db)
        print("已写入演示数据")
    else:
        from .reminders import run_cycle

        print(json.dumps(run_cycle(db, settings), ensure_ascii=False))


if __name__ == "__main__":
    main()
