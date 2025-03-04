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
    """
    登录函数：反复提示直到输入正确的账户密码（或用户选择返回登录菜单）
    返回 (role, user_id)
    """
    while True:
        role = input("Select your role (1. Employee, 2. Member): ").strip()
        cur = conn.cursor()
        if role == "1":
            employee_id = input("Enter your Employee ID (or type 'back' to return): ").strip()
            if employee_id.lower() == "back":
                return None, None
            password = input("Enter your password: ").strip()
            query = "SELECT name FROM public.employee WHERE employeeid = %s AND password = %s"
            cur.execute(query, (employee_id, password))
            result = cur.fetchone()
            if result:
                print(f"Welcome, {result[0]} (Employee)!")
                return "employee", employee_id
            else:
                print("Invalid Employee credentials. Please try again.\n")
        elif role == "2":
            member_input = input("Enter your Member ID (or type 'back' to return): ").strip()
            if member_input.lower() == "back":
                return None, None
            try:
                member_id = int(member_input)
            except ValueError:
                print("Member ID should be a number. Please try again.\n")
                continue
            password = input("Enter your password: ").strip()
            query = "SELECT name FROM public.member WHERE memberid = %s AND password = %s"
            cur.execute(query, (member_id, password))
            result = cur.fetchone()
            if result:
                print(f"Welcome, {result[0]} (Member)!")
                return "member", member_id
            else:
                print("Invalid Member credentials. Please try again.\n")
        else:
            print("Invalid role selected. Please try again.\n")


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
    print("\n=== Add a New Book or Add Copies ===")
    isbn = input("Enter ISBN: ").strip()
    
    # 检查该书是否已存在
    cur.execute("SELECT isbn FROM public.book WHERE isbn = %s", (isbn,))
    existing_book = cur.fetchone()
    
    if existing_book:
        print("This book already exists.")
        add_choice = input("Do you want to add new copies to the existing book? (y/n): ").strip().lower()
        if add_choice != "y":
            print("Operation cancelled.")
            return
    else:
        # 新书不存在，则输入书籍基本信息
        title = input("Enter Title: ").strip()
        publishyear = input("Enter Publish Year: ").strip()
        area = input("Enter Area: ").strip()
        status = "Available"  # 新书默认状态为 Available
        try:
            cur.execute("""
                INSERT INTO public.book (isbn, title, publishyear, area, status, employeeid, createdat, updatedat)
                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (isbn, title, publishyear, area, status, employee_id))
        except Exception as e:
            conn.rollback()
            print("Failed to add new book:", e)
            return
        
        # 要求添加至少一个作者或类别
        print("Please provide at least one author or category for the book.")
        authors = input("Enter author names (comma separated): ").strip()
        categories = input("Enter category names (comma separated): ").strip()
        if not authors and not categories:
            print("Error: Each book must have at least one author or category!")
            conn.rollback()
            return
        
        if authors:
            for author in authors.split(","):
                author = author.strip()
                try:
                    # get_or_create_author 函数负责查找或新建作者记录
                    authorid = get_or_create_author(conn, cur, author, employee_id)
                    cur.execute("INSERT INTO public.book_author (isbn, authorid) VALUES (%s, %s)", (isbn, authorid))
                except Exception as e:
                    conn.rollback()
                    print("Failed to add author association:", e)
                    return
        if categories:
            for category in categories.split(","):
                category = category.strip()
                try:
                    # get_or_create_category 函数负责查找或新建类别记录
                    categoryid = get_or_create_category(conn, cur, category, employee_id)
                    cur.execute("INSERT INTO public.book_category (isbn, categoryid) VALUES (%s, %s)", (isbn, categoryid))
                except Exception as e:
                    conn.rollback()
                    print("Failed to add category association:", e)
                    return
    
    # 添加影本记录
    num_copies_str = input("Enter number of copies to add for this book: ").strip()
    try:
        num_copies = int(num_copies_str)
    except ValueError:
        print("Invalid number input. Defaulting to 1 copy.")
        num_copies = 1

    copy_ids = []
    try:
        for _ in range(num_copies):
            cur.execute("""
                INSERT INTO public.bookcopy (isbn, status, createdat, updatedat)
                VALUES (%s, 'Available', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING copyid
            """, (isbn,))
            cid = cur.fetchone()[0]
            copy_ids.append(cid)
        conn.commit()
        print("New book (or copies) added successfully.")
        print("Generated copy IDs:", copy_ids)
    except Exception as e:
        conn.rollback()
        print("Failed to add copies:", e)


def employee_menu(conn, employee_id):
    while True:
        print("\nEmployee Menu:")
        print("1. Browse Books")
        print("2. Add New Book")
        print("3. Search Books")
        print("4. Logout")
        choice = input("Enter your choice: ").strip()
        if choice == "1":
            browse_books(conn)
        elif choice == "2":
            add_book(conn, employee_id)
        elif choice == "3":
            search_books(conn)
        elif choice == "4":
            print("Logging out...\n")
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
    if book[0] != "Unavailable":
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
    # 检查会员当前未归还的借阅数量
    cur.execute("""
        SELECT COUNT(borrowid)
        FROM public.borrow 
        WHERE memberid = %s AND returndate IS NULL
    """, (member_id,))
    active_borrow_count = cur.fetchone()[0]
    if active_borrow_count >= 5:
        print("You already have 5 active borrowed books. Please return some books before borrowing more.")
        return

    isbn = input("Enter ISBN of the book you want to borrow: ").strip()
    
    # 检查书籍是否存在
    cur.execute("SELECT status FROM public.book WHERE isbn = %s", (isbn,))
    book = cur.fetchone()
    if not book:
        print("Book does not exist.")
        return
    
    # 如果书籍处于不可借状态，则检查预约情况
    if book[0] == "Unavailable":
        cur.execute("""
            SELECT memberid
            FROM public.reservation
            WHERE isbn = %s AND status = 'Reserved' 
              AND pickupdeadline IS NOT NULL AND pickupdeadline > CURRENT_TIMESTAMP
            ORDER BY queuenumber ASC
            LIMIT 1
        """, (isbn,))
        res = cur.fetchone()
        if res is None or res[0] != member_id:
            print("Book is reserved for another member.")
            return
    
    try:
        # 插入借阅记录，并利用触发器自动分配一个可用影本
        cur.execute("""
            INSERT INTO public.borrow 
            (memberid, isbn, borrowdate, duedate, returndate, createdat, updatedat)
            VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_DATE + 30, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING borrowid, copyid
        """, (member_id, isbn))
        result = cur.fetchone()
        conn.commit()
        print(f"Book borrowed successfully. Borrow ID: {result[0]}, Assigned Copy ID: {result[1]}")
    except Exception as e:
        conn.rollback()
        print("Failed to borrow book:", e)


def return_book(conn, member_id):
    cur = conn.cursor()
    print("\n=== Return a Book ===")
    try:
        # 获取该会员所有未归还的借阅记录
        cur.execute("""
            SELECT borrowid, isbn, copyid 
            FROM public.borrow
            WHERE memberid = %s AND returndate IS NULL
        """, (member_id,))
        borrow_records = cur.fetchall()
        
        if not borrow_records:
            print("You don't have any books to return.")
            return
        
        print("Your active borrowed books:")
        for i, record in enumerate(borrow_records, 1):
            borrowid, isbn, copyid = record
            print(f"{i}. BorrowID: {borrowid}, ISBN: {isbn}, CopyID: {copyid}")
        
        choice = input("Enter the number of the book you want to return: ").strip()
        try:
            choice_index = int(choice) - 1
            if choice_index < 0 or choice_index >= len(borrow_records):
                print("Invalid selection.")
                return
        except ValueError:
            print("Invalid input.")
            return
        
        selected_record = borrow_records[choice_index]
        borrowid, isbn, copyid = selected_record
        
        # 更新借阅记录的归还时间
        cur.execute("""
            UPDATE public.borrow
            SET returndate = CURRENT_TIMESTAMP
            WHERE borrowid = %s
        """, (borrowid,))
        
        # 检查是否有该书的Active预约
        cur.execute("""
            SELECT reservationid, memberid
            FROM public.reservation
            WHERE isbn = %s 
              AND status = 'Active'
            ORDER BY queuenumber ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """, (isbn,))
        first_reservation = cur.fetchone()

        if first_reservation:
            reservation_id, reserved_member_id = first_reservation
            # 将这本影本标记为Reserved，并更新预约记录
            cur.execute("""
                UPDATE public.bookcopy
                SET status = 'Reserved'
                WHERE copyid = %s
            """, (copyid,))
            cur.execute("""
                UPDATE public.reservation
                SET status = 'Reserved',
                    pickupdeadline = CURRENT_TIMESTAMP + INTERVAL '3 days',
                    updatedat = CURRENT_TIMESTAMP
                WHERE reservationid = %s
            """, (reservation_id,))
            print(f"Book reserved for member {reserved_member_id}. Must borrow within 3 days.")
        else:
            # 没有Active预约则将该影本标记为Available
            cur.execute("""
                UPDATE public.bookcopy
                SET status = 'Available'
                WHERE copyid = %s
            """, (copyid,))
            print("Book marked as available")
        
        # 根据可用副本数量更新book表状态
        cur.execute("""
            WITH status_summary AS (
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'Available') AS available
                FROM public.bookcopy
                WHERE isbn = %s
            )
            UPDATE public.book
            SET status = CASE
                WHEN (SELECT available FROM status_summary) > 0 THEN 'Available'
                ELSE 'Unavailable'
            END,
            updatedat = CURRENT_TIMESTAMP
            WHERE isbn = %s
        """, (isbn, isbn))
        
        conn.commit()
        print(f"Return successful! Copy ID: {copyid}")
    
    except Exception as e:
        conn.rollback()
        print("Failed to return book:", e)

        
def member_menu(conn, member_id):
    while True:
        print("\nMember Menu:")
        print("1. Browse Books")
        print("2. Reserve a Book")
        print("3. Cancel a Reservation")
        print("4. Borrow a Book")
        print("5. Return a Book")
        print("6. Search Books")
        print("7. Logout")
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
            search_books(conn)
        elif choice == "7":
            print("Logging out...\n")
            break
        else:
            print("Invalid choice. Please try again.")

def search_books(conn):
    cur = conn.cursor()
    print("\n=== Search Books ===")
    keyword = input("Enter search keyword: ").strip()
    print("Select search type:")
    print("1. Title")
    print("2. Category")
    print("3. Year")
    print("4. Author")
    print("5. All (search in title, year, author and category)")
    search_type = input("Enter your choice: ").strip()

    if search_type == "1":
        query = "SELECT isbn, title, publishyear, status FROM public.book WHERE title ILIKE %s"
        params = (f"%{keyword}%",)
    elif search_type == "2":
        query = """
            SELECT DISTINCT b.isbn, b.title, b.publishyear, b.status 
            FROM public.book b 
            JOIN public.book_category bc ON b.isbn = bc.isbn 
            JOIN public.category c ON bc.categoryid = c.categoryid 
            WHERE c.name ILIKE %s
        """
        params = (f"%{keyword}%",)
    elif search_type == "3":
        query = "SELECT isbn, title, publishyear, status FROM public.book WHERE CAST(publishyear AS TEXT) ILIKE %s"
        params = (f"%{keyword}%",)
    elif search_type == "4":
        query = """
            SELECT DISTINCT b.isbn, b.title, b.publishyear, b.status 
            FROM public.book b 
            JOIN public.book_author ba ON b.isbn = ba.isbn 
            JOIN public.author a ON ba.authorid = a.authorid 
            WHERE a.name ILIKE %s
        """
        params = (f"%{keyword}%",)
    elif search_type == "5":
        query = """
            SELECT DISTINCT b.isbn, b.title, b.publishyear, b.status 
            FROM public.book b
            LEFT JOIN public.book_author ba ON b.isbn = ba.isbn
            LEFT JOIN public.author a ON ba.authorid = a.authorid
            LEFT JOIN public.book_category bc ON b.isbn = bc.isbn
            LEFT JOIN public.category c ON bc.categoryid = c.categoryid
            WHERE b.title ILIKE %s 
               OR CAST(b.publishyear AS TEXT) ILIKE %s 
               OR a.name ILIKE %s 
               OR c.name ILIKE %s
        """
        params = (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")
    else:
        print("Invalid search type.")
        return

    try:
        cur.execute(query, params)
        rows = cur.fetchall()
        if rows:
            print("\n=== Search Results ===")
            for row in rows:
                isbn, title, publishyear, status = row
                print(f"ISBN: {isbn}, Title: {title}, Year: {publishyear}, Status: {status}")
        else:
            print("No books found matching the search criteria.")
    except Exception as e:
        print("Search failed:", e)
    print()

def main():
    conn = get_connection()
    while True:
        print("\n=== Welcome to the Library System ===")
        print("1. Login")
        print("2. Exit")
        choice = input("Enter your choice: ").strip()
        if choice == "2":
            print("Exiting program.")
            break
        elif choice == "1":
            role, user_id = login(conn)
            # 如果登录函数返回 None，则回到登录菜单
            if role is None:
                continue
            if role == "employee":
                employee_menu(conn, user_id)
            elif role == "member":
                member_menu(conn, user_id)
        else:
            print("Invalid choice. Please try again.")
    conn.close()


if __name__ == "__main__":
    main()
