from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2

app = Flask(__name__)
CORS(app)

# Database configuration (please adjust according to your actual settings)
DB_CONFIG = {
    "dbname": "Library",
    "user": "postgres",
    "password": "admin",
    "host": "localhost",
    "port": "5432"
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

# 1️⃣ Login API
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    user_id = data.get("user_id")
    password = data.get("password")
    role = data.get("role")  # "employee" or "member"

    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT public.process_expired_reservations()")
    conn.commit()

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

# 2️⃣ Get Books List API
@app.route("/books", methods=["GET"])
def get_books():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT isbn, title, publishyear, status FROM public.book")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    books = [{"isbn": row[0], "title": row[1], "year": row[2], "status": row[3]} for row in rows]
    return jsonify(books)

# 3️⃣ Borrow Book API
@app.route("/borrow", methods=["POST"])
def borrow_book():
    data = request.json
    member_id = int(data.get("member_id"))
    isbn = data.get("isbn", "").strip()
    conn = get_connection()
    cur = conn.cursor()
    
    # Check if the member has already borrowed this ISBN and not returned (to prevent duplicate borrowing)
    cur.execute("""
        SELECT 1
        FROM public.borrow
        WHERE memberid = %s AND isbn = %s AND returndate IS NULL
    """, (member_id, isbn))
    if cur.fetchone() is not None:
        cur.close()
        conn.close()
        return jsonify({
            "status": "error", 
            "message": "You have already borrowed this book and have not returned it yet."
        }), 400

    # Check if the book exists and its current status
    cur.execute("SELECT status FROM public.book WHERE isbn = %s", (isbn,))
    book = cur.fetchone()
    if not book:
        cur.close()
        conn.close()
        return jsonify({
            "status": "error", 
            "message": "Book does not exist."
        }), 404

    # Check if there is a reservation record marked as Reserved (i.e. reservation priority)
    cur.execute("""
        SELECT memberid
        FROM public.reservation
        WHERE isbn = %s 
          AND status = 'Reserved'
          AND pickupdeadline IS NOT NULL
          AND pickupdeadline > CURRENT_TIMESTAMP
        ORDER BY queuenumber ASC
        LIMIT 1
    """, (isbn,))
    reserved = cur.fetchone()
    if reserved:
        # If there is a reservation and the current member is not the one reserved, then disallow borrowing
        if reserved[0] != member_id:
            cur.close()
            conn.close()
            return jsonify({
                "status": "error", 
                "message": "This book is reserved for another member."
            }), 400

    # Check borrowing limit
    cur.execute("""
        SELECT COUNT(borrowid)
        FROM public.borrow 
        WHERE memberid = %s AND returndate IS NULL
    """, (member_id,))
    active_borrow_count = cur.fetchone()[0]
    if active_borrow_count >= 5:
        cur.close()
        conn.close()
        return jsonify({
            "status": "error", 
            "message": "You already have 5 active borrowed books. Please return some books before borrowing more."
        }), 400

    try:
        # Insert borrowing record, and rely on triggers to automatically assign an available copy
        cur.execute("""
            INSERT INTO public.borrow 
            (memberid, isbn, borrowdate, duedate, returndate, createdat, updatedat)
            VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_DATE + 30, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING borrowid, copyid
        """, (member_id, isbn))
        result = cur.fetchone()
        conn.commit()
        borrow_id, copy_id = result[0], result[1]
        cur.close()
        conn.close()
        return jsonify({
            "status": "success", 
            "borrow_id": borrow_id, 
            "assigned_copy": copy_id
        })
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        if "No available copy" in str(e):
            error_message = "There is no available copy of the book at this time."
        else:
            error_message = "Failed to borrow book. Please try again later."
        return jsonify({
            "status": "error", 
            "message": error_message
        }), 500

# 4️⃣ Return Book API
@app.route("/return", methods=["POST"])
def return_book():
    data = request.json
    borrow_id = data.get("borrow_id")
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Update return date
        cur.execute("""
            UPDATE public.borrow
            SET returndate = CURRENT_TIMESTAMP
            WHERE borrowid = %s
        """, (borrow_id,))
        # According to return logic: check if there is an active reservation and update the corresponding copy status
        cur.execute("SELECT isbn, copyid FROM public.borrow WHERE borrowid = %s", (borrow_id,))
        row = cur.fetchone()
        if row:
            isbn, copyid = row
            # Find the active reservation record for this book (ordered by queue)
            cur.execute("""
                SELECT reservationid, memberid 
                FROM public.reservation 
                WHERE isbn = %s AND status = 'Active'
                ORDER BY queuenumber ASC, reservationdate ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            """, (isbn,))
            reservation = cur.fetchone()
            if reservation:
                reservation_id, reserved_member_id = reservation
                # Update reservation record and copy status
                cur.execute("""
                    UPDATE public.reservation
                    SET status = 'Reserved',
                        pickupdeadline = CURRENT_TIMESTAMP + INTERVAL '3 days',
                        updatedat = CURRENT_TIMESTAMP
                    WHERE reservationid = %s
                """, (reservation_id,))
                cur.execute("""
                    UPDATE public.bookcopy
                    SET status = 'Reserved', updatedat = CURRENT_TIMESTAMP
                    WHERE copyid = %s
                """, (copyid,))
            else:
                cur.execute("""
                    UPDATE public.bookcopy
                    SET status = 'Available', updatedat = CURRENT_TIMESTAMP
                    WHERE copyid = %s
                """, (copyid,))
            # Update book status
            cur.execute("""
                WITH status_summary AS (
                    SELECT COUNT(*) FILTER (WHERE status = 'Available') AS available
                    FROM public.bookcopy
                    WHERE isbn = %s
                )
                UPDATE public.book
                SET status = CASE WHEN (SELECT available FROM status_summary) > 0 THEN 'Available' ELSE 'Unavailable' END,
                    updatedat = CURRENT_TIMESTAMP
                WHERE isbn = %s
            """, (isbn, isbn))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "success", "message": "Book returned successfully."})
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 400

# 5️⃣ Add Book API
@app.route("/addBook", methods=["POST"])
def add_book():
    data = request.json
    employee_id = data.get("employee_id")
    isbn = data.get("isbn")
    title = data.get("title")          # Only required for new books
    publishyear = data.get("publishyear")  # Only required for new books
    authors = data.get("authors", [])     # Only required for new books
    categories = data.get("categories", [])  # Only required for new books
    copies = data.get("copies", 1)        # Default is 1 copy

    conn = get_connection()
    cur = conn.cursor()
    try:
        # ==================== 1. Verify Employee Permissions ====================
        cur.execute("SELECT 1 FROM public.employee WHERE employeeid = %s", (employee_id,))
        if not cur.fetchone():
            return jsonify({"status": "error", "message": "Employee does not exist or is not authorized"}), 403

        # ==================== 2. Check if the book already exists ====================
        cur.execute("SELECT isbn FROM public.book WHERE isbn = %s", (isbn,))
        existing_book = cur.fetchone()
        copy_ids = []

        if not existing_book:
            # ========== Scenario 1: Add New Book + Copy ==========
            # ---- 2.1 Verify required fields for new book ----
            if not title or not publishyear:
                return jsonify({"status": "error", "message": "New books must have a title and publication year"}), 400
            if not authors and not categories:
                return jsonify({"status": "error", "message": "New books must have at least one author or category"}), 400
            
            # ---- 2.2 Insert new book ----
            try:
                cur.execute("""INSERT INTO public.book (isbn, title, publishyear, status, employeeid, createdat, updatedat)
                VALUES (%s, %s, %s, 'Available', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (isbn, title, publishyear, employee_id))
            except Exception as e:
                return jsonify({"status": "error", "message": f"Failed to insert new book: {str(e)}"}), 400
            
            # ---- 2.3 Process authors and categories ----
            # Process authors
            for author in authors:
                author = author.strip()
                if not author:
                    continue
                # Check if exists (case-insensitive)
                cur.execute("SELECT authorid FROM public.author WHERE LOWER(name) = LOWER(%s)", (author,))
                result = cur.fetchone()
                if result:
                    authorid = result[0]
                else:
                    # Create new author
                    cur.execute("""
                        INSERT INTO public.author (name, employeeid)
                        VALUES (%s, %s) RETURNING authorid
                    """, (author, employee_id))
                    authorid = cur.fetchone()[0]
                # Associate book with author
                cur.execute("INSERT INTO public.book_author (isbn, authorid) VALUES (%s, %s)", (isbn, authorid))
            
            # Process categories (similar logic to authors)
            for category in categories:
                category = category.strip()
                if not category:
                    continue
                cur.execute("SELECT categoryid FROM public.category WHERE LOWER(name) = LOWER(%s)", (category,))
                result = cur.fetchone()
                if result:
                    categoryid = result[0]
                else:
                    cur.execute("""
                        INSERT INTO public.category (name, employeeid)
                        VALUES (%s, %s) RETURNING categoryid
                    """, (category, employee_id))
                    categoryid = cur.fetchone()[0]
                cur.execute("INSERT INTO public.book_category (isbn, categoryid) VALUES (%s, %s)", (isbn, categoryid))

        # ==================== 3. Process Copies (for both new and existing books) ==================== 
        # ---- 3.1 Verify number of copies ----
        try:
            copies = int(copies)
            if copies < 1:
                raise ValueError
        except ValueError:
            return jsonify({"status": "error", "message": "Number of copies must be an integer greater than 0"}), 400
        
        # ---- 3.2 Insert copy records ----
        for _ in range(copies):
            cur.execute("""
                INSERT INTO public.bookcopy (isbn, status, createdat, updatedat)
                VALUES (%s, 'Available', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING copyid
            """, (isbn,))
            copy_ids.append(cur.fetchone()[0])
        
        # ==================== 4. Automatically assign copies to reservations ====================
        try:
            # Query valid reservations (Active status sorted by queue)
            cur.execute("""
                SELECT reservationid, memberid 
                FROM public.reservation 
                WHERE isbn = %s AND status = 'Active'
                ORDER BY queuenumber ASC, reservationdate ASC
                FOR UPDATE SKIP LOCKED  -- Lock records to prevent concurrent conflicts
            """, (isbn,))
            reservations = cur.fetchall()
            
            # Assign copies (minimum of available copies and reservations)
            assign_count = min(len(copy_ids), len(reservations))
            for i in range(assign_count):
                res_id, member_id = reservations[i]
                copyid = copy_ids[i]
                
                # Update reservation status to Reserved
                cur.execute("""
                    UPDATE public.reservation
                    SET status = 'Reserved',
                        pickupdeadline = CURRENT_TIMESTAMP + INTERVAL '3 days',
                        updatedat = CURRENT_TIMESTAMP
                    WHERE reservationid = %s
                """, (res_id,))
                
                # Update copy status to Reserved
                cur.execute("""
                    UPDATE public.bookcopy
                    SET status = 'Reserved', updatedat = CURRENT_TIMESTAMP
                    WHERE copyid = %s
                """, (copyid,))
        
        except Exception as e:
            conn.rollback()
            return jsonify({"status": "error", "message": f"Automatic copy assignment failed: {str(e)}"}), 400
        
        # ==================== 5. Update Book Status ====================
        cur.execute("""
            WITH available_count AS (
                SELECT COUNT(*) AS cnt 
                FROM public.bookcopy 
                WHERE isbn = %s AND status = 'Available'
            )
            UPDATE public.book
            SET status = CASE WHEN available_count.cnt > 0 THEN 'Available' ELSE 'Unavailable' END,
                updatedat = CURRENT_TIMESTAMP
            FROM available_count
            WHERE isbn = %s
        """, (isbn, isbn))
        
        conn.commit()
        return jsonify({
            "status": "success",
            "message": "Operation successful" if existing_book else "New book added successfully",
            "copy_ids": copy_ids,
            "assigned_count": assign_count
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": f"Internal server error: {str(e)}"}), 500
    finally:
        cur.close()
        conn.close()

# 6️⃣ Reserve Book API (Members Only)
@app.route("/reserve", methods=["POST"])
def reserve_book():
    data = request.json
    member_id = data.get("member_id")
    isbn = data.get("isbn")
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Check if reservation limit (10 books) has been reached
        cur.execute("""
            SELECT COUNT(*) FROM public.reservation
            WHERE memberid = %s AND status IN ('Active', 'Reserved')
        """, (member_id,))
        count = cur.fetchone()[0]
        if count >= 10:
            cur.close()
            conn.close()
            return jsonify({"status": "error", "message": "Reservation limit reached."}), 400

        # Check if the book has already been reserved
        cur.execute("""
            SELECT 1 FROM public.reservation
            WHERE memberid = %s AND isbn = %s AND status IN ('Active', 'Reserved')
        """, (member_id, isbn))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"status": "error", "message": "You already have a reservation for this book."}), 400

        # Check if the book has already been borrowed and not returned
        cur.execute("""
            SELECT 1 FROM public.borrow
            WHERE memberid = %s AND isbn = %s AND returndate IS NULL
        """, (member_id, isbn))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"status": "error", "message": "You have already borrowed this book."}), 400

        # Check if the book exists and its status
        cur.execute("SELECT status FROM public.book WHERE isbn = %s", (isbn,))
        book = cur.fetchone()
        if not book:
            cur.close()
            conn.close()
            return jsonify({"status": "error", "message": "Book does not exist."}), 400
        if book[0] != "Unavailable":
            cur.close()
            conn.close()
            return jsonify({"status": "error", "message": "Reservation allowed only for unavailable books."}), 400

        # Get the next queue number
        cur.execute("""
            SELECT COALESCE(MAX(queuenumber), 0) FROM public.reservation
            WHERE isbn = %s AND status = 'Active'
        """, (isbn,))
        next_queue = cur.fetchone()[0] + 1

        cur.execute("""
            INSERT INTO public.reservation
            (memberid, isbn, reservationdate, status, queuenumber, pickupdeadline, createdat, updatedat)
            VALUES (%s, %s, CURRENT_TIMESTAMP, 'Active', %s, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (member_id, isbn, next_queue))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "success", "message": f"Book reserved successfully. Queue number: {next_queue}"})
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 400

# 7️⃣ Cancel Reservation API (Members Only)
@app.route("/cancelReservation", methods=["POST"])
def cancel_reservation():
    data = request.json
    member_id = data.get("member_id")
    reservation_id = data.get("reservation_id")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE public.reservation
            SET status = 'Canceled', updatedat = CURRENT_TIMESTAMP
            WHERE reservationid = %s AND memberid = %s
        """, (reservation_id, member_id))
        if cur.rowcount == 0:
            conn.rollback()
            cur.close()
            conn.close()
            return jsonify({"status": "error", "message": "Reservation not found or unauthorized."}), 400
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "success", "message": "Reservation canceled successfully."})
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 400

# 8️⃣ Get Borrow Records API (Supports optional filtering)
@app.route("/borrowRecords", methods=["GET"])
def borrow_records():
    filter_type = request.args.get("filter_type")
    filter_value = request.args.get("filter_value")
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Use the borrow_record_view view to query and return borrowing records and related information
        if filter_type == "borrowid":
            query = """
                SELECT borrowid, memberid, member_name, isbn, book_title, copyid, borrowdate, duedate, returndate 
                FROM borrow_record_view 
                WHERE CAST(borrowid AS TEXT) ILIKE %s 
                ORDER BY borrowdate DESC
            """
            params = (f"%{filter_value}%",)
        elif filter_type == "isbn":
            query = """
                SELECT borrowid, memberid, member_name, isbn, book_title, copyid, borrowdate, duedate, returndate 
                FROM borrow_record_view 
                WHERE isbn ILIKE %s 
                ORDER BY borrowdate DESC
            """
            params = (f"%{filter_value}%",)
        elif filter_type == "memberid":
            query = """
                SELECT borrowid, memberid, member_name, isbn, book_title, copyid, borrowdate, duedate, returndate 
                FROM borrow_record_view 
                WHERE CAST(memberid AS TEXT) ILIKE %s 
                ORDER BY borrowdate DESC
            """
            params = (f"%{filter_value}%",)
        else:
            query = """
                SELECT borrowid, memberid, member_name, isbn, book_title, copyid, borrowdate, duedate, returndate 
                FROM borrow_record_view 
                ORDER BY borrowdate DESC
            """
            params = ()
        cur.execute(query, params)
        records = cur.fetchall()
        cur.close()
        conn.close()
        result = [
            {
                "borrowid": r[0],
                "memberid": r[1],
                "member_name": r[2],
                "isbn": r[3],
                "book_title": r[4],
                "copyid": r[5],
                "borrowdate": r[6],
                "duedate": r[7],
                "returndate": r[8]
            }
            for r in records
        ]
        return jsonify(result)
    except Exception as e:
        cur.close()
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 400


# 9️⃣ Get Reservation Records API (Supports optional filtering)
@app.route("/reservationRecords", methods=["GET"])
def reservation_records():
    filter_type = request.args.get("filter_type")
    filter_value = request.args.get("filter_value")
    conn = get_connection()
    cur = conn.cursor()
    try:
        if filter_type == "reservationid":
            query = "SELECT reservationid, memberid, isbn, reservationdate, status, queuenumber, pickupdeadline FROM public.reservation WHERE CAST(reservationid AS TEXT) ILIKE %s ORDER BY reservationdate DESC"
            params = (f"%{filter_value}%",)
        elif filter_type == "isbn":
            query = "SELECT reservationid, memberid, isbn, reservationdate, status, queuenumber, pickupdeadline FROM public.reservation WHERE isbn ILIKE %s ORDER BY reservationdate DESC"
            params = (f"%{filter_value}%",)
        elif filter_type == "memberid":
            query = "SELECT reservationid, memberid, isbn, reservationdate, status, queuenumber, pickupdeadline FROM public.reservation WHERE CAST(memberid AS TEXT) ILIKE %s ORDER BY reservationdate DESC"
            params = (f"%{filter_value}%",)
        else:
            query = "SELECT reservationid, memberid, isbn, reservationdate, status, queuenumber, pickupdeadline FROM public.reservation ORDER BY reservationdate DESC"
            params = ()
        cur.execute(query, params)
        records = cur.fetchall()
        cur.close()
        conn.close()
        result = [{"reservationid": r[0], "memberid": r[1], "isbn": r[2], "reservationdate": r[3], "status": r[4], "queuenumber": r[5], "pickupdeadline": r[6]} for r in records]
        return jsonify(result)
    except Exception as e:
        cur.close()
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 400

# 🔟 Get Book Copies API
@app.route("/bookCopies", methods=["GET"])
def book_copies():
    isbn = request.args.get("isbn")
    conn = get_connection()
    cur = conn.cursor()
    try:
        if isbn:
            cur.execute("SELECT copyid, isbn, status, createdat, updatedat FROM public.bookcopy WHERE isbn = %s ORDER BY copyid", (isbn,))
        else:
            cur.execute("SELECT copyid, isbn, status, createdat, updatedat FROM public.bookcopy ORDER BY isbn, copyid")
        records = cur.fetchall()
        cur.close()
        conn.close()
        result = [{"copyid": r[0], "isbn": r[1], "status": r[2], "createdat": r[3], "updatedat": r[4]} for r in records]
        return jsonify(result)
    except Exception as e:
        cur.close()
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 400

# 1️⃣1️⃣ Update Book Information API (Employees Only)
@app.route("/updateBook", methods=["PUT"])
def update_book():
    data = request.json
    employee_id = data.get("employee_id")
    isbn = data.get("isbn")
    new_title = data.get("title")
    new_publishyear = data.get("publishyear")
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Verify employee permissions
        cur.execute("SELECT 1 FROM public.employee WHERE employeeid = %s", (employee_id,))
        if not cur.fetchone():
            return jsonify({"status": "error", "message": "Unauthorized employee."}), 403
        
        # Check if the book exists
        cur.execute("SELECT isbn FROM public.book WHERE isbn = %s", (isbn,))
        if not cur.fetchone():
            return jsonify({"status": "error", "message": "Book does not exist."}), 404
        
        # Input validation
        if new_publishyear and not str(new_publishyear).isdigit():
            return jsonify({"status": "error", "message": "Invalid publish year format."}), 400
        
        # Build dynamic update statement
        updates = []
        params = []
        if new_title:
            updates.append("title = %s")
            params.append(new_title)
        if new_publishyear:
            updates.append("publishyear = %s")
            params.append(new_publishyear)
        if not updates:
            return jsonify({"status": "error", "message": "No fields to update."}), 400
        
        # Execute update
        query = f"""
            UPDATE public.book
            SET {', '.join(updates)}, updatedat = CURRENT_TIMESTAMP
            WHERE isbn = %s
        """
        params.append(isbn)
        cur.execute(query, params)
        conn.commit()
        return jsonify({"status": "success", "message": "Book updated successfully."})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    finally:
        cur.close()
        conn.close()

# 1️⃣2️⃣ Delete Book Copy API (Employees Only, marks copy as Unavailable)
@app.route("/deleteBookCopy", methods=["DELETE"])
def delete_book_copy():
    data = request.json
    employee_id = data.get("employee_id")
    isbn = data.get("isbn")
    copy_ids = data.get("copy_ids", [])

    conn = get_connection()
    cur = conn.cursor()
    updated = []
    skipped = []
    try:
        # Verify employee permissions
        cur.execute("SELECT 1 FROM public.employee WHERE employeeid = %s", (employee_id,))
        if not cur.fetchone():
            return jsonify({"status": "error", "message": "Unauthorized employee."}), 403
        
        # Process each copy
        for cid in copy_ids:
            cur.execute("SELECT status FROM public.bookcopy WHERE copyid = %s AND isbn = %s", (cid, isbn))
            result = cur.fetchone()
            if not result:
                skipped.append({"copyid": cid, "reason": "Not found"})
            elif result[0] != "Available":
                skipped.append({"copyid": cid, "reason": f"Status is '{result[0]}'"})
            else:
                cur.execute("""
                    UPDATE public.bookcopy 
                    SET status = 'Unavailable', updatedat = CURRENT_TIMESTAMP 
                    WHERE copyid = %s
                """, (cid,))
                updated.append(cid)
        # Update book status
        cur.execute("""
            WITH available_count AS (
                SELECT COUNT(*) AS cnt 
                FROM public.bookcopy 
                WHERE isbn = %s AND status = 'Available'
            )
            UPDATE public.book
            SET status = CASE WHEN (SELECT cnt FROM available_count) > 0 THEN 'Available' ELSE 'Unavailable' END,
                updatedat = CURRENT_TIMESTAMP
            WHERE isbn = %s
        """, (isbn, isbn))
        conn.commit()
        return jsonify({"status": "success", "updated": updated, "skipped": skipped})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    finally:
        cur.close()
        conn.close()

# 1️⃣3️⃣ Search Books API
@app.route("/searchBooks", methods=["GET"])
def search_books():
    keyword = request.args.get("keyword", "")
    search_type = request.args.get("search_type", "5")  
    conn = get_connection()
    cur = conn.cursor()
    try:
        if search_type == "1":
            
            filter_clause = "b.title ILIKE %s"
            params = (f"%{keyword}%",)
        elif search_type == "2":
            
            filter_clause = "c.name ILIKE %s"
            params = (f"%{keyword}%",)
        elif search_type == "3":
            
            filter_clause = "CAST(b.publishyear AS TEXT) ILIKE %s"
            params = (f"%{keyword}%",)
        elif search_type == "4":
            
            filter_clause = "a.name ILIKE %s"
            params = (f"%{keyword}%",)
        else:
            filter_clause = ("b.title ILIKE %s OR "
                             "CAST(b.publishyear AS TEXT) ILIKE %s OR "
                             "a.name ILIKE %s OR "
                             "c.name ILIKE %s")
            params = (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")
        query = f"""
            SELECT b.isbn, b.title, b.publishyear, b.status,
                   COALESCE(string_agg(DISTINCT a.name, ', '), 'N/A') AS authors,
                   COALESCE(string_agg(DISTINCT c.name, ', '), 'N/A') AS categories
            FROM public.book b
            LEFT JOIN public.book_author ba ON b.isbn = ba.isbn
            LEFT JOIN public.author a ON ba.authorid = a.authorid
            LEFT JOIN public.book_category bc ON b.isbn = bc.isbn
            LEFT JOIN public.category c ON bc.categoryid = c.categoryid
            WHERE {filter_clause}
            GROUP BY b.isbn, b.title, b.publishyear, b.status
            ORDER BY b.title
        """
        cur.execute(query, params)
        rows = cur.fetchall()
        result = []
        for row in rows:
            result.append({
                "isbn": row[0],
                "title": row[1],
                "publishyear": row[2],
                "status": row[3],
                "authors": row[4],
                "categories": row[5]
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    finally:
        cur.close()
        conn.close()


@app.route("/books/<string:isbn>", methods=["GET"])
def get_book_by_isbn(isbn):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT isbn, title, publishyear, status FROM public.book WHERE isbn = %s", (isbn,))
        row = cur.fetchone()
        if row:
            book = {
                "isbn": row[0],
                "title": row[1],
                "year": row[2],
                "status": row[3]
            }
            return jsonify(book), 200
        else:
            return jsonify({"message": "Book not found"}), 404
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    finally:
        cur.close()
        conn.close()
@app.route("/deleteBook", methods=["DELETE"])
def delete_book():
    """
    Delete an entire book (ISBN) if and only if:
      - All copies in 'bookcopy' are 'Unavailable'.
      - The requesting employee is authorized.
      - If this deletion leaves some authors or categories with zero books, 
        those authors/categories are also removed to maintain consistency.
    """
    data = request.json
    employee_id = data.get("employee_id")
    isbn = data.get("isbn")

    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # 1) Verify employee permissions
        cur.execute("SELECT 1 FROM public.employee WHERE employeeid = %s", (employee_id,))
        if not cur.fetchone():
            return jsonify({"status": "error", "message": "Unauthorized employee or does not exist"}), 403

        # 2) Check if the book exists
        cur.execute("SELECT isbn FROM public.book WHERE isbn = %s", (isbn,))
        book_row = cur.fetchone()
        if not book_row:
            return jsonify({"status": "error", "message": "Book not found"}), 404

        # 3) Ensure all copies are 'Unavailable'
        cur.execute("""
            SELECT COUNT(*) 
            FROM public.bookcopy
            WHERE isbn = %s 
              AND status <> 'Unavailable'
        """, (isbn,))
        non_unavailable_count = cur.fetchone()[0]
        if non_unavailable_count > 0:
            return jsonify({
                "status": "error",
                "message": "Cannot delete this book because not all copies are 'Unavailable'."
            }), 400
        cur.execute("""
            SELECT 1 
            FROM public.borrow 
            WHERE isbn = %s
            LIMIT 1
        """, (isbn,))
        if cur.fetchone():
            return jsonify({
            "status": "error",
            "message": "Cannot delete book with borrow records"
        }), 400

        cur.execute("""
            SELECT 1 
            FROM public.reservation 
            WHERE isbn = %s 
            LIMIT 1
        """, (isbn,))
        if cur.fetchone():
            return jsonify({
                "status": "error",
                "message": "Cannot delete book with reservations"
            }), 400
        # 4) Before deleting the book, collect related author IDs and category IDs for cleanup
        #    so that we can remove them if they are no longer associated with any other book.
        cur.execute("""
            SELECT authorid 
            FROM public.book_author
            WHERE isbn = %s
        """, (isbn,))
        author_ids = [row[0] for row in cur.fetchall()]

        cur.execute("""
            SELECT categoryid
            FROM public.book_category
            WHERE isbn = %s
        """, (isbn,))
        category_ids = [row[0] for row in cur.fetchall()]

        # 5) Delete relationships from book_author, book_category
        cur.execute("DELETE FROM public.book_author WHERE isbn = %s", (isbn,))
        cur.execute("DELETE FROM public.book_category WHERE isbn = %s", (isbn,))

        # 6) Delete all copies for this book from bookcopy 
        cur.execute("DELETE FROM public.bookcopy WHERE isbn = %s", (isbn,))

        # 7) Finally delete the book entry
        cur.execute("DELETE FROM public.book WHERE isbn = %s", (isbn,))

        # 8) Clean up authors if they have no other books
        for author_id in author_ids:
            cur.execute("""
                SELECT 1
                FROM public.book_author
                WHERE authorid = %s
                LIMIT 1
            """, (author_id,))
            still_used = cur.fetchone()
            if not still_used:
                # If there's no other reference to this author, delete it
                cur.execute("DELETE FROM public.author WHERE authorid = %s", (author_id,))

        # 9) Clean up categories if they have no other books
        for category_id in category_ids:
            cur.execute("""
                SELECT 1
                FROM public.book_category
                WHERE categoryid = %s
                LIMIT 1
            """, (category_id,))
            still_used = cur.fetchone()
            if not still_used:
                # If there's no other reference to this category, delete it
                cur.execute("DELETE FROM public.category WHERE categoryid = %s", (category_id,))

        conn.commit()
        return jsonify({"status": "success", "message": f"Book (ISBN={isbn}) deleted successfully."})

    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
