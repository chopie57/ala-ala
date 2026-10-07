import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import piexif
from datetime import datetime
from fractions import Fraction
import io
import os

# =========================
# BULAN & HARI INDONESIA (STABIL)
# =========================
hari_list = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

# =========================
# GPS CONVERSION
# =========================
def dms_to_decimal(dms, ref):
    deg, minute, sec = dms
    val = deg[0]/deg[1] + minute[0]/minute[1]/60 + sec[0]/sec[1]/3600
    return val if ref in ['N', 'E'] else -val

def decimal_to_dms(val):
    val = abs(val)
    deg = int(val)
    minute_float = (val - deg) * 60
    minute = int(minute_float)
    sec_float = (minute_float - minute) * 60
    sec_fraction = Fraction(sec_float).limit_denominator(1000000)
    return (
        (deg, 1),
        (minute, 1),
        (sec_fraction.numerator, sec_fraction.denominator)
    )

def bersihkan_exif_error(exif_dict):
    if "Exif" in exif_dict and 41729 in exif_dict["Exif"]:
        del exif_dict["Exif"][41729]
    return exif_dict

# =========================
# WATERMARK
# =========================
def tambah_watermark(img, tanggal_obj, lat, lon, logo_path="logo.png"):
    width, height = img.size
    font_judul_size = int(width * 0.028)
    font_teks_size = int(width * 0.022)

    try:
        font_judul = ImageFont.truetype("RobotoCondensed-Bold.ttf", font_judul_size)
        font_teks = ImageFont.truetype("RobotoCondensed-Regular.ttf", font_teks_size)
    except:
        font_judul = ImageFont.load_default()
        font_teks = ImageFont.load_default()

    hari_id = hari_list[tanggal_obj.weekday()]
    tanggal_str = tanggal_obj.strftime("%d/%m/%Y")
    jam_str = tanggal_obj.strftime("%H:%M:%S")

    datetime_line = f"{hari_id}, {tanggal_str} {jam_str}"

    lines = [
        ("PENDAMPING SOSIAL", font_judul),
        (datetime_line, font_teks),
        (f"{lat}, {lon}", font_teks),
    ]

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    margin_x = int(width * 0.025)
    margin_y = int(height * 0.035)
    spacing = int(font_teks_size * 0.45)
    extra_gap = int(font_teks_size * 0.9)

    heights = []
    for text, font_used in lines:
        bbox = draw.textbbox((0, 0), text, font=font_used)
        heights.append(bbox[3] - bbox[1])

    total_height = heights[0] + extra_gap + heights[1] + spacing + heights[2]
    y_start = height - margin_y - total_height

    # LOGO
    if os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo_width = int(width * 0.18)
            ratio = logo_width / logo.size[0]
            logo_height = int(logo.size[1] * ratio)
            logo = logo.resize((logo_width, logo_height))
            overlay.paste(logo, (margin_x, y_start - logo_height - spacing), logo)
        except:
            pass

    # GARIS KUNING
    garis_width = int(width * 0.004)
    garis_height = heights[1] + spacing + heights[2]
    garis_x = margin_x
    tanggal_y = y_start + heights[0] + extra_gap
    garis_y = tanggal_y

    draw.rectangle(
        [garis_x, garis_y, garis_x + garis_width, garis_y + garis_height],
        fill=(255, 204, 0, 220)
    )

    teks_offset = garis_width + int(width * 0.012)

    # TEKS
    y = y_start
    for i, (text, font_used) in enumerate(lines):
        bbox = draw.textbbox((0, 0), text, font=font_used)
        text_h = bbox[3] - bbox[1]
        x_pos = margin_x if i == 0 else margin_x + teks_offset

        draw.text((x_pos + 2, y + 2), text, font=font_used, fill=(0, 0, 0, 120))
        draw.text((x_pos, y), text, font=font_used, fill=(255, 255, 255, 255))

        if i == 0:
            y += text_h + extra_gap
        else:
            y += text_h + spacing

    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    return img.convert("RGB")

# =========================
# RESIZE <600KB (Diubah untuk Memory/BytesIO)
# =========================
def resize_if_needed(img_bytes):
    min_target_size = 600 * 1024
    if len(img_bytes) >= min_target_size:
        return img_bytes

    img = Image.open(io.BytesIO(img_bytes))
    attempt = 0
    
    while attempt < 5:
        w, h = img.size
        img = img.resize((int(w * 1.5), int(h * 1.5)))
        
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=95)
        
        if output.tell() >= min_target_size:
            return output.getvalue()
        attempt += 1

    output = io.BytesIO()
    img.save(output, format="JPEG", quality=95)
    return output.getvalue()


# =========================
# GUI WEB STREAMLIT
# =========================
st.set_page_config(page_title="Exif & Watermark Editor", layout="centered")
st.title("📸 Exif & Watermark Editor")

# State Management untuk form
if "lat" not in st.session_state:
    st.session_state.lat = ""
if "lon" not in st.session_state:
    st.session_state.lon = ""

uploaded_file = st.file_uploader("📂 Buka Gambar (JPG/JPEG)", type=["jpg", "jpeg"])

if uploaded_file is not None:
    # Proses file ke memori
    file_bytes = uploaded_file.read()
    processed_bytes = resize_if_needed(file_bytes)
    
    img = Image.open(io.BytesIO(processed_bytes))
    st.image(img, caption="Preview Gambar", use_container_width=True)

    # Baca Metadata
    try:
        exif = piexif.load(processed_bytes)
        date_bytes = exif["Exif"].get(piexif.ExifIFD.DateTimeOriginal)
        
        if date_bytes:
            t = datetime.strptime(date_bytes.decode(), "%Y:%m:%d %H:%M:%S")
        else:
            t = datetime.now()

        make = exif["0th"].get(piexif.ImageIFD.Make, b"").decode(errors="ignore").strip() or "Xiaomi"
        model = exif["0th"].get(piexif.ImageIFD.Model, b"").decode(errors="ignore").strip() or "2312DRA50G"
        
        gps = exif.get("GPS", {})
        if 2 in gps and 1 in gps and 4 in gps and 3 in gps and not st.session_state.lat:
            lat = dms_to_decimal(gps[2], gps[1].decode())
            lon = dms_to_decimal(gps[4], gps[3].decode())
            st.session_state.lat = f"{lat:.6f}"
            st.session_state.lon = f"{lon:.6f}"

    except Exception as e:
        st.warning(f"Metadata tidak ditemukan atau gagal dibaca: {e}")
        t = datetime.now()
        make = "Xiaomi"
        model = "2312DRA50G"

    # Form Editor
    st.subheader("📝 Edit Metadata")
    
    col1, col2 = st.columns(2)
    with col1:
        input_tgl = st.text_input("Tanggal (DD:MM:YYYY)", t.strftime("%d:%m:%Y"))
        input_lat = st.text_input("Latitude", st.session_state.lat)
        input_make = st.text_input("Kamera (Make)", make)
    with col2:
        input_jam = st.text_input("Jam (HH:MM:SS)", t.strftime("%H:%M:%S"))
        input_lon = st.text_input("Longitude", st.session_state.lon)
        input_model = st.text_input("Model", model)

    # Fitur Copy Koordinat
    st.markdown("---")
    copy_file = st.file_uploader("📌 Copy Koordinat dari Gambar Lain", type=["jpg", "jpeg"])
    if copy_file:
        try:
            exif_copy = piexif.load(copy_file.read())
            gps_copy = exif_copy.get("GPS", {})
            if 2 in gps_copy and 1 in gps_copy and 4 in gps_copy and 3 in gps_copy:
                c_lat = dms_to_decimal(gps_copy[2], gps_copy[1].decode())
                c_lon = dms_to_decimal(gps_copy[4], gps_copy[3].decode())
                st.session_state.lat = f"{c_lat:.6f}"
                st.session_state.lon = f"{c_lon:.6f}"
                st.success("Koordinat berhasil disalin! Refresh untuk melihat perubahan di form.")
                st.rerun()
            else:
                st.error("Gambar sumber tidak memiliki data GPS.")
        except Exception as e:
            st.error(f"Gagal membaca koordinat: {e}")

    # Proses Penyimpanan
    if st.button("💾 Proses & Simpan Metadata", use_container_width=True):
        try:
            # Parse Tanggal
            tgl_obj = datetime.strptime(f"{input_tgl} {input_jam}", "%d:%m:%Y %H:%M:%S")
            lat_val = float(input_lat)
            lon_val = float(input_lon)

            # Update Exif Dictionary
            exif_dict = piexif.load(processed_bytes)
            
            tanggal_full = tgl_obj.strftime("%Y:%m:%d %H:%M:%S").encode()
            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = tanggal_full
            exif_dict["0th"][piexif.ImageIFD.Make] = input_make.encode()
            exif_dict["0th"][piexif.ImageIFD.Model] = input_model.encode()

            exif_dict["GPS"] = {
                piexif.GPSIFD.GPSLatitudeRef: b'N' if lat_val >= 0 else b'S',
                piexif.GPSIFD.GPSLatitude: decimal_to_dms(lat_val),
                piexif.GPSIFD.GPSLongitudeRef: b'E' if lon_val >= 0 else b'W',
                piexif.GPSIFD.GPSLongitude: decimal_to_dms(lon_val),
            }

            exif_dict = bersihkan_exif_error(exif_dict)
            exif_bytes = piexif.dump(exif_dict)

            # Tambahkan Watermark
            img_watermarked = tambah_watermark(
                img,
                tgl_obj,
                f"{lat_val:.6f}",
                f"{lon_val:.6f}"
            )

            # Simpan ke memori (buffer) untuk didownload
            output_buffer = io.BytesIO()
            img_watermarked.save(output_buffer, format="JPEG", exif=exif_bytes)
            final_bytes = output_buffer.getvalue()

            st.success("Gambar berhasil diproses! Silakan unduh di bawah ini.")
            
            # Tombol Download
            st.download_button(
                label="⬇️ Unduh Gambar Hasil",
                data=final_bytes,
                file_name=f"edited_{uploaded_file.name}",
                mime="image/jpeg"
            )

        except Exception as e:
            st.error(f"Terjadi kesalahan saat memproses: {e}")