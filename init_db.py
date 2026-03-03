"""
資料庫初始化腳本
"""
import pandas as pd
from warehousing_system import db, create_app
from warehousing_system.models import User, ProductCatalog, PackingList, Inventory, Withdrawal, Approval

def import_product_catalog_from_excel(file_path):
    """
    從 Excel 匯入 ProductCatalog
    Excel 必須包含欄位：
        - parent_item_name
        - child_item_name
    """

    app = create_app()
    with app.app_context():

        df = pd.read_excel(file_path)
        df.columns = df.columns.str.strip().str.lower()

        # ✅ 檢查必要欄位
        required_columns = {"parent_item_name", "child_item_name"}
        if not required_columns.issubset(df.columns):
            raise ValueError(
                f"Excel 必須包含欄位：{required_columns}，目前欄位為：{set(df.columns)}"
            )

        inserted = 0
        skipped = 0

        for idx, row in df.iterrows():
            parent_item_name = str(row["parent_item_name"]).strip() \
                if pd.notna(row["parent_item_name"]) else ""
            child_item_name = str(row["child_item_name"]).strip() \
                if pd.notna(row["child_item_name"]) else ""

            # 跳過空白
            if not parent_item_name or not child_item_name:
                skipped += 1
                continue

            # 檢查是否已存在
            exists = ProductCatalog.query.filter_by(
                parent_item_name=parent_item_name,
                child_item_name=child_item_name
            ).first()

            if exists:
                skipped += 1
                print(f"⚠ 已存在，略過：{parent_item_name} → {child_item_name}")
                continue

            db.session.add(ProductCatalog(
                parent_item_name=parent_item_name,
                child_item_name=child_item_name
            ))

            inserted += 1

        db.session.commit()

        print("=====================================")
        print(f"✓ 匯入完成")
        print(f"  新增筆數：{inserted}")
        print(f"  略過筆數：{skipped}")
        print("=====================================")
    
def init_database():
    app = create_app()
    with app.app_context():
        print("正在建立資料庫表格...")
        db.create_all()
        print("✓ 資料庫表格建立完成")
        
        print("\n正在設定審核人員...")
        approver_emails = ['novascope.dba@Novascopedx.com']
        for email in approver_emails:
            user = User.query.filter_by(email=email).first()
            if user:
                user.is_approver = True
                print(f"✓ 已將 {email} 設為審核人員")
            else:
                print(f"⚠ 找不到使用者 {email}，請先登入系統")
        db.session.commit()
        print("\n✓ 資料庫初始化完成！")


def add_product(parent_item_name, child_item_name):
    app = create_app()
    with app.app_context():
        exists = ProductCatalog.query.filter_by(
            parent_item_name=parent_item_name, child_item_name=child_item_name
        ).first()
        if exists:
            print(f"⚠ 已存在: {parent_item_name} → {child_item_name}")
            return False
        db.session.add(ProductCatalog(parent_item_name=parent_item_name, child_item_name=child_item_name))
        db.session.commit()
        print(f"✓ 已新增: {parent_item_name} → {child_item_name}")
        return True


def list_products():
    app = create_app()
    with app.app_context():
        products = ProductCatalog.query.order_by(
            ProductCatalog.parent_item_name, ProductCatalog.child_item_name
        ).all()
        current = None
        for p in products:
            if p.parent_item_name != current:
                current = p.parent_item_name
                print(f"\n📦 {current}")
                print("  " + "-" * 40)
            print(f"  ├── {p.child_item_name}")


def set_approver(email, is_approver=True):
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"⚠ 找不到使用者 {email}")
            return False
        user.is_approver = is_approver
        db.session.commit()
        action = "設為" if is_approver else "取消"
        print(f"✓ 已{action}審核人員: {email}")
        return True


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'init':
            init_database()
        elif cmd == 'list':
            list_products()
        elif cmd == 'add' and len(sys.argv) == 4:
            add_product(sys.argv[2], sys.argv[3])
        elif cmd == 'approver' and len(sys.argv) == 3:
            set_approver(sys.argv[2])
        elif cmd == 'import_excel' and len(sys.argv) == 3:
            # ⭐ 新增：從 Excel 匯入 ProductCatalog
            import_product_catalog_from_excel(sys.argv[2])
        else:
            print("使用方法:")
            print("  python init_db.py init                                # 初始化資料庫")
            print("  python init_db.py list                                # 列出所有產品")
            print("  python init_db.py add '貨物名稱' '品項名稱'            # 新增品項")
            print("  python init_db.py approver email                      # 設定審核人員")
            print("  python init_db.py import_excel path/to/file.xlsx      # 從 Excel 匯入產品目錄")
    else:
        init_database()