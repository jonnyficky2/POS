from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
import sqlite3
from datetime import datetime
import random
import io
import io
from openpyxl import Workbook
app = Flask(__name__)
app.secret_key = "smartwarung"

USERS = {
    "kasir": "123",
    "owner": "123"
}

BARANG = {
    "1001": {"nama": "Indomie Goreng", "harga": 3500, "stok": 50},
    "1002": {"nama": "Aqua Botol 600ml", "harga": 5000, "stok": 100},
    "1003": {"nama": "Teh Botol Sosro", "harga": 6000, "stok": 40},
    "1004": {"nama": "Chitato Sapi Panggang", "harga": 12000, "stok": 30},
    "1005": {"nama": "Taro Seaweed", "harga": 8000, "stok": 25},
    "1006": {"nama": "Kopi Kenangan Mantan", "harga": 10000, "stok": 20},
    "1007": {"nama": "Sari Roti Coklat", "harga": 7000, "stok": 35},
    "1008": {"nama": "Pop Mie Ayam", "harga": 6500, "stok": 45},
    "1009": {"nama": "Le Minerale 600ml", "harga": 4500, "stok": 80},
    "1010": {"nama": "Susu Ultra Coklat 250ml", "harga": 7500, "stok": 60}
}

TRANSFER_INFO = {
    "bank": "BCA",
    "norek": "1234567890",
    "nama": "SMART WARUNG"
}

METODE_PEMBAYARAN = ["tunai", "qris", "transfer"]

# Custom Filter untuk Format Rupiah
@app.template_filter('rupiah')
def rupiah_filter(value):
    return f"Rp {value:,.0f}".replace(",", ".")

@app.route("/")
def login():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def proses_login():
    username = request.form["username"]
    password = request.form["password"]

    if username in USERS and password == USERS[username]:
        session["user"] = username
        return redirect(url_for("dashboard"))

    flash("Username atau Password Salah", "danger")
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM transaksi")
    jumlah_transaksi = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(total) FROM transaksi")
    total_penjualan = cursor.fetchone()[0]

    conn.close()

    if total_penjualan is None:
        total_penjualan = 0

    return render_template(
        "dashboard.html",
        jumlah_transaksi=jumlah_transaksi,
        total_penjualan=total_penjualan
    )

@app.route("/stok", methods=["GET", "POST"])
def stok():

    if "user" not in session:
        return redirect("/")

    pesan = None
    error = None

    if request.method == "POST":
        barcode = request.form.get("barcode", "").strip()

        try:
            jumlah = int(request.form.get("jumlah", 0))
        except ValueError:
            jumlah = 0

        if barcode not in BARANG:
            flash("Barcode barang tidak ditemukan!", "danger")
        elif jumlah <= 0:
            flash("Jumlah stok harus lebih dari 0!", "warning")
        else:
            BARANG[barcode]["stok"] += jumlah
            flash(f"Stok {BARANG[barcode]['nama']} berhasil ditambah {jumlah}.", "success")
        return redirect(url_for("stok"))

    return render_template(
        "stok.html",
        barang=BARANG,
        total_produk=len(BARANG),
        stok_menipis=sum(1 for detail in BARANG.values() if detail["stok"] <= 10),
        total_unit=sum(detail["stok"] for detail in BARANG.values()),
        pesan=pesan,
        error=error
    )

@app.route("/transaksi", methods=["GET", "POST"])
def transaksi():

    if "user" not in session:
        return redirect("/")

    if "keranjang" not in session:
        session["keranjang"] = []
        
    error = None

    if request.method == "POST":

        barcode = request.form["barcode"]

        if barcode in BARANG:

            barang = BARANG[barcode]

            found_in_cart = False
            # Cari apakah barang sudah ada di keranjang
            for item in session["keranjang"]:
                if item["barcode"] == barcode:
                    item["qty"] += 1
                    item["subtotal"] = item["qty"] * item["harga_satuan"]
                    found_in_cart = True
                    break

            # Jika barang belum ada di keranjang, tambahkan sebagai item baru
            if not found_in_cart:
                session["keranjang"].append({
                    "barcode": barcode,
                    "nama": barang["nama"],
                    "harga_satuan": barang["harga"], # Harga per unit
                    "qty": 1,
                    "subtotal": barang["harga"] # Harga awal = harga satuan * 1
                })
            
            # Pastikan session dimodifikasi terlepas dari apakah barang baru atau sudah ada
            session.modified = True 
        else:
            flash("Barang tidak ditemukan!", "danger")

    total = sum(item["subtotal"] for item in session["keranjang"])

    return render_template(
        "transaksi.html",
        keranjang=session["keranjang"],
        total=total,
        transfer_info=TRANSFER_INFO
    )

@app.route("/get_qris")
def get_qris():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({
        "qris_image_url": url_for('static', filename='qris.svg'),
        "transfer_info": TRANSFER_INFO
    })

@app.route("/bayar", methods=["POST"])
def bayar():

    if "user" not in session:
        return redirect("/")

    if not session.get("keranjang"):
        return render_template(
            "hasil_bayar.html",
            sukses=False,
            pesan="Tidak ada barang di keranjang!",
            total=0
        )

    total = sum(
        item["subtotal"]
        for item in session["keranjang"]
    )

    metode_pembayaran = request.form.get("metode_pembayaran", "tunai")

    if metode_pembayaran not in METODE_PEMBAYARAN:
        return render_template(
            "hasil_bayar.html",
            sukses=False,
            pesan="Metode pembayaran tidak valid!",
            total=total
        )

    bayar = total
    kembalian = 0

    if metode_pembayaran == "tunai":
        try:
            bayar = int(request.form["bayar"])
        except ValueError:
            return render_template("hasil_bayar.html", sukses=False, pesan="Input uang tidak valid!", total=total)

        if bayar < total:

            return render_template(
                "hasil_bayar.html",
                sukses=False,
                pesan="Uang tidak cukup",
                total=total
            )

        kembalian = bayar - total

    nomor_struk = random.randint(10000,99999)

    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        tanggal = datetime.now().strftime("%d-%m-%Y %H:%M")
        kasir = session["user"]
        
        cursor.execute(
            "INSERT INTO transaksi(tanggal,kasir,total) VALUES(?,?,?)",
            (tanggal, kasir, total)
        )
        conn.commit()
        
        # Kurangi stok barang
        for item in session["keranjang"]:
            barcode = item["barcode"]
            if barcode in BARANG:
                BARANG[barcode]["stok"] -= item["qty"]
                
    except sqlite3.OperationalError as e:
        return f"<h1>Error Database: {e}</h1><p>Solusi: Matikan server, hapus file <b>database.db</b>, jalankan ulang <b>python init_db.py</b>, lalu jalankan server kembali.</p>"
    finally:
        conn.close()

    session["keranjang"] = []
    session.modified = True

    return render_template(
        "hasil_bayar.html",
        sukses=True,
        total=total,
        bayar=bayar,
        kembalian=kembalian,
        nomor_struk=nomor_struk,
        metode_pembayaran=metode_pembayaran,
        transfer_info=TRANSFER_INFO
    )

@app.route("/laporan")
def laporan():

    if "user" not in session:
        return redirect("/")

    tgl_awal = request.args.get('tgl_awal', '')
    tgl_akhir = request.args.get('tgl_akhir', '')

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM transaksi"
    params = []
    if tgl_awal and tgl_akhir:
        # Konversi format DD-MM-YYYY ke YYYY-MM-DD untuk perbandingan SQL
        query += " WHERE substr(tanggal, 7, 4) || '-' || substr(tanggal, 4, 2) || '-' || substr(tanggal, 1, 2) BETWEEN ? AND ?"
        params = [tgl_awal, tgl_akhir]

    cursor.execute(query, params)
    data = cursor.fetchall()

    sum_query = "SELECT SUM(total) FROM transaksi"
    if tgl_awal and tgl_akhir:
        sum_query += " WHERE substr(tanggal, 7, 4) || '-' || substr(tanggal, 4, 2) || '-' || substr(tanggal, 1, 2) BETWEEN ? AND ?"
    
    cursor.execute(sum_query, params)
    total_penjualan = cursor.fetchone()[0]

    if total_penjualan is None:
        total_penjualan = 0

    conn.close()

    tanggal_cetak = datetime.now().strftime("%d-%m-%Y")

    return render_template(
        "laporan.html",
        data=data,
        total_penjualan=total_penjualan,
        tgl_awal=tgl_awal,
        tgl_akhir=tgl_akhir
    )

@app.route("/ekspor_laporan")
def ekspor_laporan():
    if "user" not in session:
        return redirect("/")

    tgl_awal = request.args.get('tgl_awal', '')
    tgl_akhir = request.args.get('tgl_akhir', '')

    try:
        conn = sqlite3.connect("database.db")
        conn.row_factory = sqlite3.Row
        query = "SELECT id, tanggal, kasir, total FROM transaksi"
        params = []
        
        if tgl_awal and tgl_akhir:
            query += " WHERE substr(tanggal, 7, 4) || '-' || substr(tanggal, 4, 2) || '-' || substr(tanggal, 1, 2) BETWEEN ? AND ?"
            params = [tgl_awal, tgl_akhir]

        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        # Membuat buffer memori dan workbook excel
        output = io.BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.title = 'Laporan Transaksi'
        
        # Tambahkan Header
        ws.append(['ID', 'Tanggal', 'Kasir', 'Total'])
        
        # Tambahkan Data
        for row in rows:
            ws.append([row['id'], row['tanggal'], row['kasir'], row['total']])
            
        wb.save(output)
        output.seek(0)
        
        filename = f"Laporan_Transaksi_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        flash(f"Gagal mengekspor data: {str(e)}", "danger")
        return redirect(url_for("laporan"))

@app.route("/hapus/<int:id>")
def hapus(id):

    if "user" not in session:
        return redirect("/")

    if session.get("user") != "owner":
        return redirect("/laporan")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM transaksi WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/laporan")

@app.route("/hapus_laporan")
def hapus_laporan():

    if "user" not in session:
        return redirect("/")

    if session.get("user") != "owner":
        return redirect("/laporan")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM transaksi")

    conn.commit()
    conn.close()

    return redirect("/laporan")

@app.route("/hapus_item/<int:index>")
def hapus_item(index):

    if "user" not in session:
        return redirect("/")

    keranjang = session.get("keranjang", [])

    if index < len(keranjang):
        keranjang.pop(index)

    session["keranjang"] = keranjang
    session.modified = True

    return redirect("/transaksi")

@app.route("/tambah_qty/<int:index>")
def tambah_qty(index):

    if "user" not in session:
        return redirect("/")

    keranjang = session.get("keranjang", [])

    if index < len(keranjang):
        keranjang[index]["qty"] += 1
        keranjang[index]["subtotal"] = keranjang[index]["qty"] * keranjang[index]["harga_satuan"]
        
        total_keranjang = sum(item["subtotal"] for item in keranjang)

    session["keranjang"] = keranjang
    session.modified = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            "qty": keranjang[index]["qty"],
            "subtotal": keranjang[index]["subtotal"],
            "total": total_keranjang
        })

    return redirect("/transaksi")

@app.route("/kurang_qty/<int:index>")
def kurang_qty(index):

    if "user" not in session:
        return redirect("/")

    keranjang = session.get("keranjang", [])

    if index < len(keranjang):
        if keranjang[index]["qty"] > 1:
            keranjang[index]["qty"] -= 1
            keranjang[index]["subtotal"] = keranjang[index]["qty"] * keranjang[index]["harga_satuan"]
            
            total_keranjang = sum(item["subtotal"] for item in keranjang)

    session["keranjang"] = keranjang
    session.modified = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            "qty": keranjang[index]["qty"],
            "subtotal": keranjang[index]["subtotal"],
            "total": total_keranjang
        })

    return redirect("/transaksi")

@app.route("/batal_transaksi")
def batal_transaksi():

    if "user" not in session:
        return redirect("/")

    session["keranjang"] = []

    return redirect("/transaksi")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
