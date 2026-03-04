import os
from flask import Flask, session
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy


load_dotenv()

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)

    # PostgreSQL 連接設定
    # 確保使用你的現有資料庫連接字串
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "pf9Wkove4IKEAXvy-cQkeDPhv9Cb3Ag-wyJILbq_dFw"
    )

    # 初始化 SQLAlchemy
    db.init_app(app)

    # 註冊藍圖
    from warehousing_system.routes import pages
    app.register_blueprint(pages)

    # 注入待審核數量到所有模板
    @app.context_processor
    def inject_pending_count():
        if session.get('is_approver'):
            from warehousing_system.models import Withdrawal
            count = Withdrawal.query.filter_by(status='pending').count()
        else:
            count = 0
        return dict(pending_count=count)

    return app
