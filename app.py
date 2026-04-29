from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect("hotel.db")
    conn.row_factory = sqlite3.Row
    return conn

def get_summary_stats():
    conn = get_db_connection()
    stats = {
        "building_count": conn.execute("SELECT COUNT(*) AS count FROM building").fetchone()["count"],
        "room_count": conn.execute("SELECT COUNT(*) AS count FROM room").fetchone()["count"],
        "available_room_count": conn.execute("SELECT COUNT(*) AS count FROM room WHERE roomStatus = 'available'").fetchone()["count"],
        "event_count": conn.execute("SELECT COUNT(*) AS count FROM event").fetchone()["count"],
        "total_revenue": conn.execute("SELECT ROUND(COALESCE(SUM(amount), 0), 2) AS total FROM charge").fetchone()["total"]
    }
    conn.close()
    return stats

@app.route("/")
def home():
    return render_template("index.html", stats=get_summary_stats())

@app.route("/rooms")
def rooms():
    conn = get_db_connection()
    rooms = conn.execute("""
        SELECT r.roomID, r.roomNumber, r.baseRate, r.roomStatus,
               f.floorNumber, w.wingName, b.buildingName
        FROM room r
        JOIN floor f ON r.floorID = f.floorID
        JOIN wing w ON f.wingID = w.wingID
        JOIN building b ON w.buildingID = b.buildingID
        ORDER BY b.buildingName, w.wingName, f.floorNumber, r.roomNumber
    """).fetchall()
    conn.close()
    return render_template("rooms.html", rooms=rooms)

@app.route("/room/<int:room_id>")
def room_detail(room_id):
    conn = get_db_connection()

    room = conn.execute("""
        SELECT r.roomID, r.roomNumber, r.baseRate, r.roomStatus,
               f.floorNumber, f.smokingDesignation,
               w.wingName, w.proximityPool, w.proximityParking, w.handicappedAccess,
               b.buildingName,
               srd.capacity, srd.smoking, srd.hasToilet, srd.hasTV, srd.hasPhone,
               mrd.seatingCapacity
        FROM room r
        JOIN floor f ON r.floorID = f.floorID
        JOIN wing w ON f.wingID = w.wingID
        JOIN building b ON w.buildingID = b.buildingID
        LEFT JOIN sleeping_room_details srd ON r.roomID = srd.roomID
        LEFT JOIN meeting_room_details mrd ON r.roomID = mrd.roomID
        WHERE r.roomID = ?
    """, (room_id,)).fetchone()

    if room is None:
        conn.close()
        return render_template("error.html", error="Room not found.")

    beds = conn.execute("""
        SELECT bt.size, rb.quantity
        FROM room_bed rb
        JOIN bed_type bt ON rb.bedTypeId = bt.bedTypeId
        WHERE rb.roomId = ?
    """, (room_id,)).fetchall()

    adjacent_rooms = conn.execute("""
        SELECT r.roomNumber, ra.hasPrivateDoor
        FROM room_adjacency ra
        JOIN room r ON ra.roomId2 = r.roomID
        WHERE ra.roomId1 = ?
        UNION
        SELECT r.roomNumber, ra.hasPrivateDoor
        FROM room_adjacency ra
        JOIN room r ON ra.roomId1 = r.roomID
        WHERE ra.roomId2 = ?
    """, (room_id, room_id)).fetchall()

    room_image = "default-room.jpg"
    if room["buildingName"] == "Conference Center":
        room_image = "meeting-room.jpg"
    elif room["baseRate"] >= 220:
        room_image = "suite-room.jpg"
    elif room["baseRate"] >= 150:
        room_image = "standard-room.jpg"

    conn.close()
    return render_template("room_detail.html", room=room, beds=beds, adjacent_rooms=adjacent_rooms, room_image=room_image)

@app.route("/availability", methods=["GET", "POST"])
def availability():
    available_rooms = None
    start = None
    end = None

    if request.method == "POST":
        start = request.form.get("start")
        end = request.form.get("end")

        conn = get_db_connection()
        available_rooms = conn.execute("""
            SELECT r.roomID, r.roomNumber, r.baseRate, r.roomStatus
            FROM room r
            WHERE r.roomStatus = 'available'
              AND r.roomID NOT IN (
                SELECT rr.roomId
                FROM room_reservation rr
                WHERE rr.startDateTime < ?
                  AND rr.endDateTime > ?
            )
            ORDER BY r.roomNumber
        """, (end, start)).fetchall()
        conn.close()

    return render_template("availability.html", available_rooms=available_rooms, start=start, end=end)

@app.route("/events", methods=["GET", "POST"])
def events():
    conn = get_db_connection()

    keyword = request.form.get("keyword", "").strip() if request.method == "POST" else ""
    date = request.form.get("date", "").strip() if request.method == "POST" else ""

    query = """
        SELECT e.eventId, e.startDate, e.endDate,
               e.estimatedAttendance, e.estimatedGuestRooms,
               p.first_name, p.last_name,
               r.roomNumber, er.usageSlot
        FROM event e
        JOIN host h ON e.hostId = h.hostId
        JOIN person p ON h.hostId = p.personId
        JOIN event_room er ON e.eventId = er.eventId
        JOIN room r ON er.roomId = r.roomID
        WHERE 1 = 1
    """
    params = []

    if keyword:
        query += " AND (p.first_name LIKE ? OR p.last_name LIKE ?)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if date:
        query += " AND date(e.startDate) <= date(?) AND date(e.endDate) >= date(?)"
        params.extend([date, date])

    query += " ORDER BY e.eventId, er.usageSlot"

    events = conn.execute(query, params).fetchall()

    summary = conn.execute("""
        SELECT COUNT(*) AS totalEvents,
               COALESCE(SUM(estimatedAttendance), 0) AS totalAttendance,
               COALESCE(SUM(estimatedGuestRooms), 0) AS totalGuestRooms
        FROM event
    """).fetchone()

    conn.close()
    return render_template("events.html", events=events, summary=summary, keyword=keyword, date=date)

@app.route("/access")
def access():
    conn = get_db_connection()

    access_logs = conn.execute("""
        SELECT cal.logId, cal.cardId, r.roomNumber,
               cal.accessTime, cal.direction,
               p.first_name, p.last_name
        FROM card_access_log cal
        JOIN access_card ac ON cal.cardId = ac.cardId
        JOIN person p ON ac.guestId = p.personId
        JOIN room r ON cal.roomId = r.roomID
        ORDER BY cal.accessTime DESC
    """).fetchall()

    conn.close()
    return render_template("access.html", access_logs=access_logs)

@app.route("/checkin", methods=["GET", "POST"])
def checkin():
    conn = get_db_connection()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "checkin":
            guest_id = request.form.get("guestId")
            room_id = request.form.get("roomId")
            check_in = request.form.get("checkIn")
            check_out = request.form.get("checkOut")
            next_id = conn.execute("SELECT COALESCE(MAX(stayId), 0) + 1 AS nextId FROM stay").fetchone()["nextId"]

            conn.execute("INSERT INTO stay VALUES (?, ?, ?, ?)", (next_id, guest_id, check_in, check_out))
            conn.execute("INSERT INTO room_assignment VALUES (?, ?, ?, ?)", (next_id, room_id, check_in, check_out))
            conn.execute("UPDATE room SET roomStatus = 'occupied' WHERE roomID = ?", (room_id,))
            conn.commit()

        elif action == "checkout":
            stay_id = request.form.get("stayId")
            checkout_time = datetime.now().strftime("%Y-%m-%d %H:%M")

            room = conn.execute("SELECT roomId FROM room_assignment WHERE stayId = ? LIMIT 1", (stay_id,)).fetchone()
            conn.execute("UPDATE stay SET checkOut = ? WHERE stayId = ?", (checkout_time, stay_id))
            conn.execute("UPDATE room_assignment SET assignedTo = ? WHERE stayId = ?", (checkout_time, stay_id))

            if room:
                conn.execute("UPDATE room SET roomStatus = 'cleaning' WHERE roomID = ?", (room["roomId"],))

            conn.commit()

        conn.close()
        return redirect(url_for("checkin"))

    guests = conn.execute("""
        SELECT g.guestId, p.first_name, p.last_name
        FROM guest g
        JOIN person p ON g.guestId = p.personId
        ORDER BY p.last_name
    """).fetchall()

    rooms = conn.execute("""
        SELECT roomID, roomNumber, roomStatus
        FROM room
        ORDER BY roomNumber
    """).fetchall()

    active_stays = conn.execute("""
        SELECT s.stayId, p.first_name, p.last_name, r.roomNumber, s.checkIn, s.checkOut
        FROM stay s
        JOIN person p ON s.guestId = p.personId
        JOIN room_assignment ra ON s.stayId = ra.stayId
        JOIN room r ON ra.roomId = r.roomID
        ORDER BY s.stayId DESC
    """).fetchall()

    conn.close()
    return render_template("checkin.html", guests=guests, rooms=rooms, active_stays=active_stays)

@app.route("/maintenance", methods=["GET", "POST"])
def maintenance():
    conn = get_db_connection()

    if request.method == "POST":
        room_id = request.form.get("roomId")
        status = request.form.get("roomStatus")
        conn.execute("UPDATE room SET roomStatus = ? WHERE roomID = ?", (status, room_id))
        conn.commit()

    rooms = conn.execute("""
        SELECT r.roomID, r.roomNumber, r.roomStatus,
               f.floorNumber, w.wingName, b.buildingName
        FROM room r
        JOIN floor f ON r.floorID = f.floorID
        JOIN wing w ON f.wingID = w.wingID
        JOIN building b ON w.buildingID = b.buildingID
        ORDER BY r.roomNumber
    """).fetchall()

    conn.close()
    return render_template("maintenance.html", rooms=rooms)

@app.route("/guests", methods=["GET", "POST"])
def guest_lookup():
    conn = get_db_connection()
    keyword = request.form.get("keyword") if request.method == "POST" else ""
    guests = []
    stays = []
    charges = []

    if keyword:
        guests = conn.execute("""
            SELECT g.guestId, p.first_name, p.last_name, p.phone, p.email
            FROM guest g
            JOIN person p ON g.guestId = p.personId
            WHERE p.first_name LIKE ? OR p.last_name LIKE ?
            ORDER BY p.last_name
        """, (f"%{keyword}%", f"%{keyword}%")).fetchall()

        if guests:
            guest_id = guests[0]["guestId"]

            stays = conn.execute("""
                SELECT s.stayId, s.checkIn, s.checkOut, r.roomNumber
                FROM stay s
                LEFT JOIN room_assignment ra ON s.stayId = ra.stayId
                LEFT JOIN room r ON ra.roomId = r.roomID
                WHERE s.guestId = ?
                ORDER BY s.checkIn DESC
            """, (guest_id,)).fetchall()

            charges = conn.execute("""
                SELECT c.chargeId, sv.serviceType, c.amount, c.chargeDateTime, c.description
                FROM charge c
                JOIN service sv ON c.serviceId = sv.serviceId
                JOIN stay s ON c.stayId = s.stayId
                WHERE s.guestId = ?
                ORDER BY c.chargeDateTime DESC
            """, (guest_id,)).fetchall()

    conn.close()
    return render_template("guest_lookup.html", keyword=keyword, guests=guests, stays=stays, charges=charges)

@app.route("/billing", methods=["GET", "POST"])
def billing():
    conn = get_db_connection()

    keyword = request.form.get("keyword", "").strip() if request.method == "POST" else ""

    where_clause = ""
    params = []

    if keyword:
        where_clause = """
            WHERE CAST(bp.billingPartyId AS TEXT) LIKE ?
               OR p.first_name LIKE ?
               OR p.last_name LIKE ?
               OR CAST(o.organizationId AS TEXT) LIKE ?
        """
        params = [f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"]

    billing_totals = conn.execute(f"""
        SELECT bp.billingPartyId, p.first_name, p.last_name, o.organizationId,
               ROUND(SUM(c.amount), 2) AS totalAmount
        FROM billing_party bp
        JOIN charge c ON bp.billingPartyId = c.billingPartyId
        LEFT JOIN person p ON bp.personId = p.personId
        LEFT JOIN organization o ON bp.organizationId = o.organizationId
        {where_clause}
        GROUP BY bp.billingPartyId
        ORDER BY totalAmount DESC
    """, params).fetchall()

    charges = conn.execute("""
        SELECT c.chargeId, sv.serviceType, c.amount, c.chargeDateTime,
               c.stayId, c.eventId, c.description,
               bp.billingPartyId,
               p.first_name, p.last_name, o.organizationId
        FROM charge c
        JOIN service sv ON c.serviceId = sv.serviceId
        JOIN billing_party bp ON c.billingPartyId = bp.billingPartyId
        LEFT JOIN person p ON bp.personId = p.personId
        LEFT JOIN organization o ON bp.organizationId = o.organizationId
        ORDER BY c.chargeDateTime DESC
    """).fetchall()

    summary = conn.execute("""
        SELECT COUNT(DISTINCT billingPartyId) AS partyCount,
               COUNT(*) AS chargeCount,
               ROUND(COALESCE(SUM(amount), 0), 2) AS totalAmount
        FROM charge
    """).fetchone()

    conn.close()

    return render_template(
        "billing.html",
        billing_totals=billing_totals,
        charges=charges,
        summary=summary,
        keyword=keyword
    )

@app.route("/reports")
def reports():
    conn = get_db_connection()

    revenue_by_service = conn.execute("""
        SELECT s.serviceType, ROUND(SUM(c.amount), 2) AS revenue
        FROM charge c
        JOIN service s ON c.serviceId = s.serviceId
        GROUP BY s.serviceType
        ORDER BY revenue DESC
    """).fetchall()

    revenue_by_room = conn.execute("""
        SELECT r.roomNumber, ROUND(SUM(c.amount), 2) AS totalRevenue
        FROM charge c
        JOIN room r ON c.roomId = r.roomID
        GROUP BY r.roomID
        ORDER BY totalRevenue DESC
    """).fetchall()

    room_status = conn.execute("""
        SELECT roomStatus, COUNT(*) AS count
        FROM room
        GROUP BY roomStatus
    """).fetchall()

    guests_multiple_stays = conn.execute("""
        SELECT s.guestId, p.first_name, p.last_name, COUNT(*) AS stayCount
        FROM stay s
        JOIN person p ON s.guestId = p.personId
        GROUP BY s.guestId
        HAVING COUNT(*) > 1
    """).fetchall()

    event_schedule = conn.execute("""
        SELECT e.eventId, e.startDate, e.endDate, r.roomNumber, er.usageSlot
        FROM event e
        JOIN event_room er ON e.eventId = er.eventId
        JOIN room r ON er.roomId = r.roomID
        ORDER BY e.eventId, er.usageSlot
    """).fetchall()

    charges_with_owner = conn.execute("""
        SELECT c.chargeId, c.amount, c.chargeDateTime, c.description,
               s.serviceType, r.roomNumber, c.stayId, c.eventId,
               p.first_name, p.last_name, o.organizationId,
               CASE
                   WHEN c.stayId IS NOT NULL THEN 'Stay'
                   WHEN c.eventId IS NOT NULL THEN 'Event'
                   ELSE 'Unknown'
               END AS belongsTo
        FROM charge c
        LEFT JOIN service s ON c.serviceId = s.serviceId
        LEFT JOIN room r ON c.roomId = r.roomID
        LEFT JOIN billing_party bp ON c.billingPartyId = bp.billingPartyId
        LEFT JOIN person p ON bp.personId = p.personId
        LEFT JOIN organization o ON bp.organizationId = o.organizationId
        ORDER BY c.chargeId
    """).fetchall()

    conn.close()

    return render_template(
        "reports.html",
        revenue_by_service=revenue_by_service,
        revenue_by_room=revenue_by_room,
        guests_multiple_stays=guests_multiple_stays,
        event_schedule=event_schedule,
        charges_with_owner=charges_with_owner,
        service_labels=[r["serviceType"] for r in revenue_by_service],
        service_data=[r["revenue"] for r in revenue_by_service],
        room_labels=[r["roomNumber"] for r in revenue_by_room[:8]],
        room_data=[r["totalRevenue"] for r in revenue_by_room[:8]],
        status_labels=[r["roomStatus"] for r in room_status],
        status_data=[r["count"] for r in room_status]
    )

@app.errorhandler(Exception)
def handle_error(e):
    return render_template("error.html", error=str(e)), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004, debug=True)
