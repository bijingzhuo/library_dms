import psycopg2
DB_NAME = "Library"
DB_USER = "postgres"
DB_PASSWORD = "admin"
DB_HOST = "localhost"
DB_PORT = "5432"

def get_connection():
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        print("Failed to connect to the database:", e)
        exit(1)

def login(conn):
    role = input("Select your role (1. Employee, 2. Member): ").strip()
    cur = conn.cursor()
    if role == "1":
        employee_id = input("Enter your Employee ID: ").strip()
        password = input("Enter your password: ").strip()
        query = "SELECT name FROM public.employee WHERE employeeid = %s AND password = %s"
        cur.execute(query, (employee_id, password))
        result = cur.fetchone()
        if result:
            print(f"Welcome, {result[0]} (Employee)!")
            return "employee", employee_id
        else:
            print("Invalid Employee credentials.")
            return None, None
    elif role == "2":
        member_id = input("Enter your Member ID: ").strip()
        password = input("Enter your password: ").strip()
        query = "SELECT name FROM public.member WHERE memberid = %s AND password = %s"
        cur.execute(query, (member_id, password))
        result = cur.fetchone()
        if result:
            print(f"Welcome, {result[0]} (Member)!")
            return "member", member_id
        else:
            print("Invalid Member credentials.")
            return None, None
    else:
        print("Invalid role selected.")
        return None, None

def browse_books(conn):
    cur = conn.cursor()
    query = "SELECT isbn, title, publishyear, status FROM public.book"
    cur.execute(query)
    rows = cur.fetchall()
    print("\n=== Books List ===")
    for row in rows:
        isbn, title, publishyear, status = row
        print(f"ISBN: {isbn}, Title: {title}, Year: {publishyear}, Status: {status}")
    print()

def get_or_create_author(conn, cur, author_name, employee_id):
    """
    检查指定的作者名称是否存在（不区分大小写），
    如果存在则返回其authorid，否则插入新记录并返回新生成的authorid。
    """
    cur.execute("SELECT authorid FROM public.author WHERE lower(name) = lower(%s)", (author_name,))
    result = cur.fetchone()
    if result:
        return result[0]
    else:
        cur.execute(
            "INSERT INTO public.author (name, employeeid) VALUES (%s, %s) RETURNING authorid",
            (author_name, employee_id)
        )
        return cur.fetchone()[0]

def get_or_create_category(conn, cur, category_name, employee_id):
    """
    检查指定的类别名称是否存在（不区分大小写），
    如果存在则返回其categoryid，否则插入新记录并返回新生成的categoryid。
    """
    cur.execute("SELECT categoryid FROM public.category WHERE lower(name) = lower(%s)", (category_name,))
    result = cur.fetchone()
    if result:
        return result[0]
    else:
        cur.execute(
            "INSERT INTO public.category (name, employeeid) VALUES (%s, %s) RETURNING categoryid",
            (category_name, employee_id)
        )
        return cur.fetchone()[0]

def add_book(conn, employee_id):
    cur = conn.cursor()
    print("\n=== Add a New Book ===")
    isbn = input("Enter ISBN: ").strip()
    title = input("Enter Title: ").strip()
    publishyear = input("Enter Publish Year: ").strip()
    status = "Available"  # 新书默认状态为 Available
    try:
        # 插入新书记录
        cur.execute("""
            INSERT INTO public.book (isbn, title, publishyear, status, employeeid, createdat, updatedat)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (isbn, title, publishyear, status, employee_id))
        
        # 提示输入作者名称（逗号分隔）
        author_names_input = input("Enter one or more Author Names (comma separated) for this book: ").strip()
        # 提示输入类别名称（逗号分隔）
        category_names_input = input("Enter one or more Category Names (comma separated) for this book: ").strip()
        
        # 确保至少输入一个作者或类别
        if not author_names_input and not category_names_input:
            conn.rollback()
            print("Failed to add new book: Each book must have at least one author or category!")
            return
        
        # 处理作者：对每个作者名称进行检查或创建，并在 book_author 中建立关联
        if author_names_input:
            author_names = [name.strip() for name in author_names_input.split(',') if name.strip()]
            for author_name in author_names:
                author_id = get_or_create_author(conn, cur, author_name, employee_id)
                cur.execute("INSERT INTO public.book_author (isbn, authorid) VALUES (%s, %s)", (isbn, author_id))
        
        # 处理类别：对每个类别名称进行检查或创建，并在 book_category 中建立关联
        if category_names_input:
            category_names = [name.strip() for name in category_names_input.split(',') if name.strip()]
            for category_name in category_names:
                category_id = get_or_create_category(conn, cur, category_name, employee_id)
                cur.execute("INSERT INTO public.book_category (isbn, categoryid) VALUES (%s, %s)", (isbn, category_id))
        
        conn.commit()
        print("New book and its associations added successfully.\n")
    except Exception as e:
        conn.rollback()
        print("Failed to add new book:", e)

def employee_menu(conn, employee_id):
    while True:
        print("\nEmployee Menu:")
        print("1. Browse Books")
        print("2. Add New Book")
        print("3. Logout")
        choice = input("Enter your choice: ").strip()
        if choice == "1":
            browse_books(conn)
        elif choice == "2":
            add_book(conn, employee_id)
        elif choice == "3":
            print("Logging out.")
            break
        else:
            print("Invalid choice. Please try again.")

def reserve_book(conn, member_id):
    cur = conn.cursor()
    print("\n=== Reserve a Book ===")
    isbn = input("Enter ISBN of the book to reserve: ").strip()
    
    # 检查书籍是否存在
    cur.execute("SELECT status FROM public.book WHERE isbn = %s", (isbn,))
    book = cur.fetchone()
    if not book:
        print("Book does not exist.")
        return
    # 检查书籍状态是否为 "Borrowed"（只有借出状态的书才能预约）
    if book[0] != "Borrowed":
        print("Reservation is only allowed for books that are Borrowed.")
        return
    
    # 查询该书当前所有 'Active' 状态下的预约记录，计算下一个队列号
    cur.execute("""
        SELECT COALESCE(MAX(queuenumber), 0)
        FROM public.reservation
        WHERE isbn = %s AND status = 'Active'
    """, (isbn,))
    max_queue = cur.fetchone()[0]
    next_queue = max_queue + 1
    
    # 插入新的预约记录（ReservationDate 使用 CURRENT_TIMESTAMP，Status 设置为 'Active'）
    try:
        cur.execute("""
            INSERT INTO public.reservation
            (memberid, isbn, reservationdate, status, queuenumber, pickupdeadline, createdat, updatedat)
            VALUES (%s, %s, CURRENT_TIMESTAMP, 'Active', %s, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (member_id, isbn, next_queue))
        conn.commit()
        print(f"Book reserved successfully. Your queue number is: {next_queue}")
    except Exception as e:
        conn.rollback()
        print("Failed to reserve book:", e)
def cancel_reservation(conn, member_id):
    cur = conn.cursor()
    print("\n=== Cancel a Reservation ===")
    # 显示该会员所有状态为 'Active' 的预约记录
    cur.execute("""
        SELECT reservationid, isbn, reservationdate, queuenumber 
        FROM public.reservation 
        WHERE memberid = %s AND status = 'Active'
    """, (member_id,))
    reservations = cur.fetchall()
    if not reservations:
        print("You have no active reservations to cancel.")
        return
    print("Your active reservations:")
    for res in reservations:
        print(f"Reservation ID: {res[0]}, ISBN: {res[1]}, Date: {res[2]}, Queue Number: {res[3]}")
    
    res_id = input("Enter the Reservation ID you want to cancel: ").strip()
    try:
        cur.execute("""
            UPDATE public.reservation
            SET status = 'Canceled', updatedat = CURRENT_TIMESTAMP
            WHERE reservationid = %s AND memberid = %s
        """, (res_id, member_id))
        if cur.rowcount == 0:
            print("Reservation not found or you are not authorized to cancel it.")
        else:
            conn.commit()
            print("Reservation canceled successfully.")
    except Exception as e:
        conn.rollback()
        print("Failed to cancel reservation:", e)

def borrow_book(conn, member_id):
    cur = conn.cursor()
    print("\n=== Borrow a Book ===")
    # 检查会员是否已有未归还的借阅
    cur.execute("""
        SELECT borrowid FROM public.borrow 
        WHERE memberid = %s AND returndate IS NULL
    """, (member_id,))
    active_borrow = cur.fetchone()
    if active_borrow:
        print("You already have an active borrowed book. Please return it first.")
        return

    isbn = input("Enter ISBN of the book you want to borrow: ").strip()
    
    # 检查书籍是否存在
    cur.execute("SELECT status FROM public.book WHERE isbn = %s", (isbn,))
    book = cur.fetchone()
    if not book:
        print("Book does not exist.")
        return
    # 仅当书籍状态为 'Available' 时允许直接借阅
    if book[0] != "Available":
        print("Book is not available for borrowing.")
        return

    try:
        # 插入借阅记录：借书日期为当前时间，到期日为当前日期+30天，归还日期为空
        cur.execute("""
            INSERT INTO public.borrow 
            (memberid, isbn, borrowdate, duedate, returndate, createdat, updatedat)
            VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_DATE + 30, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (member_id, isbn))
        # 更新书籍状态为 'Borrowed'
        cur.execute("""
            UPDATE public.book 
            SET status = 'Borrowed', updatedat = CURRENT_TIMESTAMP
            WHERE isbn = %s
        """, (isbn,))
        conn.commit()
        print("Book borrowed successfully.")
    except Exception as e:
        conn.rollback()
        print("Failed to borrow book:", e)

def return_book(conn, member_id):
    cur = conn.cursor()
    print("\n=== Return a Book ===")
    # 查找该会员未归还的借阅记录
    cur.execute("""
        SELECT borrowid, isbn FROM public.borrow
        WHERE memberid = %s AND returndate IS NULL
    """, (member_id,))
    borrow_record = cur.fetchone()
    if not borrow_record:
        print("You do not have any borrowed book to return.")
        return
    borrowid, isbn = borrow_record
    try:
        # 更新借阅记录，将归还日期设置为当前时间
        cur.execute("""
            UPDATE public.borrow
            SET returndate = CURRENT_TIMESTAMP, updatedat = CURRENT_TIMESTAMP
            WHERE borrowid = %s
        """, (borrowid,))
        # 检查该书是否存在队列第一的有效预约记录
        cur.execute("""
            SELECT reservationid FROM public.reservation
            WHERE isbn = %s AND status = 'Active' AND queuenumber = 1
        """, (isbn,))
        reservation = cur.fetchone()
        if reservation:
            # 如果存在，则将书籍状态更新为 'Reserved'
            cur.execute("""
                UPDATE public.book
                SET status = 'Reserved', updatedat = CURRENT_TIMESTAMP
                WHERE isbn = %s
            """, (isbn,))
        else:
            # 否则更新书籍状态为 'Available'
            cur.execute("""
                UPDATE public.book
                SET status = 'Available', updatedat = CURRENT_TIMESTAMP
                WHERE isbn = %s
            """, (isbn,))
        conn.commit()
        print("Book returned successfully.")
    except Exception as e:
        conn.rollback()
        print("Failed to return book:", e)

# 更新后的 Member 菜单（仅显示修改部分）
def member_menu(conn, member_id):
    while True:
        print("\nMember Menu:")
        print("1. Browse Books")
        print("2. Reserve a Book")
        print("3. Cancel a Reservation")
        print("4. Borrow a Book")
        print("5. Return a Book")
        print("6. Logout")
        choice = input("Enter your choice: ").strip()
        if choice == "1":
            browse_books(conn)
        elif choice == "2":
            reserve_book(conn, member_id)
        elif choice == "3":
            cancel_reservation(conn, member_id)
        elif choice == "4":
            borrow_book(conn, member_id)
        elif choice == "5":
            return_book(conn, member_id)
        elif choice == "6":
            print("Logging out.")
            break
        else:
            print("Invalid choice. Please try again.")
def main():
    conn = get_connection()
    role, user_id = login(conn)
    if role == "employee":
        employee_menu(conn, user_id)
    elif role == "member":
        member_menu(conn, user_id)
    else:
        print("Login failed.")
    conn.close()

if __name__ == "__main__":
    main()
