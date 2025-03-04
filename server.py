from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2

app = Flask(__name__)
CORS(app)  # 允许跨域请求（前端调用 API）

# 数据库配置
DB_CONFIG = {
    "dbname": "Library",
    "user": "postgres",
    "password": "252436710",
    "host": "localhost",
    "port": "5432"
}

# 获取数据库连接
def get_connection():
    return psycopg2.connect(**DB_CONFIG)

# 1️⃣ 登录 API
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    user_id = data.get("user_id")
    password = data.get("password")
    role = data.get("role")  # "employee" or "member"

    conn = get_connection()
    cur = conn.cursor()

    if role == "employee":
        query = "SELECT name FROM public.employee WHERE employeeid = %s AND password = %s"
    else:
        query = "SELECT name FROM public.member WHERE memberid = %s AND password = %s"

    cur.execute(query, (user_id, password))
    result = cur.fetchone()
    cur.close()
    conn.close()

    if result:
        return jsonify({"status": "success", "name": result[0]})
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401

# 2️⃣ 获取书籍列表 API
@app.route("/books", methods=["GET"])
def get_books():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT isbn, title, publishyear, status FROM public.book")
    books = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify([{"isbn": row[0], "title": row[1], "year": row[2], "status": row[3]} for row in books])

# 3️⃣ 借书 API
@app.route("/borrow", methods=["POST"])
def borrow_book():
    data = request.json
    member_id = data.get("member_id")
    isbn = data.get("isbn")

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO public.borrow (memberid, isbn, borrowdate, duedate, returndate, createdat, updatedat)
            VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_DATE + 30, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (member_id, isbn))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "success", "message": "Book borrowed successfully."})
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 400

# 4️⃣ 归还书籍 API
@app.route("/return", methods=["POST"])
def return_book():
    data = request.json
    borrow_id = data.get("borrow_id")

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE public.borrow
            SET returndate = CURRENT_TIMESTAMP
            WHERE borrowid = %s
        """, (borrow_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "success", "message": "Book returned successfully."})
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 400

# 启动服务器
if __name__ == "__main__":
    app.run(debug=True, port=5000)
