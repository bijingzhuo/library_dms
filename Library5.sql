PGDMP  7    $                }            Library    17.2    17.2 v    �           0    0    ENCODING    ENCODING        SET client_encoding = 'UTF8';
                           false            �           0    0 
   STDSTRINGS 
   STDSTRINGS     (   SET standard_conforming_strings = 'on';
                           false            �           0    0 
   SEARCHPATH 
   SEARCHPATH     8   SELECT pg_catalog.set_config('search_path', '', false);
                           false            �           1262    33588    Library    DATABASE     �   CREATE DATABASE "Library" WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'Chinese (Simplified)_China.utf8';
    DROP DATABASE "Library";
                     postgres    false                        1255    33589    adjust_reservation_queue()    FUNCTION     /  CREATE FUNCTION public.adjust_reservation_queue() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    available_count INTEGER;
BEGIN
    IF (OLD.status IN ('Active','Reserved'))
       AND (NEW.status IN ('Canceled', 'PickedUp'))
    THEN
        UPDATE public.reservation
        SET queuenumber = queuenumber - 1
        WHERE isbn = OLD.isbn
          AND status = 'Active'
          AND queuenumber > OLD.queuenumber;

    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.reservation
        WHERE isbn = OLD.isbn AND status = 'Active'
    ) THEN
        SELECT COUNT(*) INTO available_count
        FROM public.bookcopy
        WHERE isbn = OLD.isbn AND status = 'Available';

        IF available_count > 0 THEN
            UPDATE public.book
            SET status = 'Available', updatedat = CURRENT_TIMESTAMP
            WHERE isbn = OLD.isbn;
        ELSE
            UPDATE public.book
            SET status = 'Unavailable', updatedat = CURRENT_TIMESTAMP
            WHERE isbn = OLD.isbn;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;
 1   DROP FUNCTION public.adjust_reservation_queue();
       public               postgres    false                       1255    33590    assign_book_copy()    FUNCTION     �  CREATE FUNCTION public.assign_book_copy() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    available_copy INTEGER;
    available_count INTEGER;
BEGIN
    IF NEW.copyid IS NULL THEN
        SELECT copyid INTO available_copy
        FROM public.bookcopy
        WHERE isbn = NEW.isbn AND status = 'Available'
        LIMIT 1;

        IF available_copy IS NULL THEN
            SELECT copyid INTO available_copy
            FROM public.bookcopy
            WHERE isbn = NEW.isbn AND status = 'Reserved'
            LIMIT 1;
            IF available_copy IS NULL THEN
                RAISE EXCEPTION 'No available copy for ISBN %', NEW.isbn;
            END IF;
        END IF;
        NEW.copyid = available_copy;

        UPDATE public.bookcopy
        SET status = 'Borrowed', updatedat = CURRENT_TIMESTAMP
        WHERE copyid = available_copy;

        SELECT COUNT(*) INTO available_count
        FROM public.bookcopy
        WHERE isbn = NEW.isbn AND status = 'Available';

        UPDATE public.book
        SET status = CASE WHEN available_count = 0 THEN 'Unavailable' ELSE 'Available' END,
            updatedat = CURRENT_TIMESTAMP
        WHERE isbn = NEW.isbn;
    END IF;

    RETURN NEW;
END;
$$;
 )   DROP FUNCTION public.assign_book_copy();
       public               postgres    false            �            1255    33591    check_book_associations()    FUNCTION     �  CREATE FUNCTION public.check_book_associations() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM Book b
        WHERE NOT EXISTS (SELECT 1 FROM Book_Author WHERE ISBN = b.ISBN)
          AND NOT EXISTS (SELECT 1 FROM Book_Category WHERE ISBN = b.ISBN)
    ) THEN
        RAISE EXCEPTION 'Each book must have at least one author or category!';
    END IF;
    RETURN NULL;
END;
$$;
 0   DROP FUNCTION public.check_book_associations();
       public               postgres    false            �            1255    33770    check_borrow_limit()    FUNCTION     �  CREATE FUNCTION public.check_borrow_limit() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    active_count INTEGER;
BEGIN
    IF NEW.returndate IS NOT NULL THEN
        RETURN NEW;
    END IF;

    SELECT COUNT(*) INTO active_count
    FROM public.borrow
    WHERE memberid = NEW.memberid
      AND returndate IS NULL;

    IF active_count >= 5 THEN
        RAISE EXCEPTION 'Member % has reached the maximum borrow limit of 5 books.', NEW.memberid;
    END IF;

    RETURN NEW;
END;
$$;
 +   DROP FUNCTION public.check_borrow_limit();
       public               postgres    false            �            1255    33592    check_borrow_permission()    FUNCTION     "  CREATE FUNCTION public.check_borrow_permission() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    available_count INTEGER;
    reserved_reservation RECORD;
BEGIN
    IF NEW.copyid IS NOT NULL THEN
        RETURN NEW;
    END IF;

    SELECT COUNT(*) INTO available_count
    FROM public.bookcopy
    WHERE isbn = NEW.isbn AND status = 'Available';

    SELECT *
    INTO reserved_reservation
    FROM public.reservation
    WHERE isbn = NEW.isbn
      AND status = 'Reserved'
      AND pickupdeadline >= CURRENT_TIMESTAMP
    ORDER BY queuenumber ASC, reservationdate ASC
    LIMIT 1;

    IF reserved_reservation IS NOT NULL THEN
        IF reserved_reservation.memberid = NEW.memberid THEN
            RETURN NEW;
        ELSE
            RAISE EXCEPTION 'Only the member at the front of the reservation queue can borrow this book!';
        END IF;
    ELSE
        IF available_count > 0 THEN
            RETURN NEW;
        ELSE
            RAISE EXCEPTION 'No available copy exists for ISBN %', NEW.isbn;
        END IF;
    END IF;
END;
$$;
 0   DROP FUNCTION public.check_borrow_permission();
       public               postgres    false            �            1255    33593 &   check_late_returns_and_freeze_member()    FUNCTION     �  CREATE FUNCTION public.check_late_returns_and_freeze_member() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    late_count INTEGER;
BEGIN
    IF OLD.returndate IS NULL AND NEW.returndate IS NOT NULL THEN

        IF NEW.returndate > NEW.duedate THEN

            SELECT COUNT(*) INTO late_count
            FROM public.borrow
            WHERE memberid = NEW.memberid
              AND returndate IS NOT NULL
              AND returndate > duedate;

            IF late_count >= 3 THEN
                UPDATE public.member
                SET membershipstatus = 'Frozen'
                WHERE memberid = NEW.memberid;
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
 =   DROP FUNCTION public.check_late_returns_and_freeze_member();
       public               postgres    false            �            1255    33768    check_reservation_limit()    FUNCTION     �  CREATE FUNCTION public.check_reservation_limit() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    current_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO current_count
    FROM public.reservation
    WHERE memberid = NEW.memberid
      AND status IN ('Active', 'Reserved');

    IF current_count >= 10 THEN
        RAISE EXCEPTION 'Member % has reached the reservation limit of 10 books.', NEW.memberid;
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.reservation
        WHERE memberid = NEW.memberid
          AND isbn = NEW.isbn
          AND status IN ('Active', 'Reserved')
    ) THEN
        RAISE EXCEPTION 'Member % already has a reservation for ISBN %.', NEW.memberid, NEW.isbn;
    END IF;

    RETURN NEW;
END;
$$;
 0   DROP FUNCTION public.check_reservation_limit();
       public               postgres    false            �            1255    33594    process_expired_reservations()    FUNCTION     4  CREATE FUNCTION public.process_expired_reservations() RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    expired_rec RECORD;
BEGIN
    FOR expired_rec IN
      SELECT *
      FROM reservation
      WHERE queuenumber = 1
        AND status = 'Active'
        AND pickupdeadline < CURRENT_TIMESTAMP 
    LOOP

      DELETE FROM reservation
      WHERE reservationid = expired_rec.reservationid;
      

      UPDATE reservation
      SET queuenumber = queuenumber - 1
      WHERE isbn = expired_rec.isbn AND queuenumber > 1;
      

      IF NOT EXISTS (
            SELECT 1 FROM reservation 
            WHERE isbn = expired_rec.isbn 
              AND status = 'Active'
         )
      THEN

         UPDATE book SET status = 'Available' WHERE isbn = expired_rec.isbn;
      END IF;
      
    END LOOP;
END;
$$;
 5   DROP FUNCTION public.process_expired_reservations();
       public               postgres    false            �            1255    33761 (   sync_bookcopy_and_update_status_simple()    FUNCTION     t  CREATE FUNCTION public.sync_bookcopy_and_update_status_simple() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE public.bookcopy
    SET status = 'Available', updatedat = CURRENT_TIMESTAMP
    WHERE copyid = NEW.copyid;

    UPDATE public.book
    SET status = 'Available', updatedat = CURRENT_TIMESTAMP
    WHERE isbn = NEW.isbn;

    RETURN NEW;
END;
$$;
 ?   DROP FUNCTION public.sync_bookcopy_and_update_status_simple();
       public               postgres    false            �            1255    33765     update_reservation_to_pickedup()    FUNCTION     �  CREATE FUNCTION public.update_reservation_to_pickedup() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE public.reservation
    SET status = 'PickedUp',
        updatedat = CURRENT_TIMESTAMP,
        pickupdeadline = NULL  
    WHERE isbn = NEW.isbn
      AND memberid = NEW.memberid
      AND status = 'Reserved'
      AND (pickupdeadline IS NULL OR pickupdeadline > CURRENT_TIMESTAMP);
    RETURN NEW;
END;
$$;
 7   DROP FUNCTION public.update_reservation_to_pickedup();
       public               postgres    false            �            1255    33596    update_updatedat_column()    FUNCTION     �   CREATE FUNCTION public.update_updatedat_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updatedat := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;
 0   DROP FUNCTION public.update_updatedat_column();
       public               postgres    false            �            1259    33597    author    TABLE     %  CREATE TABLE public.author (
    authorid integer NOT NULL,
    name character varying(100) NOT NULL,
    employeeid integer NOT NULL,
    createdat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);
    DROP TABLE public.author;
       public         heap r       postgres    false            �            1259    33602    author_authorid_seq    SEQUENCE     �   CREATE SEQUENCE public.author_authorid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
 *   DROP SEQUENCE public.author_authorid_seq;
       public               postgres    false    217            �           0    0    author_authorid_seq    SEQUENCE OWNED BY     K   ALTER SEQUENCE public.author_authorid_seq OWNED BY public.author.authorid;
          public               postgres    false    218            �            1259    33603    book    TABLE     i  CREATE TABLE public.book (
    isbn character varying(20) NOT NULL,
    title character varying(255) NOT NULL,
    publishyear integer,
    status character varying(50),
    employeeid integer NOT NULL,
    createdat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);
    DROP TABLE public.book;
       public         heap r       postgres    false            �            1259    33608    book_author    TABLE     l   CREATE TABLE public.book_author (
    isbn character varying(20) NOT NULL,
    authorid integer NOT NULL
);
    DROP TABLE public.book_author;
       public         heap r       postgres    false            �            1259    33611    book_category    TABLE     p   CREATE TABLE public.book_category (
    isbn character varying(20) NOT NULL,
    categoryid integer NOT NULL
);
 !   DROP TABLE public.book_category;
       public         heap r       postgres    false            �            1259    33629    category    TABLE     )  CREATE TABLE public.category (
    categoryid integer NOT NULL,
    name character varying(100) NOT NULL,
    employeeid integer NOT NULL,
    createdat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);
    DROP TABLE public.category;
       public         heap r       postgres    false            �            1259    33782    book_detail_view    VIEW     �  CREATE VIEW public.book_detail_view AS
 SELECT b.isbn,
    b.title,
    b.publishyear,
    b.status,
    COALESCE(string_agg(DISTINCT (a.name)::text, ', '::text), 'N/A'::text) AS authors,
    COALESCE(string_agg(DISTINCT (c.name)::text, ', '::text), 'N/A'::text) AS categories
   FROM ((((public.book b
     LEFT JOIN public.book_author ba ON (((b.isbn)::text = (ba.isbn)::text)))
     LEFT JOIN public.author a ON ((ba.authorid = a.authorid)))
     LEFT JOIN public.book_category bc ON (((b.isbn)::text = (bc.isbn)::text)))
     LEFT JOIN public.category c ON ((bc.categoryid = c.categoryid)))
  GROUP BY b.isbn, b.title, b.publishyear, b.status;
 #   DROP VIEW public.book_detail_view;
       public       v       postgres    false    221    221    226    226    220    220    219    219    219    219    217    217            �            1259    33614    bookcopy    TABLE     U  CREATE TABLE public.bookcopy (
    copyid integer NOT NULL,
    isbn character varying(20) NOT NULL,
    status character varying(50) DEFAULT 'Available'::character varying NOT NULL,
    createdat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);
    DROP TABLE public.bookcopy;
       public         heap r       postgres    false            �            1259    33620    bookcopy_copyid_seq    SEQUENCE     �   CREATE SEQUENCE public.bookcopy_copyid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
 *   DROP SEQUENCE public.bookcopy_copyid_seq;
       public               postgres    false    222            �           0    0    bookcopy_copyid_seq    SEQUENCE OWNED BY     K   ALTER SEQUENCE public.bookcopy_copyid_seq OWNED BY public.bookcopy.copyid;
          public               postgres    false    223            �            1259    33621    borrow    TABLE     �  CREATE TABLE public.borrow (
    borrowid integer NOT NULL,
    memberid integer NOT NULL,
    isbn character varying(20) NOT NULL,
    borrowdate timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    duedate date DEFAULT (CURRENT_DATE + 30) NOT NULL,
    returndate date,
    createdat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    copyid integer
);
    DROP TABLE public.borrow;
       public         heap r       postgres    false            �            1259    33628    borrow_borrowid_seq    SEQUENCE     �   CREATE SEQUENCE public.borrow_borrowid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
 *   DROP SEQUENCE public.borrow_borrowid_seq;
       public               postgres    false    224            �           0    0    borrow_borrowid_seq    SEQUENCE OWNED BY     K   ALTER SEQUENCE public.borrow_borrowid_seq OWNED BY public.borrow.borrowid;
          public               postgres    false    225            �            1259    33641    member    TABLE     ^  CREATE TABLE public.member (
    memberid integer NOT NULL,
    name character varying(100) NOT NULL,
    membershipstatus character varying(50),
    password character varying(255) NOT NULL,
    createdat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);
    DROP TABLE public.member;
       public         heap r       postgres    false            �            1259    33787    borrow_record_view    VIEW     x  CREATE VIEW public.borrow_record_view AS
 SELECT br.borrowid,
    br.memberid,
    m.name AS member_name,
    br.isbn,
    b.title AS book_title,
    br.copyid,
    br.borrowdate,
    br.duedate,
    br.returndate
   FROM ((public.borrow br
     LEFT JOIN public.member m ON ((br.memberid = m.memberid)))
     LEFT JOIN public.book b ON (((br.isbn)::text = (b.isbn)::text)));
 %   DROP VIEW public.borrow_record_view;
       public       v       postgres    false    219    230    230    224    224    224    224    224    224    224    219            �            1259    33634    category_categoryid_seq    SEQUENCE     �   CREATE SEQUENCE public.category_categoryid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
 .   DROP SEQUENCE public.category_categoryid_seq;
       public               postgres    false    226            �           0    0    category_categoryid_seq    SEQUENCE OWNED BY     S   ALTER SEQUENCE public.category_categoryid_seq OWNED BY public.category.categoryid;
          public               postgres    false    227            �            1259    33635    employee    TABLE     6  CREATE TABLE public.employee (
    employeeid integer NOT NULL,
    name character varying(100) NOT NULL,
    password character varying(255) NOT NULL,
    createdat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);
    DROP TABLE public.employee;
       public         heap r       postgres    false            �            1259    33640    employee_employeeid_seq    SEQUENCE     �   CREATE SEQUENCE public.employee_employeeid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
 .   DROP SEQUENCE public.employee_employeeid_seq;
       public               postgres    false    228            �           0    0    employee_employeeid_seq    SEQUENCE OWNED BY     S   ALTER SEQUENCE public.employee_employeeid_seq OWNED BY public.employee.employeeid;
          public               postgres    false    229            �            1259    33646    member_memberid_seq    SEQUENCE     �   CREATE SEQUENCE public.member_memberid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
 *   DROP SEQUENCE public.member_memberid_seq;
       public               postgres    false    230            �           0    0    member_memberid_seq    SEQUENCE OWNED BY     K   ALTER SEQUENCE public.member_memberid_seq OWNED BY public.member.memberid;
          public               postgres    false    231            �            1259    33647    reservation    TABLE     �  CREATE TABLE public.reservation (
    reservationid integer NOT NULL,
    memberid integer NOT NULL,
    isbn character varying(20) NOT NULL,
    reservationdate timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status character varying(50),
    queuenumber integer,
    pickupdeadline timestamp without time zone,
    createdat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);
    DROP TABLE public.reservation;
       public         heap r       postgres    false            �            1259    33653    reservation_reservationid_seq    SEQUENCE     �   CREATE SEQUENCE public.reservation_reservationid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
 4   DROP SEQUENCE public.reservation_reservationid_seq;
       public               postgres    false    232            �           0    0    reservation_reservationid_seq    SEQUENCE OWNED BY     _   ALTER SEQUENCE public.reservation_reservationid_seq OWNED BY public.reservation.reservationid;
          public               postgres    false    233            �           2604    33654    author authorid    DEFAULT     r   ALTER TABLE ONLY public.author ALTER COLUMN authorid SET DEFAULT nextval('public.author_authorid_seq'::regclass);
 >   ALTER TABLE public.author ALTER COLUMN authorid DROP DEFAULT;
       public               postgres    false    218    217            �           2604    33655    bookcopy copyid    DEFAULT     r   ALTER TABLE ONLY public.bookcopy ALTER COLUMN copyid SET DEFAULT nextval('public.bookcopy_copyid_seq'::regclass);
 >   ALTER TABLE public.bookcopy ALTER COLUMN copyid DROP DEFAULT;
       public               postgres    false    223    222            �           2604    33656    borrow borrowid    DEFAULT     r   ALTER TABLE ONLY public.borrow ALTER COLUMN borrowid SET DEFAULT nextval('public.borrow_borrowid_seq'::regclass);
 >   ALTER TABLE public.borrow ALTER COLUMN borrowid DROP DEFAULT;
       public               postgres    false    225    224            �           2604    33657    category categoryid    DEFAULT     z   ALTER TABLE ONLY public.category ALTER COLUMN categoryid SET DEFAULT nextval('public.category_categoryid_seq'::regclass);
 B   ALTER TABLE public.category ALTER COLUMN categoryid DROP DEFAULT;
       public               postgres    false    227    226            �           2604    33658    employee employeeid    DEFAULT     z   ALTER TABLE ONLY public.employee ALTER COLUMN employeeid SET DEFAULT nextval('public.employee_employeeid_seq'::regclass);
 B   ALTER TABLE public.employee ALTER COLUMN employeeid DROP DEFAULT;
       public               postgres    false    229    228            �           2604    33659    member memberid    DEFAULT     r   ALTER TABLE ONLY public.member ALTER COLUMN memberid SET DEFAULT nextval('public.member_memberid_seq'::regclass);
 >   ALTER TABLE public.member ALTER COLUMN memberid DROP DEFAULT;
       public               postgres    false    231    230            �           2604    33660    reservation reservationid    DEFAULT     �   ALTER TABLE ONLY public.reservation ALTER COLUMN reservationid SET DEFAULT nextval('public.reservation_reservationid_seq'::regclass);
 H   ALTER TABLE public.reservation ALTER COLUMN reservationid DROP DEFAULT;
       public               postgres    false    233    232            �          0    33597    author 
   TABLE DATA           R   COPY public.author (authorid, name, employeeid, createdat, updatedat) FROM stdin;
    public               postgres    false    217   �       �          0    33603    book 
   TABLE DATA           b   COPY public.book (isbn, title, publishyear, status, employeeid, createdat, updatedat) FROM stdin;
    public               postgres    false    219   �       �          0    33608    book_author 
   TABLE DATA           5   COPY public.book_author (isbn, authorid) FROM stdin;
    public               postgres    false    220   ��       �          0    33611    book_category 
   TABLE DATA           9   COPY public.book_category (isbn, categoryid) FROM stdin;
    public               postgres    false    221   ��       �          0    33614    bookcopy 
   TABLE DATA           N   COPY public.bookcopy (copyid, isbn, status, createdat, updatedat) FROM stdin;
    public               postgres    false    222   ��       �          0    33621    borrow 
   TABLE DATA           y   COPY public.borrow (borrowid, memberid, isbn, borrowdate, duedate, returndate, createdat, updatedat, copyid) FROM stdin;
    public               postgres    false    224   R�       �          0    33629    category 
   TABLE DATA           V   COPY public.category (categoryid, name, employeeid, createdat, updatedat) FROM stdin;
    public               postgres    false    226   ��       �          0    33635    employee 
   TABLE DATA           T   COPY public.employee (employeeid, name, password, createdat, updatedat) FROM stdin;
    public               postgres    false    228   l�       �          0    33641    member 
   TABLE DATA           b   COPY public.member (memberid, name, membershipstatus, password, createdat, updatedat) FROM stdin;
    public               postgres    false    230   X�       �          0    33647    reservation 
   TABLE DATA           �   COPY public.reservation (reservationid, memberid, isbn, reservationdate, status, queuenumber, pickupdeadline, createdat, updatedat) FROM stdin;
    public               postgres    false    232   ��       �           0    0    author_authorid_seq    SEQUENCE SET     B   SELECT pg_catalog.setval('public.author_authorid_seq', 30, true);
          public               postgres    false    218            �           0    0    bookcopy_copyid_seq    SEQUENCE SET     C   SELECT pg_catalog.setval('public.bookcopy_copyid_seq', 150, true);
          public               postgres    false    223            �           0    0    borrow_borrowid_seq    SEQUENCE SET     A   SELECT pg_catalog.setval('public.borrow_borrowid_seq', 2, true);
          public               postgres    false    225            �           0    0    category_categoryid_seq    SEQUENCE SET     F   SELECT pg_catalog.setval('public.category_categoryid_seq', 20, true);
          public               postgres    false    227            �           0    0    employee_employeeid_seq    SEQUENCE SET     F   SELECT pg_catalog.setval('public.employee_employeeid_seq', 20, true);
          public               postgres    false    229            �           0    0    member_memberid_seq    SEQUENCE SET     B   SELECT pg_catalog.setval('public.member_memberid_seq', 30, true);
          public               postgres    false    231            �           0    0    reservation_reservationid_seq    SEQUENCE SET     L   SELECT pg_catalog.setval('public.reservation_reservationid_seq', 1, false);
          public               postgres    false    233            �           2606    33662    author author_pkey 
   CONSTRAINT     V   ALTER TABLE ONLY public.author
    ADD CONSTRAINT author_pkey PRIMARY KEY (authorid);
 <   ALTER TABLE ONLY public.author DROP CONSTRAINT author_pkey;
       public                 postgres    false    217            �           2606    33664    book_author book_author_pkey 
   CONSTRAINT     f   ALTER TABLE ONLY public.book_author
    ADD CONSTRAINT book_author_pkey PRIMARY KEY (isbn, authorid);
 F   ALTER TABLE ONLY public.book_author DROP CONSTRAINT book_author_pkey;
       public                 postgres    false    220    220            �           2606    33666     book_category book_category_pkey 
   CONSTRAINT     l   ALTER TABLE ONLY public.book_category
    ADD CONSTRAINT book_category_pkey PRIMARY KEY (isbn, categoryid);
 J   ALTER TABLE ONLY public.book_category DROP CONSTRAINT book_category_pkey;
       public                 postgres    false    221    221            �           2606    33668    book book_pkey 
   CONSTRAINT     N   ALTER TABLE ONLY public.book
    ADD CONSTRAINT book_pkey PRIMARY KEY (isbn);
 8   ALTER TABLE ONLY public.book DROP CONSTRAINT book_pkey;
       public                 postgres    false    219            �           2606    33670    bookcopy bookcopy_pkey 
   CONSTRAINT     X   ALTER TABLE ONLY public.bookcopy
    ADD CONSTRAINT bookcopy_pkey PRIMARY KEY (copyid);
 @   ALTER TABLE ONLY public.bookcopy DROP CONSTRAINT bookcopy_pkey;
       public                 postgres    false    222            �           2606    33672    borrow borrow_pkey 
   CONSTRAINT     V   ALTER TABLE ONLY public.borrow
    ADD CONSTRAINT borrow_pkey PRIMARY KEY (borrowid);
 <   ALTER TABLE ONLY public.borrow DROP CONSTRAINT borrow_pkey;
       public                 postgres    false    224            �           2606    33674    category category_pkey 
   CONSTRAINT     \   ALTER TABLE ONLY public.category
    ADD CONSTRAINT category_pkey PRIMARY KEY (categoryid);
 @   ALTER TABLE ONLY public.category DROP CONSTRAINT category_pkey;
       public                 postgres    false    226            �           2606    33676    employee employee_pkey 
   CONSTRAINT     \   ALTER TABLE ONLY public.employee
    ADD CONSTRAINT employee_pkey PRIMARY KEY (employeeid);
 @   ALTER TABLE ONLY public.employee DROP CONSTRAINT employee_pkey;
       public                 postgres    false    228            �           2606    33678    member member_pkey 
   CONSTRAINT     V   ALTER TABLE ONLY public.member
    ADD CONSTRAINT member_pkey PRIMARY KEY (memberid);
 <   ALTER TABLE ONLY public.member DROP CONSTRAINT member_pkey;
       public                 postgres    false    230            �           2606    33680    reservation reservation_pkey 
   CONSTRAINT     e   ALTER TABLE ONLY public.reservation
    ADD CONSTRAINT reservation_pkey PRIMARY KEY (reservationid);
 F   ALTER TABLE ONLY public.reservation DROP CONSTRAINT reservation_pkey;
       public                 postgres    false    232            �           1259    33860    idx_author_employeeid    INDEX     N   CREATE INDEX idx_author_employeeid ON public.author USING btree (employeeid);
 )   DROP INDEX public.idx_author_employeeid;
       public                 postgres    false    217            �           1259    33861    idx_author_lower_name    INDEX     W   CREATE INDEX idx_author_lower_name ON public.author USING btree (lower((name)::text));
 )   DROP INDEX public.idx_author_lower_name;
       public                 postgres    false    217    217            �           1259    33869    idx_book_author_authorid    INDEX     T   CREATE INDEX idx_book_author_authorid ON public.book_author USING btree (authorid);
 ,   DROP INDEX public.idx_book_author_authorid;
       public                 postgres    false    220            �           1259    33870    idx_book_category_categoryid    INDEX     \   CREATE INDEX idx_book_category_categoryid ON public.book_category USING btree (categoryid);
 0   DROP INDEX public.idx_book_category_categoryid;
       public                 postgres    false    221            �           1259    33862    idx_book_employeeid    INDEX     J   CREATE INDEX idx_book_employeeid ON public.book USING btree (employeeid);
 '   DROP INDEX public.idx_book_employeeid;
       public                 postgres    false    219            �           1259    33864    idx_book_lower_title    INDEX     U   CREATE INDEX idx_book_lower_title ON public.book USING btree (lower((title)::text));
 (   DROP INDEX public.idx_book_lower_title;
       public                 postgres    false    219    219            �           1259    33863    idx_book_publishyear    INDEX     L   CREATE INDEX idx_book_publishyear ON public.book USING btree (publishyear);
 (   DROP INDEX public.idx_book_publishyear;
       public                 postgres    false    219            �           1259    33871    idx_bookcopy_isbn    INDEX     F   CREATE INDEX idx_bookcopy_isbn ON public.bookcopy USING btree (isbn);
 %   DROP INDEX public.idx_bookcopy_isbn;
       public                 postgres    false    222            �           1259    33872    idx_bookcopy_isbn_status    INDEX     U   CREATE INDEX idx_bookcopy_isbn_status ON public.bookcopy USING btree (isbn, status);
 ,   DROP INDEX public.idx_bookcopy_isbn_status;
       public                 postgres    false    222    222            �           1259    33865 !   idx_borrow_member_isbn_returndate    INDEX     j   CREATE INDEX idx_borrow_member_isbn_returndate ON public.borrow USING btree (memberid, isbn, returndate);
 5   DROP INDEX public.idx_borrow_member_isbn_returndate;
       public                 postgres    false    224    224    224            �           1259    33866    idx_borrow_member_returndate    INDEX     _   CREATE INDEX idx_borrow_member_returndate ON public.borrow USING btree (memberid, returndate);
 0   DROP INDEX public.idx_borrow_member_returndate;
       public                 postgres    false    224    224            �           1259    33858    idx_category_employeeid    INDEX     R   CREATE INDEX idx_category_employeeid ON public.category USING btree (employeeid);
 +   DROP INDEX public.idx_category_employeeid;
       public                 postgres    false    226            �           1259    33859    idx_category_lower_name    INDEX     [   CREATE INDEX idx_category_lower_name ON public.category USING btree (lower((name)::text));
 +   DROP INDEX public.idx_category_lower_name;
       public                 postgres    false    226    226            �           1259    33873    idx_member_lower_name    INDEX     W   CREATE INDEX idx_member_lower_name ON public.member USING btree (lower((name)::text));
 )   DROP INDEX public.idx_member_lower_name;
       public                 postgres    false    230    230            �           1259    33867 &   idx_reservation_isbn_status_queue_date    INDEX     �   CREATE INDEX idx_reservation_isbn_status_queue_date ON public.reservation USING btree (isbn, status, queuenumber, reservationdate);
 :   DROP INDEX public.idx_reservation_isbn_status_queue_date;
       public                 postgres    false    232    232    232    232            �           1259    33868    idx_reservation_member_status    INDEX     a   CREATE INDEX idx_reservation_member_status ON public.reservation USING btree (memberid, status);
 1   DROP INDEX public.idx_reservation_member_status;
       public                 postgres    false    232    232            �           2620    33682 (   reservation trg_adjust_reservation_queue    TRIGGER     )  CREATE TRIGGER trg_adjust_reservation_queue AFTER UPDATE ON public.reservation FOR EACH ROW WHEN ((((old.status)::text = ANY (ARRAY['Active'::text, 'Reserved'::text])) AND ((new.status)::text = ANY (ARRAY['Canceled'::text, 'PickedUp'::text])))) EXECUTE FUNCTION public.adjust_reservation_queue();
 A   DROP TRIGGER trg_adjust_reservation_queue ON public.reservation;
       public               postgres    false    232    256    232            �           2620    33683 !   borrow trg_assign_book_copy_after    TRIGGER     �   CREATE TRIGGER trg_assign_book_copy_after BEFORE INSERT OR UPDATE ON public.borrow FOR EACH ROW EXECUTE FUNCTION public.assign_book_copy();
 :   DROP TRIGGER trg_assign_book_copy_after ON public.borrow;
       public               postgres    false    257    224            �           2620    33684 %   book trg_check_book_associations_book    TRIGGER     �   CREATE CONSTRAINT TRIGGER trg_check_book_associations_book AFTER INSERT OR DELETE OR UPDATE ON public.book DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.check_book_associations();
 >   DROP TRIGGER trg_check_book_associations_book ON public.book;
       public               postgres    false    240    219            �           2620    33686 3   book_author trg_check_book_associations_book_author    TRIGGER     �   CREATE CONSTRAINT TRIGGER trg_check_book_associations_book_author AFTER INSERT OR DELETE OR UPDATE ON public.book_author DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.check_book_associations();
 L   DROP TRIGGER trg_check_book_associations_book_author ON public.book_author;
       public               postgres    false    240    220            �           2620    33688 7   book_category trg_check_book_associations_book_category    TRIGGER     �   CREATE CONSTRAINT TRIGGER trg_check_book_associations_book_category AFTER INSERT OR DELETE OR UPDATE ON public.book_category DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.check_book_associations();
 P   DROP TRIGGER trg_check_book_associations_book_category ON public.book_category;
       public               postgres    false    221    240            �           2620    33771    borrow trg_check_borrow_limit    TRIGGER     �   CREATE TRIGGER trg_check_borrow_limit BEFORE INSERT OR UPDATE ON public.borrow FOR EACH ROW EXECUTE FUNCTION public.check_borrow_limit();
 6   DROP TRIGGER trg_check_borrow_limit ON public.borrow;
       public               postgres    false    239    224            �           2620    33690 )   borrow trg_check_borrow_permission_before    TRIGGER     �   CREATE TRIGGER trg_check_borrow_permission_before BEFORE INSERT OR UPDATE ON public.borrow FOR EACH ROW EXECUTE FUNCTION public.check_borrow_permission();
 B   DROP TRIGGER trg_check_borrow_permission_before ON public.borrow;
       public               postgres    false    224    241            �           2620    33691    borrow trg_check_late_returns    TRIGGER     �   CREATE TRIGGER trg_check_late_returns AFTER UPDATE OF returndate ON public.borrow FOR EACH ROW WHEN (((old.returndate IS NULL) AND (new.returndate IS NOT NULL))) EXECUTE FUNCTION public.check_late_returns_and_freeze_member();
 6   DROP TRIGGER trg_check_late_returns ON public.borrow;
       public               postgres    false    224    224    253    224            �           2620    33769 '   reservation trg_check_reservation_limit    TRIGGER     �   CREATE TRIGGER trg_check_reservation_limit BEFORE INSERT ON public.reservation FOR EACH ROW EXECUTE FUNCTION public.check_reservation_limit();
 @   DROP TRIGGER trg_check_reservation_limit ON public.reservation;
       public               postgres    false    232    238            �           2620    33763 !   bookcopy trg_sync_bookcopy_status    TRIGGER     �   CREATE TRIGGER trg_sync_bookcopy_status AFTER UPDATE OF status ON public.bookcopy FOR EACH ROW WHEN ((((old.status)::text = 'Borrowed'::text) AND ((new.status)::text = 'Returned'::text))) EXECUTE FUNCTION public.sync_bookcopy_and_update_status_simple();
 :   DROP TRIGGER trg_sync_bookcopy_status ON public.bookcopy;
       public               postgres    false    222    236    222    222            �           2620    33764    bookcopy trg_update_on_add_copy    TRIGGER     �   CREATE TRIGGER trg_update_on_add_copy AFTER INSERT ON public.bookcopy FOR EACH ROW EXECUTE FUNCTION public.sync_bookcopy_and_update_status_simple();
 8   DROP TRIGGER trg_update_on_add_copy ON public.bookcopy;
       public               postgres    false    236    222            �           2620    33762    borrow trg_update_on_return    TRIGGER     �   CREATE TRIGGER trg_update_on_return AFTER UPDATE ON public.borrow FOR EACH ROW WHEN ((new.returndate IS NOT NULL)) EXECUTE FUNCTION public.sync_bookcopy_and_update_status_simple();
 4   DROP TRIGGER trg_update_on_return ON public.borrow;
       public               postgres    false    236    224    224            �           2620    33766 *   borrow trg_update_reservation_after_borrow    TRIGGER     �   CREATE TRIGGER trg_update_reservation_after_borrow AFTER INSERT ON public.borrow FOR EACH ROW EXECUTE FUNCTION public.update_reservation_to_pickedup();
 C   DROP TRIGGER trg_update_reservation_after_borrow ON public.borrow;
       public               postgres    false    237    224            �           2620    33695    bookcopy trg_update_updatedat    TRIGGER     �   CREATE TRIGGER trg_update_updatedat BEFORE UPDATE ON public.bookcopy FOR EACH ROW EXECUTE FUNCTION public.update_updatedat_column();
 6   DROP TRIGGER trg_update_updatedat ON public.bookcopy;
       public               postgres    false    255    222            �           2606    33696    author fk_author_employee    FK CONSTRAINT     �   ALTER TABLE ONLY public.author
    ADD CONSTRAINT fk_author_employee FOREIGN KEY (employeeid) REFERENCES public.employee(employeeid);
 C   ALTER TABLE ONLY public.author DROP CONSTRAINT fk_author_employee;
       public               postgres    false    217    228    4811            �           2606    33701 !   book_author fk_book_author_author    FK CONSTRAINT     �   ALTER TABLE ONLY public.book_author
    ADD CONSTRAINT fk_book_author_author FOREIGN KEY (authorid) REFERENCES public.author(authorid);
 K   ALTER TABLE ONLY public.book_author DROP CONSTRAINT fk_book_author_author;
       public               postgres    false    217    4784    220            �           2606    33706    book_author fk_book_author_book    FK CONSTRAINT     |   ALTER TABLE ONLY public.book_author
    ADD CONSTRAINT fk_book_author_book FOREIGN KEY (isbn) REFERENCES public.book(isbn);
 I   ALTER TABLE ONLY public.book_author DROP CONSTRAINT fk_book_author_book;
       public               postgres    false    4788    219    220            �           2606    33711 #   book_category fk_book_category_book    FK CONSTRAINT     �   ALTER TABLE ONLY public.book_category
    ADD CONSTRAINT fk_book_category_book FOREIGN KEY (isbn) REFERENCES public.book(isbn);
 M   ALTER TABLE ONLY public.book_category DROP CONSTRAINT fk_book_category_book;
       public               postgres    false    219    221    4788            �           2606    33716 '   book_category fk_book_category_category    FK CONSTRAINT     �   ALTER TABLE ONLY public.book_category
    ADD CONSTRAINT fk_book_category_category FOREIGN KEY (categoryid) REFERENCES public.category(categoryid);
 Q   ALTER TABLE ONLY public.book_category DROP CONSTRAINT fk_book_category_category;
       public               postgres    false    4807    226    221            �           2606    33721    book fk_book_employee    FK CONSTRAINT     �   ALTER TABLE ONLY public.book
    ADD CONSTRAINT fk_book_employee FOREIGN KEY (employeeid) REFERENCES public.employee(employeeid);
 ?   ALTER TABLE ONLY public.book DROP CONSTRAINT fk_book_employee;
       public               postgres    false    4811    219    228            �           2606    33726    bookcopy fk_bookcopy_book    FK CONSTRAINT     v   ALTER TABLE ONLY public.bookcopy
    ADD CONSTRAINT fk_bookcopy_book FOREIGN KEY (isbn) REFERENCES public.book(isbn);
 C   ALTER TABLE ONLY public.bookcopy DROP CONSTRAINT fk_bookcopy_book;
       public               postgres    false    219    4788    222            �           2606    33731    borrow fk_borrow_book    FK CONSTRAINT     r   ALTER TABLE ONLY public.borrow
    ADD CONSTRAINT fk_borrow_book FOREIGN KEY (isbn) REFERENCES public.book(isbn);
 ?   ALTER TABLE ONLY public.borrow DROP CONSTRAINT fk_borrow_book;
       public               postgres    false    4788    224    219            �           2606    33736    borrow fk_borrow_bookcopy    FK CONSTRAINT     ~   ALTER TABLE ONLY public.borrow
    ADD CONSTRAINT fk_borrow_bookcopy FOREIGN KEY (copyid) REFERENCES public.bookcopy(copyid);
 C   ALTER TABLE ONLY public.borrow DROP CONSTRAINT fk_borrow_bookcopy;
       public               postgres    false    222    4799    224            �           2606    33741    borrow fk_borrow_member    FK CONSTRAINT     ~   ALTER TABLE ONLY public.borrow
    ADD CONSTRAINT fk_borrow_member FOREIGN KEY (memberid) REFERENCES public.member(memberid);
 A   ALTER TABLE ONLY public.borrow DROP CONSTRAINT fk_borrow_member;
       public               postgres    false    224    4814    230            �           2606    33746    category fk_category_employee    FK CONSTRAINT     �   ALTER TABLE ONLY public.category
    ADD CONSTRAINT fk_category_employee FOREIGN KEY (employeeid) REFERENCES public.employee(employeeid);
 G   ALTER TABLE ONLY public.category DROP CONSTRAINT fk_category_employee;
       public               postgres    false    228    226    4811            �           2606    33751    reservation fk_reservation_book    FK CONSTRAINT     |   ALTER TABLE ONLY public.reservation
    ADD CONSTRAINT fk_reservation_book FOREIGN KEY (isbn) REFERENCES public.book(isbn);
 I   ALTER TABLE ONLY public.reservation DROP CONSTRAINT fk_reservation_book;
       public               postgres    false    219    4788    232            �           2606    33756 !   reservation fk_reservation_member    FK CONSTRAINT     �   ALTER TABLE ONLY public.reservation
    ADD CONSTRAINT fk_reservation_member FOREIGN KEY (memberid) REFERENCES public.member(memberid);
 K   ALTER TABLE ONLY public.reservation DROP CONSTRAINT fk_reservation_member;
       public               postgres    false    232    230    4814            �     x����J�@�ϓ��h��_��R�VkZA/c2$��ݲ�}{W��a��0�����>ƣ���(H��X$�")Pe�Z�E���<�o��e�;�g?�1�
9�M=�M��8i�LH���['��6��
�U�i�s��?BL�>��g>5[(��%�ȟ��#3,��
n��ƻ�B%d��@�#����\+!I%p?5X�zp�����B��r"��V����A�H��BT�qf�����G�f�6�-�Oj�*���_Y{���qEߙ��-      �   _  x���Mo�8��ʯ �C�	�~)���`7ۢ6zꅖ���,������q+�)PԤ�|�rf�4�K%�U!J+�C����.�nY�
��9�s�^J{)Յ�Z�8��.A]*y!�
���ae,���yq����}�}�[��מ�c[�ַ�;6�c�	]�Z�.���͵�9�YD�W�k��M��Cs��P��PxJI�9J������e�i}G�'��܀1ڈ�����*�wqE�!��N�X*���bP�6.��67Ԣ�jҧ�B��4=8�j��eס�#�G�e�����fN�@�87�To�j�7D�"�	!9XD��߱]!����w�Qr�)O��`P�]�}l���G�w�'���8��9��X��/�컵�,�;�����������VH�QI{ք���̵��H�O��R;p#HP\7��j��lc}�>lz�ῇ�wC$��젭r�r[�O��ݸ��zҨ�]���[�|��I$	%M	`7N3_���n�]�e�;h�S\A㫴���]h���$R	OI�]�fY��wj�n`���@�+�*/f�Y�>�f��H
�?R#���˾&˵�P�"	"|����7{S��t"O��K�b�!�����E�S�ż���ɜ��`�?�FL��=�
�u�xw���^�U\�x׺��F%�������·�N5��S|�7�~*�!����w�A�T�{HY�}}{~��1�Le���ǸϦ�� S@�� �� 05 d0 �` �` 86 d0 L  S@�� �� pl �` �� �pj �` � 3 ���������0�pj �` � 3 �� e Lf�oggg� ���      �     x�]�K�� ��0#��?���?ǸӒî��;��L7h�llRlKn&g��7�*�m�͠�^�p�4Jε����c1�@Q,���$貛C!s{���L+�de����`F�/���M���s���|�ؒ"��c�$ށ`�:�A��vP�~��_г�[��F־��ւ��6G�<��ೄ^�R��P�J���O�R�CRl�k�3cVK�jٳ��ݘ�ՐY��z6���������j��U�����]���I�e      �   �   x�]��u�0D�o��`�K��#����� �Z9Ÿ�mQƼ֫]�}��7$T!2m��n&BS�(��H�����y������H�@5�$y�I�~<��D-TSa��G(��M/AL{��^��T�-�n�0�#�"D�>����q�`����?�y���u����8G���mأ}����ϑ��<�������F�рh@4 �D�ـl@6 ��d�ـv���BJ�/      �   �  x���;��@E�x�
o`���G��̉800p���JAM橫��A��~-2^�\�i�=_������z��x��bb�*�*�E��y�k�i��7���Us����Opy�q�-�yI����|i������Ó��ꥋ����|�d��Ȋ��`oÞ�;����~b`>�J�F��̸L�sL�A�I��2���,]}p���3)���rx�T���`�)2���`���������N<�2�mz��zh]h�=)�#\+���Ѡ�`<�FŇFl<ip��{�ԣ|
 .�0gRƊr�>�4h4x&%Euf����ǣ��mˬ��Ť�E��s�QlT��ShPiО6Ï��N�A��l�[r���;N|�-rN�o�ap>�r��?6�h�i0
دs#ip��,`�4:n�R�~R�Ҡ�`MJ�h6��kR���4�h�&�_�Р�`MJ����44X��?��A��KR�_�ֆ�-4X�b�n���KR��mv�����w��hpàJ�
�.Sq�p��x�)����50���2qq�b�L��
.*.�� �r�q1p�f��uT.N\,���Qݴh��%3|�a����%3�/=j��Kf�=�pqӢ�� ��kf�O�kf���.�� �'kf������53@�Kf�=�i1�_/��_���      �   V   x���A
� ��+�%�Y5���G-�P�`ao��E��P�G���$8��"��� �{���UV�]ZZ�QԿ鯰D�33��.[      �   �   x��ҽ�0��x
_ R��с����K�Th�-�.}{u���?_�K�r5o��58�d�d�T�^�^��Ս����c���������A$n�.!�qΐDD��㼛m�PD��%ɽ�4D��5>�gΖ(h&$sdh��ar�ݺ�#5����{#Z��(�(�P      �   �   x������0E��W�$X/[N��ma�,l��8x�d�b��o��us9\�pIÄ��atB*��4�Z�j�B�=h�om���xU���o��zk���R�k�9MЧ~lmW���#�7����V�|�<�L��V�(Ӏgz��{GKͷ�B^9���ζ�(����o+-�х�.��_�
)��P��-���rx�qr>��H���WU����3      �   3  x���Mo�@��ï�?���6��!Z)�T��e0va?���%��C+��a}����w�!�e)�+���T����剃�GA=һ �R�I��y�%Qx��(�W{�]-�lU+����hs�����W&o���J�fSg�NPm�4���`&�)[ל��YYת�u|��[�9|�(��l��t�l��0{�09!{Vc��u����5���CϞ�~����\�+E�Y�VT6q����0�f�Z�@�du��<È���{�!�4�a�䞌��t�|=�i�U�����Y���b�Qbu{GT�D3 ��ܱ����$� �9L���0��Bw���0?qu6T�����u�q7��ܸ3[�?�B�c�r�P�Px��T㏔�~W$��Wiv��=�o�(�E�,g�%��n�V���NļH��J]Ar1.|͉(J���M���;C����i��{��� ��wJ���I�]�U���VvG,%vc��y�=��$��'4�O>`�/���b_l�_��w�9�xrXr���m[�N���oF]�A�$��0ݏF�?$�K      �      x������ � �     